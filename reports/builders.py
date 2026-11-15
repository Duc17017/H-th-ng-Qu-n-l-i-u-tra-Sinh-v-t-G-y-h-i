"""Dựng nội dung báo cáo dạng bảng (tiêu đề + cột + dòng) rồi kết xuất Excel/PDF."""
import io
import os

from django.conf import settings
from django.db.models import Count, Sum
from django.utils import timezone

from alerts.models import Alert, FollowUpTask
from forecasts.analytics import confirmed_records, summarize
from forecasts.models import Forecast
from surveys.models import SurveyPlan, SurveyRecord, SurveyTask


def _f(v, d=2):
    return "" if v is None else round(float(v), d)


def build(kind, date_from, date_to, user=None, extra=None):
    """Trả về dict: title, headers, rows, summary(list[(label, value)])."""
    extra = extra or {}
    params = {"date_from": date_from.isoformat(), "date_to": date_to.isoformat(), **{k: v for k, v in extra.items() if v}}
    period = f"{date_from:%d/%m/%Y} - {date_to:%d/%m/%Y}"
    if kind == "progress":
        plans = SurveyPlan.objects.filter(start_date__lte=date_to, end_date__gte=date_from).select_related("crop", "division")
        if user is not None:
            from core.permissions import scope_qs

            plans = scope_qs(user, plans, "division")
        rows, tot, done_all = [], 0, 0
        for p in plans:
            done, total, pct = p.progress()
            overdue = p.tasks.exclude(status="done").filter(due_date__lt=timezone.localdate()).count()
            rows.append([p.code, p.name, p.crop.name, p.division.name, p.get_status_display(), total, done, f"{pct}%", overdue])
            tot += total
            done_all += done
        return {"title": f"Tiến độ thực hiện kế hoạch điều tra ({period})",
                "headers": ["Mã", "Kế hoạch", "Cây trồng", "Địa bàn", "Trạng thái", "Nhiệm vụ", "Hoàn thành", "Tiến độ", "Quá hạn"],
                "rows": rows, "summary": [("Số kế hoạch", len(rows)), ("Tổng nhiệm vụ", tot), ("Đã hoàn thành", done_all)]}
    if kind in ("occurrence", "area"):
        qs = confirmed_records(params, user)
        dim = "division" if kind == "area" else "pest"
        data = summarize(qs, dim)
        rows = [[r["label"], r["records"], r["points"], _f(r["surveyed"]), _f(r["affected"]), _f(r["avg_density"]),
                 _f(r["avg_rate"]), _f(r["max_rate"])] for r in data]
        head = "Địa bàn" if kind == "area" else "Sinh vật gây hại"
        total = qs.aggregate(n=Count("id"), pts=Count("point", distinct=True), s=Sum("surveyed_area"), a=Sum("affected_area"))
        return {"title": ("Diện tích bị ảnh hưởng theo địa bàn" if kind == "area" else "Tình hình phát sinh, mức độ gây hại") + f" ({period})",
                "headers": [head, "Số phiếu", "Số điểm", "DT điều tra (ha)", "DT bị hại (ha)", "Mật độ TB", "Tỷ lệ hại TB (%)", "Tỷ lệ hại cao nhất (%)"],
                "rows": rows, "summary": [("Số phiếu đã xác nhận", total["n"]), ("Số điểm điều tra", total["pts"]),
                                          ("Diện tích điều tra (ha)", _f(total["s"])), ("Diện tích bị hại (ha)", _f(total["a"]))]}
    if kind == "forecast":
        qs = Forecast.objects.filter(valid_from__lte=date_to, valid_to__gte=date_from).select_related("pest", "crop", "division")
        rows = [[x.title, x.pest.name, x.crop.name, x.division.name, f"{x.valid_from:%d/%m/%Y} - {x.valid_to:%d/%m/%Y}",
                 x.get_risk_level_display(), x.get_status_display(), x.get_actual_level_display() if x.actual_level else "",
                 x.evaluation_note] for x in qs]
        return {"title": f"Nhận định dự tính, dự báo ({period})",
                "headers": ["Nhận định", "Sinh vật", "Cây trồng", "Địa bàn", "Thời gian", "Nguy cơ dự báo", "Trạng thái", "Thực tế", "Đánh giá"],
                "rows": rows, "summary": [("Số nhận định", len(rows)), ("Đã xác nhận", sum(1 for x in qs if x.status == "confirmed"))]}
    if kind == "alert":
        qs = Alert.objects.filter(valid_from__lte=date_to, valid_to__gte=date_from).select_related("pest", "crop")
        rows = []
        for a in qs:
            fu = a.followups.all()
            total, done = fu.count(), fu.filter(status="done").count()
            rows.append([a.code, a.title, a.pest.name, a.crop.name, a.get_risk_level_display(), a.get_status_display(),
                         a.published_at.strftime("%d/%m/%Y") if a.published_at else "", total, done])
        return {"title": f"Bản tin cảnh báo và kết quả theo dõi ({period})",
                "headers": ["Số hiệu", "Tiêu đề", "Sinh vật", "Cây trồng", "Nguy cơ", "Trạng thái", "Phát hành", "NV theo dõi", "Hoàn thành"],
                "rows": rows, "summary": [("Số bản tin", len(rows))]}
    raise ValueError("Loại báo cáo không hợp lệ")


def to_xlsx(rep):
    from openpyxl import Workbook
    from openpyxl.styles import Alignment, Font, PatternFill

    wb = Workbook()
    ws = wb.active
    ws.title = "Bao_cao"
    ws.append([rep["title"]])
    ws["A1"].font = Font(bold=True, size=14)
    ws.append([f"Ngày lập: {timezone.localtime():%d/%m/%Y %H:%M}"])
    for label, val in rep["summary"]:
        ws.append([label, val])
    ws.append([])
    ws.append(rep["headers"])
    hr = ws.max_row
    for c in ws[hr]:
        c.font = Font(bold=True, color="FFFFFF")
        c.fill = PatternFill("solid", fgColor="2E7D32")
        c.alignment = Alignment(wrap_text=True, vertical="center")
    for row in rep["rows"]:
        # tránh chèn công thức từ dữ liệu người dùng nhập
        ws.append([("'" + v if isinstance(v, str) and v[:1] in "=+-@" else v) for v in row])
    for i, h in enumerate(rep["headers"], start=1):
        ws.column_dimensions[ws.cell(row=hr, column=i).column_letter].width = max(14, min(40, len(str(h)) + 6))
    buf = io.BytesIO()
    wb.save(buf)
    return buf.getvalue()


def _find_font():
    cands = [settings.PDF_FONT_PATH, r"C:\Windows\Fonts\arial.ttf", r"C:\Windows\Fonts\tahoma.ttf",
             "/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf", "/Library/Fonts/Arial.ttf"]
    for p in cands:
        if p and os.path.exists(p):
            return p
    return None


def to_pdf(rep):
    from reportlab.lib import colors
    from reportlab.lib.pagesizes import A4, landscape
    from reportlab.lib.styles import ParagraphStyle
    from reportlab.lib.units import cm
    from reportlab.pdfbase import pdfmetrics
    from reportlab.pdfbase.ttfonts import TTFont
    from reportlab.platypus import Paragraph, SimpleDocTemplate, Spacer, Table, TableStyle

    font = "Helvetica"
    path = _find_font()
    if path:
        try:
            pdfmetrics.registerFont(TTFont("VNFont", path))
            font = "VNFont"
        except Exception:
            font = "Helvetica"
    buf = io.BytesIO()
    doc = SimpleDocTemplate(buf, pagesize=landscape(A4), leftMargin=1.2 * cm, rightMargin=1.2 * cm,
                            topMargin=1.2 * cm, bottomMargin=1.2 * cm, title=rep["title"])
    title = ParagraphStyle("t", fontName=font, fontSize=14, leading=18, spaceAfter=6)
    body = ParagraphStyle("b", fontName=font, fontSize=8, leading=10)
    story = [Paragraph(_esc(rep["title"]), title),
             Paragraph(f"Ngày lập: {timezone.localtime():%d/%m/%Y %H:%M}", body), Spacer(1, 6)]
    for label, val in rep["summary"]:
        story.append(Paragraph(_esc(f"{label}: {val}"), body))
    story.append(Spacer(1, 8))
    data = [[Paragraph(_esc(h), body) for h in rep["headers"]]] + \
           [[Paragraph(_esc(str(c)), body) for c in row] for row in rep["rows"]]
    t = Table(data, repeatRows=1)
    t.setStyle(TableStyle([("BACKGROUND", (0, 0), (-1, 0), colors.HexColor("#E8F5E9")),
                           ("GRID", (0, 0), (-1, -1), 0.4, colors.grey), ("VALIGN", (0, 0), (-1, -1), "TOP")]))
    story.append(t)
    if font == "Helvetica":
        story.append(Spacer(1, 8))
        story.append(Paragraph("Lưu ý: chưa tìm thấy font Unicode, một số ký tự tiếng Việt có thể hiển thị sai. Đặt PDF_FONT_PATH trong .env.", body))
    doc.build(story)
    return buf.getvalue()


def _esc(s):
    return str(s).replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")


def dashboard_stats(user):
    from core.permissions import scope_qs

    today = timezone.localdate()
    month_start = today.replace(day=1)
    tasks = scope_qs(user, SurveyTask.objects.all(), "point__division")
    records = scope_qs(user, SurveyRecord.objects.all(), "point__division")
    alerts = Alert.objects.filter(status__in=["published", "updated"], valid_from__lte=today, valid_to__gte=today)
    confirmed = confirmed_records({"date_from": month_start.isoformat()}, user)
    agg = confirmed.aggregate(s=Sum("surveyed_area"), a=Sum("affected_area"), pts=Count("point", distinct=True))
    return {
        "plans_running": scope_qs(user, SurveyPlan.objects.filter(status__in=["approved", "running"]), "division").count(),
        "tasks_total": tasks.count(),
        "tasks_done": tasks.filter(status="done").count(),
        "tasks_overdue": tasks.exclude(status="done").filter(due_date__lt=today).count(),
        "records_pending": records.filter(status="submitted").count(),
        "records_revision": records.filter(status="revision").count(),
        "records_month": confirmed.count(),
        "points_month": agg["pts"] or 0,
        "surveyed_month": agg["s"] or 0,
        "affected_month": agg["a"] or 0,
        "forecast_pending": Forecast.objects.filter(status="pending").count(),
        "alerts_live": alerts.count(),
        "alerts_pending": Alert.objects.filter(status="pending").count(),
        "followup_open": FollowUpTask.objects.exclude(status="done").count(),
        "followup_overdue": FollowUpTask.objects.exclude(status="done").filter(due_date__lt=today).count(),
    }
