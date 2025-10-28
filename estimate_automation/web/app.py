from __future__ import annotations

import cgi
import logging
import os
import re
import unicodedata
import zipfile
from datetime import datetime
from decimal import Decimal
from io import BytesIO
from pathlib import Path
from typing import Callable, Iterable, Tuple
from urllib.parse import parse_qs

from ..exceptions import EstimateAutomationError, ValidationError
from ..logging import configure_logging
from ..service import generate_artifacts
from ..settings import get_settings

ResponseBody = Iterable[bytes]
StartResponse = Callable[[str, list[Tuple[str, str]]], None]


class EstimateWebApp:
    """Minimal WSGI application serving the estimate automation UI and API."""

    def __init__(self) -> None:
        configure_logging()
        self.logger = logging.getLogger("estimate_automation.web")
        self.settings = get_settings()
        self.base_dir = Path(__file__).parent
        self.template_path = self.base_dir / "templates" / "index.html"
        self.static_dir = self.base_dir / "static"

    def __call__(self, environ: dict, start_response: StartResponse) -> ResponseBody:
        method = environ.get("REQUEST_METHOD", "GET").upper()
        path = environ.get("PATH_INFO", "/")

        if method == "GET" and path == "/":
            return self._serve_index(start_response)
        if method == "GET" and path == "/healthz":
            return self._serve_healthz(start_response)
        if method == "OPTIONS" and path == "/api/estimates":
            return self._serve_options(start_response)
        if path.startswith("/static/") and method == "GET":
            return self._serve_static(path, start_response)
        if path == "/api/estimates" and method == "POST":
            return self._handle_estimate(environ, start_response)

        start_response("404 Not Found", self._headers([("Content-Type", "text/plain; charset=utf-8")]))
        return ["Not Found".encode("utf-8")]

    # --- Route handlers -------------------------------------------------

    def _serve_index(self, start_response: StartResponse) -> ResponseBody:
        html = self._render_index()
        start_response("200 OK", self._headers([("Content-Type", "text/html; charset=utf-8")]))
        return [html.encode("utf-8")]

    def _serve_healthz(self, start_response: StartResponse) -> ResponseBody:
        start_response("200 OK", self._headers([("Content-Type", "application/json")]))
        return [b"{\"status\": \"ok\"}"]

    def _serve_options(self, start_response: StartResponse) -> ResponseBody:
        headers = self._headers(
            [
                ("Allow", "POST, OPTIONS"),
                ("Access-Control-Allow-Methods", "POST, OPTIONS"),
                ("Access-Control-Allow-Headers", "Content-Type, X-API-Key"),
            ]
        )
        start_response("204 No Content", headers)
        return [b""]

    def _serve_static(self, path: str, start_response: StartResponse) -> ResponseBody:
        relative = path[len("/static/") :]
        file_path = self.static_dir / relative
        if not file_path.exists():
            start_response("404 Not Found", self._headers([("Content-Type", "text/plain")]))
            return [b"Not Found"]

        mime_type = "text/plain"
        if file_path.suffix == ".css":
            mime_type = "text/css"
        elif file_path.suffix in {".jpg", ".jpeg"}:
            mime_type = "image/jpeg"
        elif file_path.suffix == ".png":
            mime_type = "image/png"

        start_response("200 OK", self._headers([("Content-Type", f"{mime_type}; charset=utf-8")]))
        return [file_path.read_bytes()]

    def _handle_estimate(self, environ: dict, start_response: StartResponse) -> ResponseBody:
        form = cgi.FieldStorage(fp=environ["wsgi.input"], environ=environ, keep_blank_values=True)

        provided_api_key = (
            form.getvalue("form_api_key")
            or environ.get("HTTP_X_API_KEY")
            or parse_qs(environ.get("QUERY_STRING", "")).get("api_key", [None])[0]
        )
        if self.settings.api_key and provided_api_key != self.settings.api_key:
            self.logger.warning("Rejected request due to invalid API key")
            start_response("401 Unauthorized", self._headers([("Content-Type", "text/plain")]))
            return ["Invalid API key".encode("utf-8")]

        try:
            unit_file = form["unit_price_master"].file
            template_file = form["template"].file
            memo_file = form["memo"].file
        except KeyError:
            start_response("400 Bad Request", self._headers([("Content-Type", "text/plain")]))
            return ["必要なファイルが不足しています".encode("utf-8")]

        try:
            unit_csv = unit_file.read().decode("utf-8-sig")
            template_csv = template_file.read().decode("utf-8-sig")
            memo_json = memo_file.read().decode("utf-8")
        except UnicodeDecodeError:
            start_response("400 Bad Request", self._headers([("Content-Type", "text/plain")]))
            return ["ファイルの文字コードはUTF-8である必要があります".encode("utf-8")]

        tax_rate_value = form.getvalue("tax_rate")
        try:
            tax_rate = Decimal(tax_rate_value) if tax_rate_value else Decimal(str(self.settings.default_tax_rate))
        except Exception:  # pragma: no cover - defensive
            start_response("400 Bad Request", self._headers([("Content-Type", "text/plain")]))
            return ["税率の形式が正しくありません".encode("utf-8")]

        try:
            artifacts = generate_artifacts(unit_csv, template_csv, memo_json, tax_rate)
        except ValidationError as exc:
            self.logger.info("Validation error while generating estimate: %s", exc)
            start_response("400 Bad Request", self._headers([("Content-Type", "text/plain")]))
            return [str(exc).encode("utf-8")]
        except EstimateAutomationError as exc:  # pragma: no cover - defensive
            self.logger.error("Domain error: %s", exc)
            start_response("422 Unprocessable Entity", self._headers([("Content-Type", "text/plain")]))
            return [str(exc).encode("utf-8")]
        except Exception as exc:  # pragma: no cover - unexpected failures
            self.logger.exception("Unexpected failure during estimate generation")
            start_response("500 Internal Server Error", self._headers([("Content-Type", "text/plain")]))
            return ["サーバーエラーが発生しました".encode("utf-8")]

        buffer = BytesIO()
        file_stem = slugify(artifacts.estimate.memo.project_name)
        with zipfile.ZipFile(buffer, "w", zipfile.ZIP_DEFLATED) as archive:
            archive.writestr(f"{file_stem}_estimate.pdf", artifacts.pdf_bytes)
            archive.writestr(f"{file_stem}_email.txt", artifacts.email_text)
        buffer.seek(0)

        headers = self._headers(
            [
                ("Content-Type", "application/zip"),
                ("Content-Disposition", f"attachment; filename=\"{file_stem}.zip\""),
            ]
        )
        start_response("200 OK", headers)
        self.logger.info("Generated artifacts for %s", artifacts.estimate.memo.project_name)
        return [buffer.getvalue()]

    # --- Helpers --------------------------------------------------------

    def _render_index(self) -> str:
        template = self.template_path.read_text(encoding="utf-8")
        api_key_field = ""
        if self.settings.api_key:
            indent = " " * 16
            api_key_field = (
                f"{indent}<label class=\"field\">\n"
                f"{indent}    <span>APIキー</span>\n"
                f"{indent}    <input type=\"password\" name=\"form_api_key\" required placeholder=\"管理者から共有されたキーを入力\">\n"
                f"{indent}</label>\n"
            )
        content = template
        content = content.replace("{{API_KEY_FIELD}}", api_key_field)
        content = content.replace("{{DEFAULT_TAX_RATE}}", str(self.settings.default_tax_rate))
        content = content.replace("{{CURRENT_YEAR}}", str(datetime.utcnow().year))
        return content

    def _headers(self, extra: list[Tuple[str, str]]) -> list[Tuple[str, str]]:
        headers: list[Tuple[str, str]] = []
        origin = self.settings.cors_origins[0] if self.settings.cors_origins else "*"
        headers.append(("Access-Control-Allow-Origin", origin))
        headers.extend(extra)
        return headers


def slugify(value: str) -> str:
    normalized = unicodedata.normalize("NFKC", value)
    sanitized = re.sub(r"[^A-Za-z0-9_-]+", "-", normalized).strip("-")
    return sanitized or "estimate"


app = EstimateWebApp()


def start() -> None:  # pragma: no cover - CLI entry point
    from wsgiref.simple_server import make_server

    host = os.getenv("ESTIMATE_AUTOMATION_HOST", "0.0.0.0")
    port = int(os.getenv("PORT", "8000"))
    with make_server(host, port, app) as server:
        print(f"Serving on http://{host}:{port}")
        server.serve_forever()
