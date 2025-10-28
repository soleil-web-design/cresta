from __future__ import annotations

from dataclasses import dataclass
from decimal import Decimal

from .email import render_email_draft
from .estimate import build_estimate
from .models import EstimateResult
from .parser import parse_project_memo, parse_template, parse_unit_price_master
from .pdf import render_pdf_bytes


@dataclass(slots=True)
class EstimateArtifacts:
    estimate: EstimateResult
    pdf_bytes: bytes
    email_text: str


def generate_artifacts(
    unit_price_csv: str,
    template_csv: str,
    memo_json: str,
    tax_rate: Decimal,
) -> EstimateArtifacts:
    master = parse_unit_price_master(unit_price_csv)
    items = parse_template(template_csv, master)
    memo = parse_project_memo(memo_json)
    estimate = build_estimate(items, memo, tax_rate)
    pdf_bytes = render_pdf_bytes(estimate)
    email_text = render_email_draft(estimate)
    return EstimateArtifacts(estimate=estimate, pdf_bytes=pdf_bytes, email_text=email_text)
