from django.contrib import messages
from django.core.exceptions import PermissionDenied
from django.shortcuts import get_object_or_404, redirect, render
from django.views.decorators.http import require_POST

from core.audit import history_for
from core.permissions import has_perm, perm_required, scope_qs
from . import analytics as an
from . import forms as f
from . import models as m
from . import services as s


def forecasts_for(user):
    return scope_qs(user, m.Forecast.objects.select_related("pest", "crop", "division", "created_by"), "division")


@perm_required("forecast", "view")
def analysis(request):
    form = f.AnalysisForm(request.GET or None)
    ctx = {"form": form, "ran": False}
    if request.GET and form.is_valid():
        d = {k: (v.pk if hasattr(v, "pk") else v) for k, v in form.cleaned_data.items() if v and k != "period"}
        qs = an.confirmed_records(d, request.user)
        series = an.trend(qs, form.cleaned_data["period"])
        direction, slope = an.trend_direction(series)
        ctx.update(ran=True, series=series, direction=direction, slope=slope,
                   by_division=an.summarize(qs, "division"), by_pest=an.summarize(qs, "pest"),
                   chart_labels=[r["period"].strftime("%d/%m/%Y") for r in series],
                   chart_rate=[round(r["avg_rate"], 2) if r["avg_rate"] is not None else None for r in series],
                   chart_area=[round(r["affected"], 2) if r["affected"] is not None else None for r in series],
                   total=qs.count())
    return render(request, "forecasts/analysis.html", ctx)


@perm_required("forecast", "view")
def compare(request):
    from datetime import date

    p = request.GET
    result = None
    dim = p.get("dimension", "division")
    if dim not in an.DIMENSIONS:
        dim = "division"
    try:
        if all(p.get(k) for k in ("a_from", "a_to", "b_from", "b_to")):
            for k in ("a_from", "a_to", "b_from", "b_to"):
                date.fromisoformat(p[k])
            base = {k: p[k] for k in ("crop", "pest", "season", "division") if p.get(k)}
            result = an.compare_periods(base, request.user, p["a_from"], p["a_to"], p["b_from"], p["b_to"], dim)
    except ValueError:
        messages.error(request, "Ngày nhập không hợp lệ.")
    from accounts.models import AdminDivision
    from catalog.models import Crop, PestSpecies, Season

    return render(request, "forecasts/compare.html", {
        "result": result, "p": p, "dims": an.DIMENSIONS, "dim": dim, "crops": Crop.objects.all(),
        "pests": PestSpecies.objects.all(), "seasons": Season.objects.all(), "divisions": AdminDivision.objects.all()})


@perm_required("forecast", "view")
def forecast_list(request):
    qs = forecasts_for(request.user)
    for k in ("status", "risk_level", "pest"):
        if request.GET.get(k):
            qs = qs.filter(**{k: request.GET[k]})
    from catalog.models import PestSpecies
    from django.core.paginator import Paginator

    return render(request, "forecasts/forecast_list.html", {
        "page": Paginator(qs, 20).get_page(request.GET.get("page")), "statuses": m.Forecast.STATUSES,
        "risks": m.RISK_LEVELS, "pests": PestSpecies.objects.all(),
        "can_create": has_perm(request.user, "forecast", "create")})


@perm_required("forecast", "view")
def forecast_detail(request, pk):
    fc = get_object_or_404(forecasts_for(request.user), pk=pk)
    u = request.user
    return render(request, "forecasts/forecast_detail.html", {
        "fc": fc, "history": history_for(fc), "note_form": f.NoteForm(),
        "can_edit": fc.editable and has_perm(u, "forecast", "edit"),
        "can_submit": fc.status in ("draft", "rejected") and has_perm(u, "forecast", "edit"),
        "can_review": fc.status == "pending" and has_perm(u, "forecast", "confirm"),
        "can_evaluate": fc.is_confirmed and has_perm(u, "forecast", "edit"),
        "meta": fc.analysis_meta,
    })


def _form(request, fc):
    form = f.ForecastForm(request.POST or None, instance=fc)
    if request.method == "POST" and form.is_valid():
        obj = form.save(commit=False)
        if fc is None:
            obj.created_by = request.user
        obj.save()
        messages.success(request, "Đã lưu nhận định.")
        return redirect("forecasts:detail", pk=obj.pk)
    return render(request, "crud/form.html", {"form": form, "obj": fc, "title": "Nhận định dự tính, dự báo",
                                              "back_url": "/forecasts/forecasts/"})


@perm_required("forecast", "create")
def forecast_create(request):
    return _form(request, None)


@perm_required("forecast", "edit")
def forecast_edit(request, pk):
    fc = get_object_or_404(forecasts_for(request.user), pk=pk)
    if not fc.editable:
        messages.error(request, "Nhận định đã gửi hoặc đã xác nhận, không thể chỉnh sửa.")
        return redirect("forecasts:detail", pk=pk)
    return _form(request, fc)


@perm_required("forecast", "create")
def suggest_view(request):
    form = f.SuggestForm(request.POST or None)
    if request.method == "POST" and form.is_valid():
        try:
            fc = s.suggest(form.cleaned_data["threshold"], form.cleaned_data["division"], request.user,
                           form.cleaned_data["lookback_days"])
            messages.success(request, "Đã tạo nhận định gợi ý ở trạng thái dự thảo. Cần chuyên môn xem xét, bổ sung và xác nhận.")
            return redirect("forecasts:detail", pk=fc.pk)
        except s.ForecastError as e:
            messages.error(request, str(e))
    return render(request, "forecasts/suggest.html", {"form": form})


@require_POST
@perm_required("forecast", "view")  # quyền chi tiết theo từng hành động được kiểm tra bên trong
def forecast_action(request, pk, action):
    fc = get_object_or_404(forecasts_for(request.user), pk=pk)
    u = request.user
    if action in ("confirm", "reject"):
        if not has_perm(u, "forecast", "confirm"):
            raise PermissionDenied
    elif action in ("submit", "evaluate"):
        if not (has_perm(u, "forecast", "edit") or has_perm(u, "forecast", "create")):
            raise PermissionDenied
    else:
        raise PermissionDenied
    try:
        if action == "evaluate":
            s.evaluate_actual(fc, u)
        else:
            s.transition(fc, action, u, request.POST.get("note", "").strip())
        messages.success(request, "Đã cập nhật nhận định.")
    except s.ForecastError as e:
        messages.error(request, str(e))
    return redirect("forecasts:detail", pk=pk)
