"""Dựng nội dung bài viết từ văn bản thuần sang HTML an toàn.

Bài viết trong CSDL lưu văn bản thuần, biên tập viên có thể dùng một tập cú pháp
rất nhỏ để trình bày cho dễ đọc:

    ## Tiêu đề mục          tiêu đề cấp 2 (có mục lục tự động)
    ### Tiêu đề phụ         tiêu đề cấp 3
    - gạch đầu dòng
    1. đánh số
    > trích dẫn
    | cột | cột |            bảng, dòng thứ hai là dòng kẻ phân cách
    **đậm**

Mọi nội dung đều được escape trước khi ghép thẻ, nên bài viết không thể chèn
HTML lạ vào trang. Toàn bộ xử lý chạy nội bộ, không phụ thuộc thư viện ngoài.
"""

from __future__ import annotations

import re
import unicodedata
from html import escape

INLINE_BOLD = re.compile(r"\*\*(.+?)\*\*")
ORDERED = re.compile(r"^\d+[.)]\s+")
TABLE_DIVIDER = re.compile(r"^[\s:|-]+$")

H2_CLASS = ("font-headline-lg text-headline-lg text-on-surface mt-6 mb-3 pb-1.5 "
            "border-b border-outline-variant/40 scroll-mt-24")
H3_CLASS = "font-headline-sm text-headline-sm text-on-surface mt-5 mb-2"
TH_CLASS = ("text-left font-semibold text-on-surface px-3 py-2 border-b border-outline-variant/60 "
            "bg-surface-container-low")
TD_CLASS = "px-3 py-2 border-b border-outline-variant/30 align-top"
QUOTE_CLASS = ("my-4 pl-4 border-l-4 border-primary/40 bg-surface-container-low py-3 pr-3 "
               "rounded-r-lg text-on-surface-variant")

WORDS_PER_MINUTE = 220


def _inline(text: str) -> str:
    return INLINE_BOLD.sub(r"<strong>\1</strong>", escape(text))


def _fold(text: str) -> str:
    text = (text or "").lower().replace("đ", "d")
    return "".join(c for c in unicodedata.normalize("NFD", text) if unicodedata.category(c) != "Mn")


def anchor(text: str, used: set) -> str:
    """Sinh id ổn định cho tiêu đề mục, bảo đảm không trùng trong cùng bài."""
    base = re.sub(r"[^a-z0-9]+", "-", _fold(text)).strip("-") or "muc"
    slug, i = base, 1
    while slug in used:
        i += 1
        slug = f"{base}-{i}"
    used.add(slug)
    return slug


def _render_table(rows: list[str]) -> str:
    cells = [[c.strip() for c in r.strip().strip("|").split("|")] for r in rows]
    head = cells[0]
    body = [r for r in cells[1:] if not TABLE_DIVIDER.match("|".join(r) or "|")]
    parts = ['<div class="overflow-x-auto my-4"><table class="w-full text-body-sm border-collapse">',
             "<thead><tr>"]
    parts += [f'<th class="{TH_CLASS}">{_inline(h)}</th>' for h in head]
    parts.append("</tr></thead><tbody>")
    for row in body:
        parts.append("<tr>" + "".join(f'<td class="{TD_CLASS}">{_inline(c)}</td>' for c in row) + "</tr>")
    parts.append("</tbody></table></div>")
    return "".join(parts)


def render_article(text: str) -> tuple[str, list[tuple[str, str]]]:
    """Trả về (HTML, danh sách (id, tiêu đề) của các mục cấp 2)."""
    lines = (text or "").replace("\r\n", "\n").replace("\r", "\n").split("\n")
    out: list[str] = []
    headings: list[tuple[str, str]] = []
    used: set = set()
    list_open: str | None = None
    table_buf: list[str] = []
    para: list[str] = []

    def close_list():
        nonlocal list_open
        if list_open:
            out.append(f"</{list_open}>")
            list_open = None

    def flush_para():
        if para:
            out.append(f'<p class="mb-3 leading-relaxed">{" ".join(_inline(p) for p in para)}</p>')
            para.clear()

    def flush_table():
        if table_buf:
            out.append(_render_table(table_buf))
            table_buf.clear()

    def flush_all():
        flush_para()
        close_list()
        flush_table()

    for raw in lines:
        stripped = raw.strip()

        if not stripped:
            flush_all()
            continue

        if stripped.startswith("|") or (table_buf and stripped.endswith("|")):
            flush_para()
            close_list()
            table_buf.append(stripped)
            continue
        flush_table()

        if stripped.startswith("### "):
            flush_para()
            close_list()
            out.append(f'<h3 class="{H3_CLASS}">{_inline(stripped[4:])}</h3>')
        elif stripped.startswith(("## ", "# ")):
            flush_para()
            close_list()
            title = stripped[3:] if stripped.startswith("## ") else stripped[2:]
            anchor_id = anchor(title, used)
            headings.append((anchor_id, title))
            out.append(f'<h2 id="{anchor_id}" class="{H2_CLASS}">{_inline(title)}</h2>')
        elif stripped.startswith("> "):
            flush_para()
            close_list()
            out.append(f'<blockquote class="{QUOTE_CLASS}">{_inline(stripped[2:])}</blockquote>')
        elif ORDERED.match(stripped):
            flush_para()
            if list_open != "ol":
                close_list()
                out.append('<ol class="list-decimal pl-6 mb-3 flex flex-col gap-1.5">')
                list_open = "ol"
            out.append(f"<li>{_inline(ORDERED.sub('', stripped))}</li>")
        elif stripped.startswith(("- ", "* ", "• ")):
            flush_para()
            if list_open != "ul":
                close_list()
                out.append('<ul class="list-disc pl-6 mb-3 flex flex-col gap-1.5">')
                list_open = "ul"
            out.append(f"<li>{_inline(stripped[2:])}</li>")
        else:
            close_list()
            para.append(stripped)

    flush_all()
    return "".join(out), headings


def outline(text: str) -> list[dict]:
    """Mục lục bài viết, cùng id với tiêu đề do render_article() sinh ra."""
    used: set = set()
    items = []
    for line in (text or "").replace("\r\n", "\n").split("\n"):
        stripped = line.strip()
        if stripped.startswith(("## ", "# ")):
            title = stripped[3:] if stripped.startswith("## ") else stripped[2:]
            items.append({"id": anchor(title, used), "title": title, "num": len(items) + 1})
    return items


def reading_minutes(text: str) -> int:
    """Ước tính thời gian đọc, làm tròn lên, tối thiểu 1 phút."""
    words = len(re.findall(r"\S+", strip_markdown(text or "")))
    return max(1, -(-words // WORDS_PER_MINUTE))


HEADING = re.compile(r"^\s*#{1,3}\s+")
QUOTE = re.compile(r"^\s*>\s?")
BULLET = re.compile(r"^\s*[-*•]\s+")
NUMBERED = re.compile(r"^\s*\d+[.)]\s+")

TABLE_ROW = re.compile(r"^\s*\|.*\|\s*$")
TABLE_DASHES = re.compile(r"^\s*\|?[\s:|-]*\|?\s*$")


def _table_row_to_sentence(header: list[str], row: list[str]) -> str:
    """Đổi một dòng bảng thành câu đọc được, để trợ lý đọc tra được cả số liệu."""
    pairs = []
    for i, cell in enumerate(row):
        if not cell:
            continue
        label = header[i] if i < len(header) else ""
        if i == 0 or not label:
            pairs.append(cell)
        else:
            pairs.append(f"{label}: {cell}")
    return " — ".join(pairs)


def _as_sentence(text: str) -> str:
    """Bổ sung dấu kết câu cho gạch đầu dòng, trích dẫn, dòng bảng.

    Trợ lý đọc dựa vào dấu kết câu để nhận ra câu văn đầy đủ; nếu để mảnh vụn
    không dấu, nó sẽ trích ra những đoạn cụt nghĩa.
    """
    text = text.strip()
    if not text or text.endswith((".", "!", "?", ":", "…", ";")):
        return text
    return text + "."


def strip_markdown(text: str) -> str:
    """Bỏ ký tự định dạng, đổi bảng thành câu, để bộ phân tích đọc được nội dung.

    Mỗi tiêu đề mục, gạch đầu dòng và dòng bảng được tách thành đoạn riêng: nếu
    ghép tất cả lại, câu văn sẽ dính vào nhau và trợ lý đọc trích ra đoạn vô nghĩa.
    """
    lines = (text or "").replace("\r\n", "\n").replace("\r", "\n").split("\n")
    paragraphs: list[str] = []
    current: list[str] = []
    header: list[str] = []

    def flush():
        if current:
            paragraphs.append(" ".join(current))
            current.clear()

    for line in lines:
        stripped = line.strip()
        if not stripped:
            flush()
            header = []
            continue

        if TABLE_ROW.match(stripped):
            flush()
            if TABLE_DASHES.match(stripped):
                continue
            cells = [c.strip() for c in stripped.strip("|").split("|")]
            if not header:
                header = cells
                paragraphs.append(_as_sentence(", ".join(c for c in cells if c)))
                continue
            sentence = _table_row_to_sentence(header, cells)
            if sentence:
                paragraphs.append(_as_sentence(sentence))
            continue
        header = []

        if HEADING.match(stripped):
            flush()
            paragraphs.append(HEADING.sub("", stripped))
        elif QUOTE.match(stripped):
            flush()
            paragraphs.append(_as_sentence(QUOTE.sub("", stripped)))
        elif BULLET.match(stripped):
            flush()
            paragraphs.append(_as_sentence(BULLET.sub("", stripped)))
        elif NUMBERED.match(stripped):
            flush()
            paragraphs.append(_as_sentence(NUMBERED.sub("", stripped)))
        else:
            current.append(stripped.replace("**", "").replace("__", ""))

    flush()
    return re.sub(r"[ \t]{2,}", " ", "\n".join(p for p in paragraphs if p))
