from __future__ import annotations

from decimal import Decimal
from pathlib import Path
from typing import List, Tuple

from .models import EstimateResult

PAGE_WIDTH = 595
PAGE_HEIGHT = 842
LEFT_MARGIN = 50
RIGHT_MARGIN = 50
TOP_MARGIN = 780
LINE_HEIGHT = 18
MIN_BOTTOM_MARGIN = 50
TITLE_FONT_SIZE = 18
BODY_FONT_SIZE = 12
SMALL_FONT_SIZE = 11

Command = Tuple[str, Tuple]


def generate_pdf(estimate: EstimateResult, output_path: Path) -> None:
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_bytes(render_pdf_bytes(estimate))


def render_pdf_bytes(estimate: EstimateResult) -> bytes:
    pages: List[List[Command]] = []
    current: List[Command] = []
    y_position = TOP_MARGIN

    def flush_page() -> None:
        nonlocal current, y_position
        if current:
            pages.append(current)
        current = []
        y_position = TOP_MARGIN

    def ensure_space(lines: int = 1) -> None:
        nonlocal y_position
        if y_position - LINE_HEIGHT * lines < MIN_BOTTOM_MARGIN:
            flush_page()

    def add_text(text: str, font_size: int = BODY_FONT_SIZE, offset: int = 0) -> None:
        nonlocal y_position
        ensure_space(1)
        current.append(("text", (LEFT_MARGIN + offset, y_position, font_size, text)))
        y_position -= LINE_HEIGHT

    def add_separator() -> None:
        nonlocal y_position
        current.append(("line", (LEFT_MARGIN, y_position + 6, PAGE_WIDTH - RIGHT_MARGIN, y_position + 6)))
        y_position -= 4

    def add_blank() -> None:
        nonlocal y_position
        y_position -= LINE_HEIGHT

    memo = estimate.memo

    add_text("御見積書", TITLE_FONT_SIZE)
    add_blank()

    header_rows = [
        ("案件名", memo.project_name),
        ("発行日", memo.issue_date),
        ("納期", memo.due_date),
        ("宛先", memo.client_name),
        ("現場所在地", memo.location),
        ("登録番号", memo.invoice_registration_number),
        ("担当", f"{memo.contact.company} {memo.contact.person}"),
    ]

    for label, value in header_rows:
        add_text(f"{label}: {value}", font_size=SMALL_FONT_SIZE)
    add_separator()

    add_text("【明細】", font_size=SMALL_FONT_SIZE)
    for item in estimate.items:
        add_text(item.name, font_size=SMALL_FONT_SIZE)
        add_text(
            f"    数量: {format_decimal(item.quantity)}{item.unit} / 単価: {format_currency(item.unit_price)} / 小計: {format_currency(item.subtotal)}",
            font_size=SMALL_FONT_SIZE,
        )
        add_blank()

    if memo.adjustments:
        add_separator()
        add_text("【調整項目】", font_size=SMALL_FONT_SIZE)
        for adj in memo.adjustments:
            add_text(f"- {adj.description}: {format_currency(adj.amount)}", font_size=SMALL_FONT_SIZE)
        add_blank()

    if memo.notes:
        add_separator()
        add_text("【特記事項】", font_size=SMALL_FONT_SIZE)
        for note in memo.notes:
            add_text(f"- {note}", font_size=SMALL_FONT_SIZE)
        add_blank()

    add_separator()
    add_text(f"税別小計: {format_currency(estimate.subtotal)}", font_size=BODY_FONT_SIZE)
    add_text(f"調整計: {format_currency(estimate.adjustments_total)}", font_size=BODY_FONT_SIZE)
    add_text(f"税別合計 (四捨五入): {format_currency(estimate.tax_exclusive_total)}", font_size=BODY_FONT_SIZE)
    add_text(
        f"消費税 ({(estimate.tax_rate * Decimal('100')).quantize(Decimal('1'))}%): {format_currency(estimate.tax_amount)}",
        font_size=BODY_FONT_SIZE,
    )
    add_text(f"税込合計 (切り上げ): {format_currency(estimate.tax_inclusive_total)}", font_size=BODY_FONT_SIZE)

    add_blank()
    add_text(f"連絡先 Email: {memo.contact.email}", font_size=SMALL_FONT_SIZE)
    if memo.contact.phone:
        add_text(f"Tel: {memo.contact.phone}", font_size=SMALL_FONT_SIZE)

    if current:
        pages.append(current)

    return _build_pdf(pages)


def _build_pdf(pages: List[List[Command]]) -> bytes:
    objects: List[bytes] = []

    def add_object(content: bytes) -> int:
        objects.append(content)
        return len(objects)

    font_obj = add_object(b"<< /Type /Font /Subtype /Type1 /BaseFont /Helvetica >>")

    page_refs: List[int] = []
    content_refs: List[int] = []

    for page in pages:
        stream_commands: List[str] = []
        line_width_set = False
        for command, payload in page:
            if command == "text":
                x, y, font_size, text = payload
                stream_commands.append(f"BT /F1 {font_size} Tf {x} {y} Td ({_escape(text)}) Tj ET")
            elif command == "line":
                x1, y1, x2, y2 = payload
                if not line_width_set:
                    stream_commands.append("0.5 w")
                    line_width_set = True
                stream_commands.append(f"{x1} {y1} m {x2} {y2} l S")
        stream = "\n".join(stream_commands).encode("utf-8")
        content_obj = add_object(b"")
        stream_buffer = bytearray()
        stream_buffer.extend(f"<< /Length {len(stream)} >>\nstream\n".encode("utf-8"))
        stream_buffer.extend(stream)
        stream_buffer.extend(b"\nendstream")
        objects[content_obj - 1] = bytes(stream_buffer)
        content_refs.append(content_obj)
        page_ref = add_object(b"")
        page_refs.append(page_ref)

    pages_obj = add_object(b"")
    catalog_obj = add_object(b"")

    for page_ref, content_ref in zip(page_refs, content_refs):
        page_dict = (
            f"<< /Type /Page /Parent {pages_obj} 0 R /MediaBox [0 0 {PAGE_WIDTH} {PAGE_HEIGHT}] "
            f"/Resources << /Font << /F1 {font_obj} 0 R >> >> /Contents {content_ref} 0 R >>"
        )
        objects[page_ref - 1] = page_dict.encode("utf-8")

    kids = "[" + " ".join(f"{ref} 0 R" for ref in page_refs) + "]"
    pages_dict = f"<< /Type /Pages /Kids {kids} /Count {len(page_refs)} >>"
    objects[pages_obj - 1] = pages_dict.encode("utf-8")

    catalog_dict = f"<< /Type /Catalog /Pages {pages_obj} 0 R >>"
    objects[catalog_obj - 1] = catalog_dict.encode("utf-8")

    return _assemble_pdf(objects, catalog_obj)


def _assemble_pdf(objects: List[bytes], catalog_obj: int) -> bytes:
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


def _escape(text: str) -> str:
    return text.replace("\\", r"\\").replace("(", r"\(").replace(")", r"\)")


def format_currency(value: Decimal) -> str:
    quantized = value.quantize(Decimal("1")) if value == value.to_integral_value() else value
    absolute = abs(quantized)
    formatted = (
        f"{absolute:,}" if absolute == absolute.to_integral_value() else format(absolute, ",.2f")
    )
    prefix = "-" if quantized < 0 else ""
    return f"{prefix}¥{formatted}"


def format_decimal(value: Decimal) -> str:
    normalized = value.normalize()
    if normalized == normalized.to_integral():
        return f"{normalized:.0f}"
    return format(normalized, "f")
