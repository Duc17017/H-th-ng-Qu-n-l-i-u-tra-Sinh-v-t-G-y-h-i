"""Phân tích dữ liệu điều tra: tổng hợp, so sánh kỳ, xu hướng. Chỉ dùng phiếu đã xác nhận."""
from django.db.models import Avg, Count, Max, Sum
from django.db.models.functions import TruncDay, TruncMonth, TruncWeek

from surveys.models import SurveyRecord

GROUPINGS = {
    "day": ("Ngày", TruncDay),
    "week": ("Tuần", TruncWeek),
    "month": ("Tháng", TruncMonth),
}
DIMENSIONS = {
    "division": ("Địa bàn", "point__division__name"),
    "crop": ("Cây trồng", "crop__name"),
    "pest": ("Sinh vật gây hại", "pest__name"),
    "season": ("Mùa vụ", "season__name"),
    "unit": ("Đơn vị", "unit__name"),
}


def confirmed_records(params, user=None):
    """Bộ lọc dùng chung cho thống kê. params: dict-like (GET)."""
    qs = SurveyRecord.objects.filter(status="confirmed")
    if user is not None:
        from core.permissions import scope_qs

        qs = scope_qs(user, qs, "point__division")
    if params.get("date_from"):
        qs = qs.filter(survey_date__date__gte=params["date_from"])
    if params.get("date_to"):
        qs = qs.filter(survey_date__date__lte=params["date_to"])
    if params.get("crop"):
        qs = qs.filter(crop_id=params["crop"])
    if params.get("pest"):
        qs = qs.filter(pest_id=params["pest"])
    if params.get("season"):
        qs = qs.filter(season_id=params["season"])
    if params.get("division"):
        from accounts.models import AdminDivision

        d = AdminDivision.objects.filter(pk=params["division"]).first()
        if d:
            qs = qs.filter(point__division_id__in=d.descendant_ids())
    return qs


AGG = dict(
    records=Count("id"),
    points=Count("point", distinct=True),
    surveyed=Sum("surveyed_area"),
    affected=Sum("affected_area"),
    avg_density=Avg("density"),
    avg_rate=Avg("damage_rate"),
    max_rate=Max("damage_rate"),
)


def summarize(qs, dimension=None, period=None):
    """Tổng hợp theo chiều (địa bàn/cây trồng/đối tượng...) và/hoặc theo kỳ (ngày/tuần/tháng)."""
    values, order = [], []
    if period in GROUPINGS:
        qs = qs.annotate(period=GROUPINGS[period][1]("survey_date"))
        values.append("period")
        order.append("period")
    if dimension in DIMENSIONS:
        values.append(DIMENSIONS[dimension][1])
        order.append(DIMENSIONS[dimension][1])
    if not values:
        row = qs.aggregate(**AGG)
        return [row]
    rows = list(qs.values(*values).annotate(**AGG).order_by(*order))
    for r in rows:
        if dimension in DIMENSIONS:
            r["label"] = r.get(DIMENSIONS[dimension][1]) or "(chưa xác định)"
    return rows


def compare_periods(params, user, a_from, a_to, b_from, b_to, dimension="division"):
    """So sánh hai kỳ điều tra theo chiều đã chọn."""
    base = {k: v for k, v in params.items() if k not in ("date_from", "date_to")}
    a = summarize(confirmed_records({**base, "date_from": a_from, "date_to": a_to}, user), dimension)
    b = summarize(confirmed_records({**base, "date_from": b_from, "date_to": b_to}, user), dimension)
    key = DIMENSIONS[dimension][1]
    amap = {r[key]: r for r in a}
    bmap = {r[key]: r for r in b}
    out = []
    for name in sorted(set(amap) | set(bmap), key=lambda x: str(x)):
        ra, rb = amap.get(name), bmap.get(name)
        va = ra["avg_rate"] if ra else None
        vb = rb["avg_rate"] if rb else None
        out.append({
            "label": name or "(chưa xác định)",
            "a_rate": va, "b_rate": vb,
            "delta": (vb - va) if va is not None and vb is not None else None,
            "a_affected": ra["affected"] if ra else None, "b_affected": rb["affected"] if rb else None,
            "a_records": ra["records"] if ra else 0, "b_records": rb["records"] if rb else 0,
        })
    return out


def trend(qs, period="week"):
    """Chuỗi thời gian: tỷ lệ hại TB, mật độ TB, diện tích hại theo kỳ."""
    rows = summarize(qs, None, period)
    return [{"period": r["period"], "avg_rate": r["avg_rate"], "avg_density": r["avg_density"],
             "affected": r["affected"], "records": r["records"]} for r in rows]


def trend_direction(series, key="avg_rate"):
    """Hồi quy tuyến tính đơn giản trên chuỗi, trả về (hướng, độ dốc)."""
    pts = [(i, float(r[key])) for i, r in enumerate(series) if r.get(key) is not None]
    n = len(pts)
    if n < 3:
        return "Chưa đủ dữ liệu", None
    sx = sum(x for x, _ in pts)
    sy = sum(y for _, y in pts)
    sxx = sum(x * x for x, _ in pts)
    sxy = sum(x * y for x, y in pts)
    den = n * sxx - sx * sx
    if den == 0:
        return "Ổn định", 0.0
    slope = (n * sxy - sx * sy) / den
    mean = sy / n or 1
    rel = slope / mean if mean else 0
    if rel > 0.05:
        return "Có xu hướng tăng", slope
    if rel < -0.05:
        return "Có xu hướng giảm", slope
    return "Ổn định", slope
