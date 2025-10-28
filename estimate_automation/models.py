from __future__ import annotations

from dataclasses import dataclass, field
from decimal import Decimal
from typing import List, Optional


@dataclass
class EstimateItem:
    """Represents a single row in the estimate template."""

    name: str
    unit_price: Decimal
    unit: str
    quantity: Decimal
    subtotal: Decimal


@dataclass
class Adjustment:
    description: str
    amount: Decimal


@dataclass
class Contact:
    company: str
    person: str
    email: str
    phone: Optional[str] = None


@dataclass
class EmailSettings:
    to: List[str]
    cc: List[str] = field(default_factory=list)
    subject: Optional[str] = None
    body_template: Optional[str] = None


@dataclass
class ProjectMemo:
    project_name: str
    client_name: str
    location: str
    issue_date: str
    due_date: str
    invoice_registration_number: str
    contact: Contact
    notes: List[str] = field(default_factory=list)
    adjustments: List[Adjustment] = field(default_factory=list)
    email: Optional[EmailSettings] = None


@dataclass
class EstimateResult:
    items: List[EstimateItem]
    memo: ProjectMemo
    subtotal: Decimal
    adjustments_total: Decimal
    tax_exclusive_total: Decimal
    tax_amount: Decimal
    tax_inclusive_total: Decimal
    tax_rate: Decimal
