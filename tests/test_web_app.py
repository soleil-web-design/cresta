from __future__ import annotations

from io import BytesIO
from pathlib import Path
from typing import Iterable, Tuple
import zipfile

from wsgiref.util import setup_testing_defaults

from estimate_automation.settings import get_settings
from estimate_automation.web.app import EstimateWebApp

SAMPLES = Path("samples")


def _sample_files() -> list[Tuple[str, Tuple[str | None, bytes, str | None]]]:
    return [
        (
            "unit_price_master",
            (
                "unit.csv",
                (SAMPLES / "unit_prices.csv").read_bytes(),
                "text/csv",
            ),
        ),
        (
            "template",
            (
                "template.csv",
                (SAMPLES / "projects" / "sample_a" / "template.csv").read_bytes(),
                "text/csv",
            ),
        ),
        (
            "memo",
            (
                "memo.json",
                (SAMPLES / "projects" / "sample_a" / "memo.json").read_bytes(),
                "application/json",
            ),
        ),
    ]


def _build_multipart(parts: Iterable[Tuple[str, Tuple[str | None, bytes, str | None]]], extra_fields: dict[str, str] | None = None) -> tuple[str, bytes]:
    boundary = "----EstimateAutomationBoundary"
    body = BytesIO()
    for name, (filename, content, content_type) in parts:
        body.write(f"--{boundary}\r\n".encode("utf-8"))
        disposition = f'Content-Disposition: form-data; name="{name}"'
        if filename:
            disposition += f'; filename="{filename}"'
        body.write((disposition + "\r\n").encode("utf-8"))
        if content_type:
            body.write(f"Content-Type: {content_type}\r\n".encode("utf-8"))
        body.write(b"\r\n")
        body.write(content)
        body.write(b"\r\n")
    if extra_fields:
        for key, value in extra_fields.items():
            body.write(f"--{boundary}\r\n".encode("utf-8"))
            body.write(f'Content-Disposition: form-data; name="{key}"\r\n\r\n'.encode("utf-8"))
            body.write(value.encode("utf-8"))
            body.write(b"\r\n")
    body.write(f"--{boundary}--\r\n".encode("utf-8"))
    return boundary, body.getvalue()


def _call_app(app: EstimateWebApp, method: str, path: str, body: bytes, content_type: str, headers: dict[str, str] | None = None):
    environ: dict[str, object] = {}
    setup_testing_defaults(environ)
    environ["REQUEST_METHOD"] = method
    environ["PATH_INFO"] = path
    environ["CONTENT_TYPE"] = content_type
    environ["CONTENT_LENGTH"] = str(len(body))
    environ["wsgi.input"] = BytesIO(body)
    if headers:
        for key, value in headers.items():
            environ[f"HTTP_{key.upper().replace('-', '_')}"] = value

    captured: dict[str, object] = {}

    def start_response(status: str, response_headers: list[Tuple[str, str]]) -> None:
        captured["status"] = status
        captured["headers"] = dict(response_headers)

    response_body = b"".join(app(environ, start_response))
    return captured["status"], captured["headers"], response_body


def test_generate_estimate_artifacts() -> None:
    get_settings.cache_clear()
    app = EstimateWebApp()

    boundary, payload = _build_multipart(_sample_files())
    status, headers, body = _call_app(
        app,
        "POST",
        "/api/estimates",
        payload,
        f"multipart/form-data; boundary={boundary}",
    )

    assert status.startswith("200")
    assert headers["Content-Type"] == "application/zip"

    with zipfile.ZipFile(BytesIO(body)) as archive:
        names = archive.namelist()
        assert any(name.endswith("_estimate.pdf") for name in names)
        assert any(name.endswith("_email.txt") for name in names)
        pdf_name = next(name for name in names if name.endswith("_estimate.pdf"))
        email_name = next(name for name in names if name.endswith("_email.txt"))
        pdf_bytes = archive.read(pdf_name)
        email_text = archive.read(email_name).decode("utf-8")

    assert pdf_bytes.startswith(b"%PDF")
    assert "適格請求書発行事業者登録番号" in email_text


def test_api_key_enforcement(monkeypatch) -> None:
    monkeypatch.setenv("ESTIMATE_AUTOMATION_API_KEY", "super-secret")
    get_settings.cache_clear()
    app = EstimateWebApp()

    # Missing API key -> 401
    boundary, payload = _build_multipart(_sample_files())
    status, _, _ = _call_app(
        app,
        "POST",
        "/api/estimates",
        payload,
        f"multipart/form-data; boundary={boundary}",
    )
    assert status.startswith("401")

    # Valid API key via form field
    boundary, payload = _build_multipart(_sample_files(), extra_fields={"form_api_key": "super-secret"})
    status, _, _ = _call_app(
        app,
        "POST",
        "/api/estimates",
        payload,
        f"multipart/form-data; boundary={boundary}",
    )
    assert status.startswith("200")

    get_settings.cache_clear()
