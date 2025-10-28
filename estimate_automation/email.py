from __future__ import annotations

from pathlib import Path
from typing import List

from .models import EstimateResult


DEFAULT_SUBJECT_TEMPLATE = "【御見積書送付】{project_name}"
DEFAULT_BODY_TEMPLATE = (
    "{client_name} {contact_person} 様\n\n"
    "いつもお世話になっております。{company}の{contact_person}です。\n"
    "標記の件につきまして、添付の通り御見積書をお送りいたします。\n"
    "税込合計は{total_with_tax}となります。\n\n"
    "内容をご確認のうえ、ご不明点がございましたらご連絡ください。\n"
    "引き続きよろしくお願いいたします。"
)


def build_email_draft(estimate: EstimateResult, output_path: Path) -> None:
    memo = estimate.memo
    email_settings = memo.email

    to_addresses: List[str] = email_settings.to if email_settings and email_settings.to else [memo.contact.email]
    cc_addresses: List[str] = email_settings.cc if email_settings else []
    subject_template = email_settings.subject if email_settings and email_settings.subject else DEFAULT_SUBJECT_TEMPLATE
    body_template = email_settings.body_template if email_settings and email_settings.body_template else DEFAULT_BODY_TEMPLATE

    context = {
        "project_name": memo.project_name,
        "client_name": memo.client_name,
        "contact_person": memo.contact.person,
        "company": memo.contact.company,
        "total_with_tax": f"¥{estimate.tax_inclusive_total:,}",
        "issue_date": memo.issue_date,
        "due_date": memo.due_date,
        "invoice_number": memo.invoice_registration_number,
    }

    subject = subject_template.format(**context)
    body_template = body_template.replace("\\n", "\n")
    body = body_template.format(**context)

    lines = [
        f"To: {', '.join(to_addresses)}",
        f"Cc: {', '.join(cc_addresses) if cc_addresses else '-'}",
        f"Subject: {subject}",
        "",
        body,
        "",
        f"添付資料: 見積書（{memo.project_name}）.pdf",
        f"発行日: {memo.issue_date}",
        f"適格請求書発行事業者登録番号: {memo.invoice_registration_number}",
    ]

    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text("\n".join(lines) + "\n", encoding="utf-8")
