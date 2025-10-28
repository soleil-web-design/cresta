from __future__ import annotations

import csv
import io
import json
from decimal import Decimal
from pathlib import Path
from typing import Dict, Iterable, List, TextIO

from .exceptions import ValidationError
from .models import Adjustment, Contact, EmailSettings, EstimateItem, ProjectMemo


def load_unit_price_master(path: Path) -> Dict[str, Decimal]:
    with path.open("r", encoding="utf-8-sig", newline="") as fh:
        return parse_unit_price_master(fh.read())


def parse_unit_price_master(text: str) -> Dict[str, Decimal]:
    return _read_unit_price_master(io.StringIO(text))


def load_template(path: Path, master: Dict[str, Decimal]) -> List[EstimateItem]:
    with path.open("r", encoding="utf-8-sig", newline="") as fh:
        return parse_template(fh.read(), master)


def parse_template(text: str, master: Dict[str, Decimal]) -> List[EstimateItem]:
    return list(_read_template(io.StringIO(text), master))


def load_project_memo(path: Path) -> ProjectMemo:
    return parse_project_memo(path.read_text(encoding="utf-8"))


def parse_project_memo(text: str) -> ProjectMemo:
    try:
        raw = json.loads(text)
    except json.JSONDecodeError as exc:
        raise ValidationError(f"Invalid memo JSON: {exc}") from exc

    try:
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
    except KeyError as exc:  # pragma: no cover - defensive programming
        raise ValidationError(f"Memo missing required field: {exc.args[0]}") from exc

    return memo


def _read_unit_price_master(handle: TextIO) -> Dict[str, Decimal]:
    try:
        reader = csv.DictReader(handle)
    except csv.Error as exc:  # pragma: no cover - depends on CSV dialect
        raise ValidationError(f"Failed to read unit price master: {exc}") from exc

    required = {"品名", "単価"}
    missing = required - set(reader.fieldnames or [])
    if missing:
        raise ValidationError(f"Unit price master missing columns: {missing}")

    master: Dict[str, Decimal] = {}
    for row in reader:
        name = (row.get("品名") or "").strip()
        if not name:
            continue
        unit_price = _to_decimal(row.get("単価"))
        master[name] = unit_price
    if not master:
        raise ValidationError("Unit price master is empty")
    return master


def _read_template(handle: TextIO, master: Dict[str, Decimal]) -> Iterable[EstimateItem]:
    try:
        reader = csv.DictReader(handle)
    except csv.Error as exc:  # pragma: no cover - defensive
        raise ValidationError(f"Failed to read template: {exc}") from exc

    required = {"品名", "単価", "単位", "数量", "小計"}
    missing = required - set(reader.fieldnames or [])
    if missing:
        raise ValidationError(f"Template missing columns: {missing}")

    for row in reader:
        name = (row.get("品名") or "").strip()
        if not name:
            continue
        unit = (row.get("単位") or "式").strip()
        quantity = _to_decimal(row.get("数量")) if row.get("数量") else Decimal("0")
        unit_price = _resolve_unit_price(row.get("単価"), name, master)
        subtotal = _to_decimal(row.get("小計")) if row.get("小計") else (unit_price * quantity)
        yield EstimateItem(
            name=name,
            unit_price=unit_price,
            unit=unit,
            quantity=quantity,
            subtotal=subtotal,
        )


def _resolve_unit_price(value: str | None, name: str, master: Dict[str, Decimal]) -> Decimal:
    if value is not None and value != "":
        return _to_decimal(value)
    if name not in master:
        raise ValidationError(f"Unit price for '{name}' not found in master data")
    return master[name]


def _to_decimal(value: object | None) -> Decimal:
    if isinstance(value, Decimal):
        return value
    if value is None:
        return Decimal("0")
    text = str(value).strip()
    if not text:
        return Decimal("0")
    try:
        return Decimal(text)
    except Exception as exc:  # pragma: no cover - narrow failure case
        raise ValidationError(f"Invalid decimal value: {value}") from exc
