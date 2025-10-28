from __future__ import annotations

import json
from decimal import Decimal
from pathlib import Path
from typing import Dict, List

from .models import Adjustment, Contact, EmailSettings, EstimateItem, ProjectMemo


def load_unit_price_master(path: Path) -> Dict[str, Decimal]:
    import csv

    master: Dict[str, Decimal] = {}
    with path.open("r", encoding="utf-8-sig", newline="") as fh:
        reader = csv.DictReader(fh)
        required = {"品名", "単価"}
        missing = required - set(reader.fieldnames or [])
        if missing:
            raise ValueError(f"Unit price master missing columns: {missing}")
        for row in reader:
            name = row["品名"].strip()
            if not name:
                continue
            unit_price = _to_decimal(row.get("単価"))
            master[name] = unit_price
    return master


def load_template(path: Path, master: Dict[str, Decimal]) -> List[EstimateItem]:
    import csv

    items: List[EstimateItem] = []
    with path.open("r", encoding="utf-8-sig", newline="") as fh:
        reader = csv.DictReader(fh)
        required = {"品名", "単価", "単位", "数量", "小計"}
        missing = required - set(reader.fieldnames or [])
        if missing:
            raise ValueError(f"Template missing columns: {missing}")
        for row in reader:
            name = row["品名"].strip()
            if not name:
                continue
            unit = row["単位"].strip() or "式"
            quantity = _to_decimal(row["数量"]) if row["数量"] else Decimal("0")
            unit_price = _resolve_unit_price(row.get("単価"), name, master)
            subtotal = _to_decimal(row["小計"]) if row["小計"] else (unit_price * quantity)
            items.append(
                EstimateItem(
                    name=name,
                    unit_price=unit_price,
                    unit=unit,
                    quantity=quantity,
                    subtotal=subtotal,
                )
            )
    return items


def load_project_memo(path: Path) -> ProjectMemo:
    raw = json.loads(path.read_text(encoding="utf-8"))

    contact = raw.get("contact") or {}
    email_raw = raw.get("email")
    adjustments_raw = raw.get("adjustments") or []

    memo = ProjectMemo(
        project_name=raw["project_name"],
        client_name=raw["client_name"],
        location=raw["location"],
        issue_date=raw["issue_date"],
        due_date=raw["due_date"],
        invoice_registration_number=raw["invoice_registration_number"],
        contact=Contact(
            company=contact.get("company", ""),
            person=contact.get("person", ""),
            email=contact.get("email", ""),
            phone=contact.get("phone"),
        ),
        notes=list(raw.get("notes") or []),
        adjustments=[
            Adjustment(description=a["description"], amount=_to_decimal(a["amount"]))
            for a in adjustments_raw
        ],
        email=EmailSettings(
            to=list(email_raw.get("to", [])),
            cc=list(email_raw.get("cc", [])),
            subject=email_raw.get("subject"),
            body_template=email_raw.get("body_template"),
        )
        if email_raw
        else None,
    )
    return memo


def _resolve_unit_price(value: str | None, name: str, master: Dict[str, Decimal]) -> Decimal:
    if value is not None and value != "":
        return _to_decimal(value)
    if name not in master:
        raise ValueError(f"Unit price for '{name}' not found in master data")
    return master[name]


def _to_decimal(value: object) -> Decimal:
    if isinstance(value, Decimal):
        return value
    if value is None:
        return Decimal("0")
    text = str(value).strip()
    if not text:
        return Decimal("0")
    return Decimal(text)
