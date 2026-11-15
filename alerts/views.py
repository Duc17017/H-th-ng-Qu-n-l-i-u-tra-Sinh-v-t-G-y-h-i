from django.contrib import messages
from django.core.exceptions import PermissionDenied
from django.core.paginator import Paginator
from django.shortcuts import get_object_or_404, redirect, render
from django.utils import timezone
from django.views.decorators.http import require_POST

from core.audit import history_for
from core.permissions import has_perm, perm_required
from . import forms as f
from . import models as m
from . import services as s


def alerts_for(user):
    qs = m.Alert.objects.select_related("pest", "crop", "created_by").prefetch_related("divisions")
    ids = None
    from core.permissions import division_ids_for

    ids = division_ids_for(user)
    if ids is not None:
        qs = qs.filter(divisions__in=ids).distinct()
    return qs


def followups_for(user):
    qs = m.FollowUpTask.objects.select_related("alert", "assignee", "unit", "division")
    if user.role == "surveyor":
        qs = qs.filter(assignee=user)
    return qs


@perm_required("alert", "view")
def alert_list(request):
    qs = alerts_for(request.user)
    for k in ("status", "risk_level", "pest"):
        if request.GET.get(k):
            qs = qs.filter(**{k: request.GET[k]})
    q = request.GET.get("q", "").strip()
    if q:
        qs = qs.filter(title__icontains=q)
    from catalog.models import PestSpecies
    from forecasts.models import RISK_LEVELS

    return render(request, "alerts/alert_list.html", {
        "page": Paginator(qs, 20).get_page(request.GET.get("page")), "statuses": m.Alert.STATUSES,
        "risks": RISK_LEVELS, "pests": PestSpecies.objects.all(), "q": q,
        "can_create": has_perm(request.user, "alert", "create")})


@perm_required("alert", "view")
def alert_detail(request, pk):
    a = get_object_or_404(alerts_for(request.user), pk=pk)
    u = request.user
    return render(request, "alerts/alert_detail.html", {
        "a": a, "revisions": a.revisions.select_related("user"), "followups": a.followups.select_related("assignee", "unit"),
        "summary": s.followup_summary(a), "note_form": f.NoteForm(),
        "can_edit": a.editable and has_perm(u, "alert", "edit"),
        "can_submit": a.status in ("draft", "updated") and has_perm(u, "alert", "edit"),
        "can_approve": a.status == "pending" and has_perm(u, "alert", "approve"),
        "can_update": a.status == "published" and has_perm(u, "alert", "edit"),
        "can_expire": a.status in ("published", "updated") and has_perm(u, "alert", "approve"),
        "can_followup": a.status in ("published", "updated") and has_perm(u, "alert", "create"),
        "recipients": s.recipients(a)[:50] if a.status != "draft" else [],
        "changes": history_for(a),
    })


def _form(request, alert):
    form = f.AlertForm(request.POST or None, instance=alert)
    if request.method == "POST" and form.is_valid():
        obj = form.save(commit=False)
        if alert is None:
            obj.created_by = request.user
        if obj.forecast_id and obj.forecast.status != "confirmed":
            form.add_error("forecast", "Chỉ được dùng nhận định đã xác nhận.")
        else:
            obj.save()
            form.save_m2m()
            s.add_revision(obj, "edit" if alert else "create", request.user)
            messages.success(request, "Đã lưu bản tin.")
            return redirect("alerts:alert_detail", pk=obj.pk)
    return render(request, "crud/form.html", {"form": form, "obj": alert, "title": "Bản tin cảnh báo",
                                              "back_url": "/alerts/alerts/"})


@perm_required("alert", "create")
def alert_create(request):
    return _form(request, None)


@perm_required("alert", "create")
def alert_from_forecast(request, forecast_id):
    from forecasts.models import Forecast

    fc = get_object_or_404(Forecast, pk=forecast_id, status="confirmed")
    form = f.AlertFromForecastForm(request.POST or None)
    if request.method == "POST" and form.is_valid():
        if m.Alert.objects.filter(code=form.cleaned_data["code"]).exists():
            form.add_error("code", "Số hiệu đã tồn tại.")
        else:
            a = m.Alert.objects.create(
                code=form.cleaned_data["code"], title=f"Cảnh báo {fc.pest.name} trên {fc.crop.name}",
                pest=fc.pest, crop=fc.crop, valid_from=fc.valid_from, valid_to=fc.valid_to,
                risk_level=fc.risk_level, forecast=fc, basis=fc.basis, guidance=fc.recommendation,
                channels=["web", "notify"], created_by=request.user)
            a.divisions.add(fc.division)
            s.add_revision(a, "create", request.user, "Tạo từ nhận định dự báo")
            messages.success(request, "Đã tạo bản tin từ nhận định đã xác nhận.")
            return redirect("alerts:alert_detail", pk=a.pk)
    return render(request, "alerts/from_forecast.html", {"form": form, "fc": fc})


@perm_required("alert", "edit")
def alert_edit(request, pk):
    a = get_object_or_404(alerts_for(request.user), pk=pk)
    if not a.editable:
        messages.error(request, "Bản tin đang chờ duyệt, đã phát hành hoặc hết hiệu lực, không thể sửa trực tiếp.")
        return redirect("alerts:alert_detail", pk=pk)
    return _form(request, a)


@require_POST
@perm_required("alert", "view")  # quyền chi tiết theo từng hành động được kiểm tra bên trong
def alert_action(request, pk, action):
    a = get_object_or_404(alerts_for(request.user), pk=pk)
    u = request.user
    can_write = has_perm(u, "alert", "edit") or has_perm(u, "alert", "create")
    try:
        if action in ("update", "submit") and not can_write:
            raise PermissionDenied
        if action == "update":
            s.start_update(a, u)
            messages.success(request, "Bản tin đã chuyển sang chế độ điều chỉnh (lần ban hành mới).")
            return redirect("alerts:alert_edit", pk=pk)
        if action in ("approve", "return", "expire", "reopen"):
            if not has_perm(u, "alert", "approve"):
                raise PermissionDenied
        elif action != "submit":
            raise PermissionDenied
        s.transition(a, action, u, request.POST.get("note", "").strip())
        messages.success(request, "Đã cập nhật trạng thái bản tin.")
    except s.AlertError as e:
        messages.error(request, str(e))
    return redirect("alerts:alert_detail", pk=pk)


# ---------------- nhiệm vụ theo dõi
@perm_required("alert", "view")
def followup_list(request):
    qs = followups_for(request.user)
    if request.GET.get("status"):
        qs = qs.filter(status=request.GET["status"])
    if request.GET.get("overdue"):
        qs = qs.exclude(status="done").filter(due_date__lt=timezone.localdate())
    return render(request, "alerts/followup_list.html", {
        "page": Paginator(qs, 25).get_page(request.GET.get("page")), "statuses": m.FollowUpTask.STATUSES,
        "can_create": has_perm(request.user, "alert", "create")})


@perm_required("alert", "create")
def followup_create(request):
    initial = {"alert": request.GET.get("alert")} if request.GET.get("alert") else None
    form = f.FollowUpForm(request.POST or None, initial=initial)
    form.fields["alert"].queryset = m.Alert.objects.filter(status__in=["published", "updated"])
    if request.method == "POST" and form.is_valid():
        t = form.save()
        if t.assignee:
            from core.notify import notify

            notify([t.assignee], "Nhiệm vụ theo dõi sau cảnh báo", t.title, f"/alerts/followups/{t.pk}/")
        messages.success(request, "Đã giao nhiệm vụ theo dõi.")
        return redirect("alerts:alert_detail", pk=t.alert_id)
    return render(request, "crud/form.html", {"form": form, "title": "Nhiệm vụ theo dõi sau cảnh báo",
                                              "back_url": "/alerts/followups/"})


@perm_required("alert", "view")
def followup_detail(request, pk):
    t = get_object_or_404(followups_for(request.user), pk=pk)
    can_report = (t.assignee_id == request.user.pk or has_perm(request.user, "alert", "edit")) and t.status != "done"
    return render(request, "alerts/followup_detail.html", {"t": t, "can_report": can_report,
                                                           "form": f.FollowUpResultForm(instance=t)})


@require_POST
@perm_required("alert", "view")
def followup_report(request, pk):
    t = get_object_or_404(followups_for(request.user), pk=pk)
    if not (t.assignee_id == request.user.pk or has_perm(request.user, "alert", "edit")) or t.status == "done":
        raise PermissionDenied
    form = f.FollowUpResultForm(request.POST, instance=t)
    if form.is_valid():
        obj = form.save(commit=False)
        if obj.status == "done":
            obj.completed_at = timezone.now()
        obj.save()
        messages.success(request, "Đã cập nhật kết quả theo dõi.")
    else:
        messages.error(request, "; ".join(e for errs in form.errors.values() for e in errs))
    return redirect("alerts:followup_detail", pk=pk)
