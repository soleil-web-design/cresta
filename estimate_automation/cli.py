from __future__ import annotations

import argparse
import json
import time
from decimal import Decimal
from pathlib import Path
from typing import Any, Dict

from .email import build_email_draft
from .estimate import build_estimate
from .parser import load_project_memo, load_template, load_unit_price_master
from .pdf import generate_pdf


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Generate estimate PDFs and email drafts")
    parser.add_argument("config", type=Path, help="Path to configuration JSON file")
    parser.add_argument("--project", type=str, help="Run a single project by name", default=None)
    return parser.parse_args()


def load_config(path: Path) -> Dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8"))


def main() -> None:
    args = parse_args()
    config = load_config(args.config)

    unit_price_master = load_unit_price_master(Path(config["unit_price_master"]))
    tax_rate = Decimal(str(config.get("tax_rate", "0.1")))
    output_root = Path(config.get("output_root", "outputs"))

    retry = config.get("retry", {})
    max_attempts = int(retry.get("max_attempts", 1))
    delay_seconds = float(retry.get("delay_seconds", 0))

    projects = config.get("projects", [])
    if args.project:
        projects = [p for p in projects if p.get("name") == args.project]
        if not projects:
            raise SystemExit(f"Project '{args.project}' not found in config")

    for project_cfg in projects:
        project_name = project_cfg["name"]
        template_path = Path(project_cfg["template"])
        memo_path = Path(project_cfg["memo"])
        output_dir = output_root / project_cfg.get("output_subdir", project_name)
        pdf_name = project_cfg.get("pdf_name", f"{project_name}_estimate.pdf")
        email_name = project_cfg.get("email_name", f"{project_name}_email.txt")

        attempts = 0
        while True:
            attempts += 1
            try:
                memo = load_project_memo(memo_path)
                items = load_template(template_path, unit_price_master)
                estimate = build_estimate(items, memo, tax_rate)
                generate_pdf(estimate, output_dir / pdf_name)
                build_email_draft(estimate, output_dir / email_name)
                print(f"[OK] {project_name} -> {output_dir}")
                break
            except Exception as exc:  # pylint: disable=broad-exception-caught
                print(f"[ERROR] {project_name} attempt {attempts}: {exc}")
                if attempts >= max_attempts:
                    raise
                time.sleep(delay_seconds)


if __name__ == "__main__":
    main()
