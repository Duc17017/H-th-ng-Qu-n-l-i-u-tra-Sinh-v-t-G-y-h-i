"""Gợi ý nhận định tự động từ dữ liệu điều tra đã xác nhận + ngưỡng + thời tiết.
Kết quả luôn ở trạng thái dự thảo và phải được cán bộ chuyên môn xác nhận."""
import datetime as dt

from django.db import transaction
from django.db.models import Avg, Max, Sum
from django.utils import timezone

from core.audit import write_log
from core.notify import notify, users_with_perm
from surveys.models import SurveyRecord
from . import models as m

LEVEL_ORDER = ["low", "medium", "high", "very_high"]


class ForecastError(Exception):
    pass


def metric_value(qs, metric):
    field = {"damage_rate": "damage_rate", "density": "density", "affected_area": "affected_area"}[metric]
    if metric == "affected_area":
        return qs.aggregate(v=Sum(field))["v"]
    return qs.aggregate(v=Avg(field))["v"]


def suggest(threshold, division, user, lookback_days=30):
    """Tạo Forecast dự thảo từ dữ liệu N ngày gần nhất. Lưu đầy đủ nguồn dữ liệu và tiêu chí."""
    if not threshold.is_active:
        raise ForecastError("Tiêu chí này đã ngừng áp dụng.")
    today = timezone.localdate()
    start = today - dt.timedelta(days=lookback_days)
    ids = division.descendant_ids()
    qs = SurveyRecord.objects.filter(status="confirmed", pest=threshold.pest, point__division_id__in=ids,
                                     survey_date__date__gte=start, survey_date__date__lte=today)
    if threshold.crop_id:
        qs = qs.filter(crop=threshold.crop)
    if threshold.stage_id:
        qs = qs.filter(stage=threshold.stage)
    n = qs.count()
    if n == 0:
        raise ForecastError("Không có phiếu điều tra đã xác nhận trong khoảng thời gian phân tích.")
    value = metric_value(qs, threshold.metric)
    level = threshold.evaluate(value) or "low"

    weather = m.WeatherData.objects.filter(division_id__in=ids, date__gte=start, date__lte=today)
    wagg = weather.aggregate(t=Avg("temp_avg"), h=Avg("humidity"), r=Sum("rainfall"), last=Max("updated_at"))
    weather_note, favorable = "", None
    if weather.exists():
        favorable = True
        if threshold.temp_min is not None and wagg["t"] is not None and wagg["t"] < threshold.temp_min:
            favorable = False
        if threshold.temp_max is not None and wagg["t"] is not None and wagg["t"] > threshold.temp_max:
            favorable = False
        if threshold.humidity_min is not None and wagg["h"] is not None and wagg["h"] < threshold.humidity_min:
            favorable = False
        weather_note = (f" Thời tiết {lookback_days} ngày gần nhất: nhiệt độ TB {wagg['t']:.1f}°C"
                        if wagg["t"] is not None else "") + \
                       (f", độ ẩm TB {wagg['h']:.0f}%" if wagg["h"] is not None else "") + \
                       (f", tổng mưa {wagg['r']:.0f} mm" if wagg["r"] is not None else "") + \
                       (". Điều kiện thời tiết thuận lợi cho sinh vật gây hại." if favorable else ". Điều kiện thời tiết chưa thật thuận lợi.")
        if favorable and level in ("medium", "high"):
            level = LEVEL_ORDER[LEVEL_ORDER.index(level) + 1]
    metric_label = dict(m.Threshold.METRICS)[threshold.metric]
    basis = (f"Dựa trên {n} phiếu điều tra đã xác nhận từ {start:%d/%m/%Y} đến {today:%d/%m/%Y} "
             f"tại {division.name}. {metric_label}: {value:.2f}. "
             f"Tiêu chí: {threshold.name} (trung bình ≥ {threshold.medium_from}, cao ≥ {threshold.high_from}, "
             f"rất cao ≥ {threshold.very_high_from}).{weather_note}")
    meta = {
        "method": "threshold_rule", "records_used": n, "record_ids": list(qs.values_list("id", flat=True)[:500]),
        "window": [start.isoformat(), today.isoformat()], "metric": threshold.metric, "metric_value": value,
        "threshold_id": threshold.pk, "weather_used": weather.exists(),
        "weather_last_update": wagg["last"].isoformat() if wagg["last"] else None,
        "data_as_of": timezone.now().isoformat(),
    }
    fc = m.Forecast.objects.create(
        title=f"Nhận định {threshold.pest.name} - {division.name}",
        pest=threshold.pest, crop=threshold.crop or qs.first().crop, division=division, stage=threshold.stage,
        valid_from=today, valid_to=today + dt.timedelta(days=14), risk_level=level,
        expected_rate=qs.aggregate(v=Avg("damage_rate"))["v"], expected_area=qs.aggregate(v=Sum("affected_area"))["v"],
        basis=basis, recommendation="", threshold=threshold, origin="auto", analysis_meta=meta,
        status="draft", created_by=user)
    write_log("forecast_suggest", fc, note="Gợi ý tự động, chờ chuyên môn xác nhận", user=user)
    return fc


@transaction.atomic
def transition(fc, action, user, note=""):
    flows = {"submit": ({"draft", "rejected"}, "pending"), "confirm": ({"pending"}, "confirmed"),
             "reject": ({"pending"}, "rejected")}
    allowed, to = flows[action]
    if fc.status not in allowed:
        raise ForecastError("Trạng thái hiện tại không cho phép thao tác này.")
    if action == "submit" and (not fc.basis.strip() or not fc.recommendation.strip()):
        raise ForecastError("Cần có căn cứ dữ liệu và khuyến nghị chuyên môn trước khi trình xác nhận.")
    if action == "reject" and not note.strip():
        raise ForecastError("Cần nhập lý do không thông qua.")
    old = fc.status
    fc.status = to
    if action == "confirm":
        fc.confirmed_by, fc.confirmed_at = user, timezone.now()
    if note:
        fc.review_note = note
    fc.save()
    write_log(f"forecast_{action}", fc, note=note, changes={"status": [old, to]}, user=user)
    if action == "submit":
        notify([u for u in users_with_perm("forecast", "confirm", fc.division.descendant_ids()) if u != user],
               "Nhận định dự báo chờ xác nhận", fc.title, f"/forecasts/forecasts/{fc.pk}/")
    elif fc.created_by and fc.created_by != user:
        notify([fc.created_by], "Nhận định dự báo đã được xử lý", f"{fc.title}: {fc.get_status_display()}",
               f"/forecasts/forecasts/{fc.pk}/")


def evaluate_actual(fc, user):
    """Đối chiếu dự báo với số liệu thực tế đã xác nhận trong thời gian dự báo."""
    ids = fc.division.descendant_ids()
    qs = SurveyRecord.objects.filter(status="confirmed", pest=fc.pest, crop=fc.crop, point__division_id__in=ids,
                                     survey_date__date__gte=fc.valid_from, survey_date__date__lte=fc.valid_to)
    if not qs.exists():
        raise ForecastError("Chưa có phiếu điều tra đã xác nhận trong thời gian dự báo để đối chiếu.")
    agg = qs.aggregate(r=Avg("damage_rate"), a=Sum("affected_area"), d=Avg("density"))
    fc.actual_rate, fc.actual_area = agg["r"], agg["a"]
    if fc.threshold_id:
        th = fc.threshold
        val = {"damage_rate": agg["r"], "density": agg["d"], "affected_area": agg["a"]}[th.metric]
        fc.actual_level = th.evaluate(val) or ""
    if fc.actual_level:
        diff = LEVEL_ORDER.index(fc.actual_level) - LEVEL_ORDER.index(fc.risk_level)
        verdict = "Dự báo sát thực tế" if diff == 0 else ("Thực tế nặng hơn dự báo" if diff > 0 else "Thực tế nhẹ hơn dự báo")
    else:
        verdict = "Đã cập nhật số liệu thực tế; cần cán bộ đánh giá mức độ"
    fc.evaluation_note = f"{verdict}. Dựa trên {qs.count()} phiếu điều tra đã xác nhận."
    fc.evaluated_at = timezone.now()
    fc.save()
    write_log("forecast_evaluate", fc, note=fc.evaluation_note, user=user)
    return fc
