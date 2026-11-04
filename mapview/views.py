import json

from django.contrib import messages
from django.http import HttpResponse, JsonResponse
from django.shortcuts import redirect, render
from django.utils import timezone
from django.views.decorators.http import require_POST

from accounts.models import AdminDivision
from catalog.models import Crop, DamageLevel, PestSpecies
from core.permissions import has_perm, perm_required, scope_qs
from forecasts.analytics import confirmed_records
from surveys.models import SurveyPoint, SurveyRecord, SurveyRoute
from .models import ExternalLayer


def _filters(request):
    g = request.GET
    return {k: g.get(k) for k in ("date_from", "date_to", "crop", "pest", "division") if g.get(k)}


def _level(rate):
    if rate is None:
        return "none"
    for lo, name in ((50, "very_high"), (30, "high"), (10, "medium")):
        if rate >= lo:
            return name
    return "low"


@perm_required("map", "view")
def map_page(request):
    layers = ExternalLayer.objects.filter(is_active=True)
    return render(request, "mapview/map.html", {
        "crops": Crop.objects.all(), "pests": PestSpecies.objects.all(), "divisions": AdminDivision.objects.all(),
        "levels": DamageLevel.objects.all(),
        "ext_layers": json.dumps([{"name": l.name, "kind": l.kind, "url": l.url, "layers": l.layers,
                                   "attribution": l.attribution, "base": l.is_base} for l in layers], ensure_ascii=False),
        "can_export": has_perm(request.user, "map", "export"),
        "can_import": has_perm(request.user, "map", "create"),
    })


@perm_required("map", "view")
def points_geojson(request):
    """Điểm điều tra kèm kết quả mới nhất theo bộ lọc; chỉ dùng phiếu đã xác nhận để tính mức độ."""
    f = _filters(request)
    recs = confirmed_records(f, request.user).select_related("point", "pest", "crop", "damage_level")
    latest = {}
    for r in recs.order_by("survey_date"):
        latest[r.point_id] = r
    points = scope_qs(request.user, SurveyPoint.objects.filter(is_active=True, latitude__isnull=False), "division")
    if f.get("crop"):
        points = points.filter(pk__in=latest.keys()) if latest else points.none()
    elif f.get("pest") or f.get("date_from") or f.get("date_to"):
        points = points.filter(pk__in=latest.keys())
    if f.get("division"):
        d = AdminDivision.objects.filter(pk=f["division"]).first()
        if d:
            points = points.filter(division_id__in=d.descendant_ids())
    feats = []
    for p in points.select_related("division")[:5000]:
        r = latest.get(p.pk)
        props = {"id": p.pk, "code": p.code, "name": p.name, "division": p.division.name,
                 "area_ha": p.area_ha, "level": _level(r.damage_rate) if r else "none"}
        if r:
            props.update(record_id=r.pk, date=timezone.localtime(r.survey_date).strftime("%d/%m/%Y"),
                         pest=r.pest.name, crop=r.crop.name, rate=r.damage_rate, density=r.density,
                         affected=r.affected_area,
                         level_name=r.damage_level.name if r.damage_level else "")
        feats.append({"type": "Feature", "properties": props,
                      "geometry": {"type": "Point", "coordinates": [p.longitude, p.latitude]}})
    return JsonResponse({"type": "FeatureCollection", "features": feats})


@perm_required("map", "view")
def routes_geojson(request):
    """Tuyến điều tra dạng đường nối các điểm theo mã điểm."""
    routes = SurveyRoute.objects.select_related("plan").prefetch_related("points")
    routes = scope_qs(request.user, routes, "plan__division")
    feats = []
    for r in routes[:500]:
        pts = sorted([p for p in r.points.all() if p.latitude is not None], key=lambda p: p.code)
        if len(pts) >= 2:
            feats.append({"type": "Feature", "properties": {"id": r.pk, "name": r.name, "plan": r.plan.code},
                          "geometry": {"type": "LineString", "coordinates": [[p.longitude, p.latitude] for p in pts]}})
    return JsonResponse({"type": "FeatureCollection", "features": feats})


@perm_required("map", "view")
def point_detail(request, pk):
    p = scope_qs(request.user, SurveyPoint.objects.select_related("division", "route"), "division").filter(pk=pk).first()
    if not p:
        return JsonResponse({"error": "Không tìm thấy"}, status=404)
    recs = confirmed_records({}, request.user).filter(point=p).select_related("pest", "crop", "damage_level").order_by("-survey_date")[:30]
    hist = [{"id": r.pk, "date": timezone.localtime(r.survey_date).strftime("%d/%m/%Y"), "pest": r.pest.name,
             "crop": r.crop.name, "rate": r.damage_rate, "density": r.density, "affected": r.affected_area,
             "comment": r.comment, "images": [a.file.url for a in r.attachments.all() if a.is_image][:4]} for r in recs]
    return JsonResponse({"point": {"id": p.pk, "code": p.code, "name": p.name, "division": p.division.full_name,
                                   "address": p.address, "lat": p.latitude, "lng": p.longitude}, "history": hist})


@perm_required("map", "view")
def timeline_api(request):
    """Biến động theo thời gian: tỷ lệ hại TB và diện tích hại theo tháng cho vùng đang lọc."""
    from forecasts.analytics import trend

    data = trend(confirmed_records(_filters(request), request.user), "month")
    return JsonResponse({"series": [{"period": r["period"].strftime("%m/%Y"),
                                     "rate": round(r["avg_rate"], 2) if r["avg_rate"] is not None else None,
                                     "affected": round(r["affected"], 2) if r["affected"] is not None else None,
                                     "records": r["records"]} for r in data]})


@perm_required("map", "export")
def export_geojson(request):
    resp = points_geojson(request)
    out = HttpResponse(resp.content, content_type="application/geo+json")
    out["Content-Disposition"] = 'attachment; filename="diem_dieu_tra.geojson"'
    return out


@require_POST
@perm_required("map", "create")
def import_geojson(request):
    """Nhập điểm điều tra từ GeoJSON: cần properties.code, properties.name, properties.division_code."""
    f = request.FILES.get("file")
    if not f or f.size > 5 * 1024 * 1024:
        messages.error(request, "Hãy chọn tệp GeoJSON không quá 5 MB.")
        return redirect("mapview:map")
    try:
        data = json.load(f)
        feats = data["features"]
        if len(feats) > 5000:
            raise ValueError("Quá 5000 đối tượng")
    except (ValueError, KeyError, TypeError):
        messages.error(request, "Tệp GeoJSON không hợp lệ.")
        return redirect("mapview:map")
    divs = {d.code: d for d in AdminDivision.objects.all()}
    ok = bad = 0
    for ft in feats:
        try:
            props, geom = ft["properties"], ft["geometry"]
            if geom["type"] != "Point":
                raise ValueError
            lng, lat = float(geom["coordinates"][0]), float(geom["coordinates"][1])
            div = divs[str(props["division_code"])]
            if not (-90 <= lat <= 90 and -180 <= lng <= 180):
                raise ValueError
            SurveyPoint.objects.update_or_create(code=str(props["code"])[:30],
                                                 defaults={"name": str(props["name"])[:200], "division": div,
                                                           "latitude": lat, "longitude": lng})
            ok += 1
        except (KeyError, ValueError, TypeError, IndexError):
            bad += 1
    messages.success(request, f"Đã nhập {ok} điểm; bỏ qua {bad} đối tượng không hợp lệ.")
    return redirect("mapview:map")
