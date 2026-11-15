import datetime as dt

from django.contrib import messages
from django.http import HttpResponse
from django.shortcuts import get_object_or_404, redirect, render
from django.utils import timezone

from accounts.models import AdminDivision
from catalog.models import Crop, PestSpecies, Season
from core.permissions import has_perm, perm_required
from forecasts import analytics as an
from . import builders as b
from . import models as m


@perm_required("report", "view")
def dashboard(request):
    stats = b.dashboard_stats(request.user)
    today = timezone.localdate()
    qs = an.confirmed_records({"date_from": (today - dt.timedelta(days=180)).isoformat()}, request.user)
    series = an.trend(qs, "month")
    by_pest = an.summarize(qs, "pest")
    by_div = an.summarize(qs, "division")
    from alerts.models import Alert
    from forecasts.models import Forecast

    cards = [
        ("Kế hoạch đang thực hiện", stats["plans_running"], "/surveys/plans/"),
        ("Phiếu chờ xác nhận", stats["records_pending"], "/surveys/records/?status=submitted"),
        ("Nhiệm vụ quá hạn", stats["tasks_overdue"], "/surveys/my-tasks/?overdue=1"),
        ("Dự báo chờ xác nhận", stats["forecast_pending"], "/forecasts/forecasts/?status=pending"),
        ("Cảnh báo đang hiệu lực", stats["alerts_live"], "/alerts/alerts/?status=published"),
        ("Theo dõi quá hạn", stats["followup_overdue"], "/alerts/followups/?overdue=1"),
    ]
    return render(request, "reports/dashboard.html", {
        "s": stats, "cards": cards,
        "task_pct": round(stats["tasks_done"] * 100 / stats["tasks_total"]) if stats["tasks_total"] else 0,
        "labels": [r["period"].strftime("%m/%Y") for r in series],
        "rate": [round(r["avg_rate"], 2) if r["avg_rate"] is not None else None for r in series],
        "area": [round(r["affected"], 2) if r["affected"] is not None else None for r in series],
        "pest_labels": [r["label"] for r in by_pest[:8]],
        "pest_values": [round(r["affected"] or 0, 2) for r in by_pest[:8]],
        "div_rows": sorted(by_div, key=lambda r: -(r["avg_rate"] or 0))[:8],
        "alerts": Alert.objects.filter(status__in=["published", "updated"], valid_to__gte=today).select_related("pest")[:5],
        "forecasts": Forecast.objects.filter(status="confirmed", valid_to__gte=today).select_related("pest", "division")[:5],
    })


@perm_required("data", "view")
def summary(request):
    p = request.GET
    params = {k: p[k] for k in ("date_from", "date_to", "crop", "pest", "season", "division") if p.get(k)}
    dim = p.get("dimension") or "division"
    period = p.get("period") or ""
    rows = None
    if p:
        rows = an.summarize(an.confirmed_records(params, request.user), dim if dim in an.DIMENSIONS else None,
                            period if period in an.GROUPINGS else None)
    return render(request, "reports/summary.html", {
        "rows": rows, "p": p, "dims": an.DIMENSIONS, "periods": an.GROUPINGS, "dim": dim, "period": period,
        "crops": Crop.objects.all(), "pests": PestSpecies.objects.all(), "seasons": Season.objects.all(),
        "divisions": AdminDivision.objects.all(), "can_export": has_perm(request.user, "data", "export")})


def _parse_dates(request):
    today = timezone.localdate()
    try:
        d_to = dt.date.fromisoformat(request.GET.get("date_to") or today.isoformat())
        d_from = dt.date.fromisoformat(request.GET.get("date_from") or (d_to - dt.timedelta(days=30)).isoformat())
    except ValueError:
        return None, None
    return d_from, d_to


@perm_required("report", "view")
def report_list(request):
    return render(request, "reports/report_list.html", {
        "templates": m.ReportTemplate.objects.filter(is_active=True),
        "generated": m.GeneratedReport.objects.select_related("template", "created_by")[:20],
        "can_export": has_perm(request.user, "report", "export")})


@perm_required("report", "view")
def report_view(request, code):
    tpl = get_object_or_404(m.ReportTemplate, code=code, is_active=True)
    d_from, d_to = _parse_dates(request)
    if d_from is None:
        messages.error(request, "Ngày không hợp lệ.")
        return redirect("reports:list")
    rep = b.build(tpl.kind, d_from, d_to, request.user, {"crop": request.GET.get("crop"), "pest": request.GET.get("pest"),
                                                         "division": request.GET.get("division")})
    return render(request, "reports/report_view.html", {
        "tpl": tpl, "rep": rep, "d_from": d_from, "d_to": d_to, "crops": Crop.objects.all(),
        "pests": PestSpecies.objects.all(), "divisions": AdminDivision.objects.all(),
        "can_export": has_perm(request.user, "report", "export"), "p": request.GET})


@perm_required("report", "export")
def report_export(request, code, fmt):
    tpl = get_object_or_404(m.ReportTemplate, code=code, is_active=True)
    d_from, d_to = _parse_dates(request)
    if d_from is None or fmt not in ("xlsx", "pdf"):
        messages.error(request, "Tham số kết xuất không hợp lệ.")
        return redirect("reports:list")
    rep = b.build(tpl.kind, d_from, d_to, request.user, {"crop": request.GET.get("crop"), "pest": request.GET.get("pest"),
                                                         "division": request.GET.get("division")})
    content = b.to_xlsx(rep) if fmt == "xlsx" else b.to_pdf(rep)
    from core.audit import write_log

    write_log("report_export", note=f"{tpl.code} {fmt} {d_from}..{d_to}", user=request.user)
    ctype = ("application/vnd.openxmlformats-officedocument.spreadsheetml.sheet" if fmt == "xlsx" else "application/pdf")
    resp = HttpResponse(content, content_type=ctype)
    resp["Content-Disposition"] = f'attachment; filename="{tpl.code}_{d_from:%Y%m%d}_{d_to:%Y%m%d}.{fmt}"'
    return resp


@perm_required("data", "export")
def summary_export(request):
    from openpyxl import Workbook

    p = request.GET
    params = {k: p[k] for k in ("date_from", "date_to", "crop", "pest", "season", "division") if p.get(k)}
    dim = p.get("dimension") if p.get("dimension") in an.DIMENSIONS else "division"
    period = p.get("period") if p.get("period") in an.GROUPINGS else None
    rows = an.summarize(an.confirmed_records(params, request.user), dim, period)
    wb = Workbook()
    ws = wb.active
    ws.append(["Kỳ" if period else "", an.DIMENSIONS[dim][0], "Số phiếu", "Số điểm", "DT điều tra (ha)", "DT bị hại (ha)",
               "Mật độ TB", "Tỷ lệ hại TB (%)", "Tỷ lệ hại cao nhất (%)"])
    for r in rows:
        label = r.get("label", "")
        label = "'" + label if isinstance(label, str) and label[:1] in "=+-@" else label
        ws.append([r["period"].strftime("%d/%m/%Y") if period and r.get("period") else "", label, r["records"], r["points"],
                   r["surveyed"], r["affected"], r["avg_density"], r["avg_rate"], r["max_rate"]])
    import io

    buf = io.BytesIO()
    wb.save(buf)
    resp = HttpResponse(buf.getvalue(), content_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet")
    resp["Content-Disposition"] = 'attachment; filename="tong_hop_du_lieu.xlsx"'
    return resp
