"""Định dạng chung cho file Excel xuất ra: tự căn cột theo nội dung, tiêu đề đậm, cố định hàng tiêu đề, bộ lọc."""
import datetime as dt

from openpyxl.styles import Alignment, Border, Font, PatternFill, Side
from openpyxl.utils import get_column_letter

HEADER_FILL = PatternFill("solid", fgColor="2E7D32")
HEADER_FONT = Font(bold=True, color="FFFFFF")
THIN = Side(style="thin", color="BFBFBF")
BORDER = Border(left=THIN, right=THIN, top=THIN, bottom=THIN)
MIN_WIDTH, MAX_WIDTH = 10, 60


def _text_len(value):
    if value is None:
        return 0
    if isinstance(value, (dt.datetime, dt.date)):
        return 16
    if isinstance(value, float):
        value = f"{value:.2f}"
    # Dòng dài nhất quyết định độ rộng khi ô có xuống dòng
    return max((len(line) for line in str(value).splitlines()), default=0)


def format_table(ws, header_row=1, first_data_row=None, freeze=True, filter_=True):
    """Định dạng bảng bắt đầu từ `header_row` đến hết dữ liệu.

    - Cột rộng vừa nội dung dài nhất (từ `first_data_row` trở xuống), giới hạn 10 đến 60 ký tự.
    - Ô dài hơn mức tối đa tự xuống dòng thay vì bị cắt.
    - Hàng tiêu đề tô xanh, chữ đậm; cố định khi cuộn; có nút lọc.
    """
    last_row, last_col = ws.max_row, ws.max_column
    if last_row < header_row or last_col < 1:
        return
    start = first_data_row or header_row
    for col in range(1, last_col + 1):
        longest = max((_text_len(ws.cell(row=r, column=col).value) for r in range(start, last_row + 1)), default=0)
        ws.column_dimensions[get_column_letter(col)].width = max(MIN_WIDTH, min(MAX_WIDTH, longest + 3))
    for col in range(1, last_col + 1):
        head = ws.cell(row=header_row, column=col)
        head.font, head.fill, head.border = HEADER_FONT, HEADER_FILL, BORDER
        head.alignment = Alignment(wrap_text=True, vertical="center", horizontal="center")
    for r in range(header_row + 1, last_row + 1):
        for col in range(1, last_col + 1):
            cell = ws.cell(row=r, column=col)
            cell.border = BORDER
            cell.alignment = Alignment(wrap_text=True, vertical="top")
    ws.row_dimensions[header_row].height = 30
    if freeze:
        ws.freeze_panes = ws.cell(row=header_row + 1, column=1)
    if filter_ and last_row > header_row:
        ws.auto_filter.ref = f"A{header_row}:{get_column_letter(last_col)}{last_row}"
