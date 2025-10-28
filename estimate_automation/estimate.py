from __future__ import annotations

from decimal import Decimal, ROUND_HALF_UP, ROUND_UP
from typing import Iterable

from .models import Adjustment, EstimateItem, EstimateResult, ProjectMemo


def build_estimate(
    items: Iterable[EstimateItem],
    memo: ProjectMemo,
    tax_rate: Decimal,
) -> EstimateResult:
    subtotal = sum((item.subtotal for item in items), Decimal("0"))

    adjustments_total = sum((adj.amount for adj in memo.adjustments), Decimal("0"))

    tax_exclusive_total = (subtotal + adjustments_total).quantize(Decimal("1"), rounding=ROUND_HALF_UP)
    tax_multiplier = Decimal("1") + tax_rate
    tax_inclusive_raw = (tax_exclusive_total * tax_multiplier)
    tax_inclusive_total = tax_inclusive_raw.quantize(Decimal("1"), rounding=ROUND_UP)
    tax_amount = tax_inclusive_total - tax_exclusive_total

    return EstimateResult(
        items=list(items),
        memo=memo,
        subtotal=subtotal,
        adjustments_total=adjustments_total,
        tax_exclusive_total=tax_exclusive_total,
        tax_amount=tax_amount,
        tax_inclusive_total=tax_inclusive_total,
        tax_rate=tax_rate,
    )
