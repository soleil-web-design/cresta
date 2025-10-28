from __future__ import annotations

from decimal import Decimal
from pathlib import Path
from typing import List

from .models import EstimateResult

LINE_HEIGHT = 18
TOP_MARGIN = 780
LEFT_MARGIN = 50
FONT_SIZE = 12
MAX_LINES_PER_PAGE = 40
PAGE_HEIGHT = 842
PAGE_WIDTH = 595
MIN_BOTTOM_MARGIN = 40


def generate_pdf(estimate: EstimateResult, output_path: Path) -> None:
    pages: List[List[str]] = []
    current: List[str] = []

    def add_line(text: str) -> None:
        nonlocal current
        if len(current) >= MAX_LINES_PER_PAGE:
            pages.append(current)
            current = []
        current.append(text)

    add_line(f"見積書: {estimate.memo.project_name}")
    add_line(f"発行日: {estimate.memo.issue_date}")
    add_line(f"納期: {estimate.memo.due_date}")
    add_line(f"宛先: {estimate.memo.client_name}")
    add_line(f"現場所在地: {estimate.memo.location}")
    add_line("")
    add_line("【明細】")
    add_line("品名 / 数量 / 単価 / 小計")

    for item in estimate.items:
        add_line(
            f"- {item.name} / {format_decimal(item.quantity)}{item.unit} / {format_currency(item.unit_price)} / {format_currency(item.subtotal)}"
        )

    if estimate.memo.adjustments:
        add_line("")
        add_line("【調整項目】")
        for adj in estimate.memo.adjustments:
            add_line(f"- {adj.description}: {format_currency(adj.amount)}")

    if estimate.memo.notes:
        add_line("")
        add_line("【特記事項】")
        for note in estimate.memo.notes:
            add_line(f"- {note}")

    add_line("")
    add_line(f"税別小計: {format_currency(estimate.subtotal)}")
    add_line(f"調整計: {format_currency(estimate.adjustments_total)}")
    add_line(f"税別合計 (四捨五入後): {format_currency(estimate.tax_exclusive_total)}")
    add_line(
        f"消費税 ({(estimate.tax_rate * Decimal('100')).quantize(Decimal('1'))}%): {format_currency(estimate.tax_amount)}"
    )
    add_line(f"税込合計 (切り上げ後): {format_currency(estimate.tax_inclusive_total)}")
    add_line("")
    add_line("適格請求書発行事業者登録番号")
    add_line(f"{estimate.memo.invoice_registration_number}")

    add_line("")
    add_line("連絡先")
    add_line(f"{estimate.memo.contact.company} {estimate.memo.contact.person}")
    add_line(f"Email: {estimate.memo.contact.email}")
    if estimate.memo.contact.phone:
        add_line(f"Tel: {estimate.memo.contact.phone}")

    if current:
        pages.append(current)

    pdf_bytes = _build_pdf_from_pages(pages)
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_bytes(pdf_bytes)


def _build_pdf_from_pages(pages: List[List[str]]) -> bytes:
    objects: List[bytearray] = []

    def add_object(content: str | bytes) -> int:
        if isinstance(content, str):
            content_bytes = content.encode("utf-8")
        else:
            content_bytes = content
        objects.append(bytearray(content_bytes))
        return len(objects)

    font_obj = add_object("<< /Type /Font /Subtype /Type1 /BaseFont /Helvetica >>")

    page_refs: List[int] = []
    content_refs: List[int] = []

    for page_lines in pages:
        stream_commands = []
        y = TOP_MARGIN
        for line in page_lines:
            sanitized = (
                line.replace("\\", r"\\")
                .replace("(", r"\(")
                .replace(")", r"\)")
            )
            stream_commands.append(f"BT /F1 {FONT_SIZE} Tf {LEFT_MARGIN} {y} Td ({sanitized}) Tj ET")
            y -= LINE_HEIGHT
            if y < MIN_BOTTOM_MARGIN:
                y = TOP_MARGIN
        stream_text = "\n".join(stream_commands)
        stream_bytes = stream_text.encode("utf-8")
        content_ref = add_object(b"")
        content_stream = bytearray()
        content_stream.extend(f"<< /Length {len(stream_bytes)} >>\nstream\n".encode("utf-8"))
        content_stream.extend(stream_bytes)
        content_stream.extend(b"\nendstream")
        objects[content_ref - 1] = content_stream
        content_refs.append(content_ref)
        page_ref = add_object(b"")
        page_refs.append(page_ref)

    pages_obj = add_object(b"")
    catalog_obj = add_object(b"")

    for page_ref, content_ref in zip(page_refs, content_refs):
        page_dict = (
            f"<< /Type /Page /Parent {pages_obj} 0 R /MediaBox [0 0 {PAGE_WIDTH} {PAGE_HEIGHT}] "
            f"/Resources << /Font << /F1 {font_obj} 0 R >> >> /Contents {content_ref} 0 R >>"
        )
        objects[page_ref - 1] = bytearray(page_dict.encode("utf-8"))

    kids = "[" + " ".join(f"{ref} 0 R" for ref in page_refs) + "]"
    pages_dict = f"<< /Type /Pages /Kids {kids} /Count {len(page_refs)} >>"
    objects[pages_obj - 1] = bytearray(pages_dict.encode("utf-8"))

    catalog_dict = f"<< /Type /Catalog /Pages {pages_obj} 0 R >>"
    objects[catalog_obj - 1] = bytearray(catalog_dict.encode("utf-8"))

    return _assemble_pdf(objects, catalog_obj)


def _assemble_pdf(objects: List[bytearray], catalog_obj: int) -> bytes:
    buffer = bytearray()
    buffer.extend(b"%PDF-1.4\n")
    offsets = [0]
    for obj_id, content in enumerate(objects, start=1):
        offsets.append(len(buffer))
        buffer.extend(f"{obj_id} 0 obj\n".encode("utf-8"))
        buffer.extend(content)
        buffer.extend(b"\nendobj\n")

    xref_start = len(buffer)
    buffer.extend(f"xref\n0 {len(objects)+1}\n".encode("utf-8"))
    buffer.extend(b"0000000000 65535 f \n")
    for offset in offsets[1:]:
        buffer.extend(f"{offset:010d} 00000 n \n".encode("utf-8"))
    buffer.extend(b"trailer\n")
    buffer.extend(f"<< /Size {len(objects)+1} /Root {catalog_obj} 0 R >>\n".encode("utf-8"))
    buffer.extend(f"startxref\n{xref_start}\n%%EOF".encode("utf-8"))
    return bytes(buffer)


def format_currency(value: Decimal) -> str:
    quantized = value.quantize(Decimal("1")) if value == value.to_integral_value() else value
    absolute = abs(quantized)
    formatted = (
        f"{absolute:,}"
        if absolute == absolute.to_integral_value()
        else format(absolute, ",.2f")
    )
    prefix = "-" if quantized < 0 else ""
    return f"{prefix}¥{formatted}"


def format_decimal(value: Decimal) -> str:
    normalized = value.normalize()
    if normalized == normalized.to_integral():
        return f"{normalized:.0f}"
    return format(normalized, "f")
