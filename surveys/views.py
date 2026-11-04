import json
import uuid

from django.contrib import messages
from django.core.exceptions import PermissionDenied
from django.core.paginator import Paginator
from django.db.models import Q
from django.http import HttpResponse, JsonResponse
from django.shortcuts import get_object_or_404, redirect, render
from django.urls import reverse
from django.utils import timezone
from django.views.decorators.http import require_POST

from core.audit import history_for
from core.permissions import division_ids_for, has_perm, perm_required, scope_qs
from catalog import models as cat
from . import forms as f
from . import models as m
from . import services as s


# ------------------------------------------------------------------ phạm vi dữ liệu
def records_for(user):
    qs = m.SurveyRecord.objects.select_related("point", "point__division", "crop", "pest", "surveyor", "damage_level")
    qs = scope_qs(user, qs, "point__division")
    if user.role == "surveyor":
        qs = qs.filter(Q(surveyor=user) | Q(task__assignee=user))
    return qs


def tasks_for(user):
    qs = m.SurveyTask.objects.select_related("plan", "point", "assignee", "unit")
    qs = scope_qs(user, qs, "point__division")
    if user.role == "surveyor":
        qs = qs.filter(assignee=user)
    return qs


def plans_for(user):
    return scope_qs(user, m.SurveyPlan.objects.select_related("crop", "division", "season"), "division")


def points_for(user):
    return scope_qs(user, m.SurveyPoint.objects.select_related("division", "route", "crop"), "division")


# ------------------------------------------------------------------ kế hoạch
@perm_required("plans", "view")
def plan_list(request):
    qs = plans_for(request.user)
    for key in ("status", "plan_type", "crop"):
        if request.GET.get(key):
            qs = qs.filter(**{key: request.GET[key]})
    q = request.GET.get("q", "").strip()
    if q:
        qs = qs.filter(Q(name__icontains=q) | Q(code__icontains=q))
    page = Paginator(qs, 20).get_page(request.GET.get("page"))
    from catalog.models import Crop

    return render(request, "surveys/plan_list.html", {
        "page": page, "q": q, "statuses": m.SurveyPlan.STATUSES, "types": m.SurveyPlan.TYPES,
        "crops": Crop.objects.all(), "can_create": has_perm(request.user, "plans", "create"),
    })


@perm_required("plans", "view")
def plan_detail(request, pk):
    plan = get_object_or_404(plans_for(request.user), pk=pk)
    tasks = plan.tasks.select_related("point", "assignee", "unit")
    done, total, pct = plan.progress()
    return render(request, "surveys/plan_detail.html", {
        "plan": plan, "routes": plan.routes.select_related("unit", "division"), "tasks": tasks[:300],
        "done": done, "total": total, "pct": pct, "history": history_for(plan),
        "can_edit": has_perm(request.user, "plans", "edit"),
        "can_approve": has_perm(request.user, "plans", "approve"),
        "gen_form": f.GenerateTasksForm(),
    })


@perm_required("plans", "create")
def plan_create(request):
    return _plan_form(request, None)


@perm_required("plans", "edit")
def plan_edit(request, pk):
    plan = get_object_or_404(plans_for(request.user), pk=pk)
    if plan.status not in ("draft", "approved", "running"):
        messages.error(request, "Kế hoạch đã kết thúc hoặc bị hủy, hãy mở lại trước khi sửa.")
        return redirect("surveys:plan_detail", pk=pk)
    return _plan_form(request, plan)


def _plan_form(request, plan):
    form = f.PlanForm(request.POST or None, instance=plan)
    if request.method == "POST" and form.is_valid():
        obj = form.save(commit=False)
        if plan is None:
            obj.created_by = request.user
            obj.status = "draft" if obj.status in ("approved", "running", "done") and not has_perm(request.user, "plans", "approve") else obj.status
        obj.save()
        form.save_m2m()
        messages.success(request, "Đã lưu kế hoạch.")
        return redirect("surveys:plan_detail", pk=obj.pk)
    return render(request, "crud/form.html", {"form": form, "obj": plan, "title": "Kế hoạch điều tra",
                                              "back_url": "/surveys/plans/"})


@require_POST
@perm_required("plans", "approve")
def plan_action(request, pk, action):
    plan = get_object_or_404(plans_for(request.user), pk=pk)
    if action not in s.PLAN_FLOW:
        raise PermissionDenied
    try:
        s.transition_plan(plan, action, request.user)
        messages.success(request, "Đã cập nhật trạng thái kế hoạch.")
    except s.WorkflowError as e:
        messages.error(request, str(e))
    return redirect("surveys:plan_detail", pk=pk)


@require_POST
@perm_required("plans", "edit")
def plan_generate(request, pk):
    plan = get_object_or_404(plans_for(request.user), pk=pk)
    form = f.GenerateTasksForm(request.POST)
    if form.is_valid():
        try:
            n = s.generate_tasks(plan, form.cleaned_data["unit"], form.cleaned_data["assignee"], form.cleaned_data["due_days"])
            messages.success(request, f"Đã sinh {n} nhiệm vụ điều tra mới.")
        except s.WorkflowError as e:
            messages.error(request, str(e))
    else:
        messages.error(request, "Thông tin sinh nhiệm vụ không hợp lệ.")
    return redirect("surveys:plan_detail", pk=pk)


# ------------------------------------------------------------------ nhiệm vụ
@perm_required("plans", "view")
def task_list(request):
    qs = tasks_for(request.user)
    status = request.GET.get("status")
    if status:
        qs = qs.filter(status=status)
    if request.GET.get("mine"):
        qs = qs.filter(assignee=request.user)
    if request.GET.get("overdue"):
        qs = qs.exclude(status="done").filter(due_date__lt=timezone.localdate())
    page = Paginator(qs, 25).get_page(request.GET.get("page"))
    return render(request, "surveys/task_list.html", {"page": page, "statuses": m.SurveyTask.STATUSES})


@require_POST
@perm_required("records", "create")
def task_start(request, pk):
    task = get_object_or_404(tasks_for(request.user), pk=pk)
    try:
        s.start_task(task, request.user)
    except s.WorkflowError as e:
        messages.error(request, str(e))
    return redirect("surveys:task_list")


# ------------------------------------------------------------------ phiếu điều tra
@perm_required("records", "view")
def record_list(request):
    qs = records_for(request.user)
    flt = f.RecordFilterForm(request.GET or None)
    if flt.is_valid():
        d = flt.cleaned_data
        if d["q"]:
            qs = qs.filter(Q(point__name__icontains=d["q"]) | Q(point__code__icontains=d["q"]) | Q(comment__icontains=d["q"]))
        for k in ("status", "crop", "pest"):
            if d[k]:
                qs = qs.filter(**{k: d[k]})
        if d["date_from"]:
            qs = qs.filter(survey_date__date__gte=d["date_from"])
        if d["date_to"]:
            qs = qs.filter(survey_date__date__lte=d["date_to"])
    page = Paginator(qs, 25).get_page(request.GET.get("page"))
    return render(request, "surveys/record_list.html", {
        "page": page, "flt": flt, "can_create": has_perm(request.user, "records", "create"),
        "can_import": has_perm(request.user, "data", "create"),
    })


def _can_edit_record(user, rec):
    if not has_perm(user, "records", "edit") and not has_perm(user, "records", "create"):
        return False
    if rec.status in ("draft", "revision"):
        return user.role in ("admin",) or rec.surveyor_id in (None, user.pk) or has_perm(user, "records", "confirm")
    return False


@perm_required("records", "view")
def record_detail(request, pk):
    rec = get_object_or_404(records_for(request.user), pk=pk)
    errors, warnings = rec.validate_data()
    u = request.user
    return render(request, "surveys/record_detail.html", {
        "rec": rec, "errors": errors, "warnings": warnings,
        "attachments": rec.attachments.all(), "history": rec.history.select_related("user"),
        "changes": history_for(rec),
        "can_edit": _can_edit_record(u, rec),
        "can_submit": rec.status in ("draft", "revision") and _can_edit_record(u, rec),
        "can_review": rec.status == "submitted" and has_perm(u, "records", "confirm"),
        "can_reopen": rec.status == "confirmed" and has_perm(u, "records", "approve"),
        "attach_form": f.AttachmentForm(), "review_form": f.ReviewForm(),
        "coords": rec.effective_coords(),
    })


def _record_form(request, rec=None, task=None):
    template = None
    if task and task.plan.form_template_id:
        template = task.plan.form_template
    form = f.RecordForm(request.POST or None, instance=rec, user=request.user, template=template,
                        initial=_initial_from_task(task) if task and not rec else None)
    form.fields["point"].queryset = points_for(request.user).filter(is_active=True)
    if request.method == "POST" and form.is_valid():
        obj = form.save(commit=False)
        errors, warnings = obj.validate_data()
        if errors:
            for e in errors:
                form.add_error(None, e)
        else:
            obj.save()
            if not obj.history.exists():
                m.RecordHistory.objects.create(record=obj, action="create", to_status=obj.status, user=request.user)
            if obj.task_id and obj.task.status == "assigned":
                obj.task.status = "doing"
                obj.task.save(update_fields=["status", "updated_at"])
            for w in warnings:
                messages.warning(request, w)
            messages.success(request, "Đã lưu phiếu điều tra.")
            if "submit" in request.POST:
                try:
                    s.transition_record(obj, "submit", request.user)
                    messages.success(request, "Đã gửi phiếu để xác nhận.")
                except s.WorkflowError as e:
                    messages.error(request, str(e))
            return redirect("surveys:record_detail", pk=obj.pk)
    return render(request, "surveys/record_form.html", {"form": form, "rec": rec, "task": task})


def _initial_from_task(task):
    p = task.plan
    return {"task": task.pk, "point": task.point_id, "crop": p.crop_id, "season": p.season_id,
            "method": p.method_id, "unit": task.unit_id,
            "pest": p.pests.first().pk if p.pests.exists() else None,
            "latitude": task.point.latitude, "longitude": task.point.longitude}


@perm_required("records", "create")
def record_create(request):
    task = None
    if request.GET.get("task"):
        task = get_object_or_404(tasks_for(request.user), pk=request.GET["task"])
    return _record_form(request, None, task)


@perm_required("records", "create")
def record_edit(request, pk):
    rec = get_object_or_404(records_for(request.user), pk=pk)
    if not _can_edit_record(request.user, rec):
        messages.error(request, "Bạn không thể chỉnh sửa phiếu ở trạng thái hiện tại.")
        return redirect("surveys:record_detail", pk=pk)
    return _record_form(request, rec, rec.task)


@require_POST
@perm_required("records", "view")  # quyền chi tiết theo từng hành động được kiểm tra bên trong
def record_action(request, pk, action):
    rec = get_object_or_404(records_for(request.user), pk=pk)
    u = request.user
    if action == "submit":
        ok = _can_edit_record(u, rec)
    elif action in ("confirm", "revise"):
        ok = has_perm(u, "records", "confirm")
    elif action == "reopen":
        ok = has_perm(u, "records", "approve")
    else:
        ok = False
    if not ok:
        raise PermissionDenied
    note = request.POST.get("note", "").strip()
    try:
        s.transition_record(rec, action, u, note)
        messages.success(request, "Đã cập nhật trạng thái phiếu.")
    except s.WorkflowError as e:
        messages.error(request, str(e))
    return redirect("surveys:record_detail", pk=pk)


@require_POST
@perm_required("records", "create")
def record_attach(request, pk):
    rec = get_object_or_404(records_for(request.user), pk=pk)
    if not _can_edit_record(request.user, rec):
        raise PermissionDenied
    form = f.AttachmentForm(request.POST, request.FILES)
    if form.is_valid():
        a = form.save(commit=False)
        a.record, a.uploaded_by = rec, request.user
        a.save()
        messages.success(request, "Đã đính kèm tệp.")
    else:
        messages.error(request, "; ".join(e for errs in form.errors.values() for e in errs))
    return redirect("surveys:record_detail", pk=pk)


@require_POST
@perm_required("records", "create")
def attachment_delete(request, pk):
    a = get_object_or_404(m.RecordAttachment, pk=pk)
    rec = get_object_or_404(records_for(request.user), pk=a.record_id)
    if not _can_edit_record(request.user, rec):
        raise PermissionDenied
    a.file.delete(save=False)
    a.delete()
    return redirect("surveys:record_detail", pk=rec.pk)


@perm_required("records", "view")
def form_fields_api(request, plan_id):
    """Trả về cấu hình trường động của biểu mẫu để giao diện offline có thể dựng form."""
    plan = get_object_or_404(plans_for(request.user), pk=plan_id)
    tpl = plan.form_template
    fields = []
    if tpl:
        fields = [{"key": x.key, "label": x.label, "type": x.field_type, "required": x.required,
                   "min": x.min_value, "max": x.max_value, "choices": x.choice_list()} for x in tpl.fields.all()]
    return JsonResponse({"template": tpl.name if tpl else None, "fields": fields})


# ------------------------------------------------------------------ làm việc ngoại tuyến
@perm_required("records", "create")
def offline_page(request):
    from catalog import models as cat

    tasks = tasks_for(request.user).exclude(status="done").select_related("plan", "point")[:200]
    payload = {
        "crops": list(cat.Crop.objects.filter(is_active=True).values("id", "name")),
        "pests": list(cat.PestSpecies.objects.filter(is_active=True).values("id", "name")),
        "points": [{"id": p.pk, "name": f"{p.code} - {p.name}", "lat": p.latitude, "lng": p.longitude}
                   for p in points_for(request.user).filter(is_active=True)[:1000]],
        "tasks": [{"id": t.pk, "label": str(t), "point": t.point_id, "crop": t.plan.crop_id} for t in tasks],
    }
    return render(request, "surveys/offline.html", {"payload_json": json.dumps(payload, ensure_ascii=False)})


@require_POST
@perm_required("records", "create")
def sync_api(request):
    """Nhận các phiếu lưu tạm ở thiết bị và đồng bộ lên máy chủ (idempotent theo client_uuid)."""
    try:
        items = json.loads(request.body.decode("utf-8")).get("records", [])
    except (ValueError, AttributeError):
        return JsonResponse({"error": "Dữ liệu không hợp lệ"}, status=400)
    if not isinstance(items, list) or len(items) > 200:
        return JsonResponse({"error": "Danh sách phiếu không hợp lệ"}, status=400)
    results = []
    visible_points = {p.pk: p for p in points_for(request.user)}
    for it in items:
        cid = str(it.get("client_uuid", ""))[:64]
        try:
            if not cid:
                raise ValueError("Thiếu mã phiếu cục bộ")
            existing = m.SurveyRecord.objects.filter(client_uuid=cid, surveyor=request.user).first()
            if existing:
                results.append({"client_uuid": cid, "ok": True, "id": existing.pk, "duplicate": True})
                continue
            point = visible_points.get(int(it["point"]))
            if not point:
                raise ValueError("Điểm điều tra không hợp lệ")
            when = timezone.datetime.fromisoformat(it["survey_date"])
            if timezone.is_naive(when):
                when = timezone.make_aware(when)
            task = None
            if it.get("task"):
                task = tasks_for(request.user).filter(pk=int(it["task"]), point=point).first()
            rec = m.SurveyRecord(
                client_uuid=cid, point=point, task=task, plan=task.plan if task else None,
                survey_date=when, surveyor=request.user, unit=request.user.unit, crop_id=int(it["crop"]),
                pest_id=int(it["pest"]), source="mobile", status="draft",
                density=_num(it.get("density")), damage_rate=_num(it.get("damage_rate")),
                surveyed_area=_num(it.get("surveyed_area")), affected_area=_num(it.get("affected_area")),
                latitude=_num(it.get("latitude")), longitude=_num(it.get("longitude")),
                comment=str(it.get("comment", ""))[:2000])
            errors, warnings = rec.validate_data()
            if errors:
                raise ValueError(" ".join(errors))
            rec.save()
            m.RecordHistory.objects.create(record=rec, action="sync", to_status="draft",
                                           note="Đồng bộ từ thiết bị", user=request.user)
            results.append({"client_uuid": cid, "ok": True, "id": rec.pk, "warnings": warnings})
        except (KeyError, ValueError, TypeError) as e:
            results.append({"client_uuid": cid, "ok": False, "error": str(e)})
    return JsonResponse({"results": results})


def _num(v):
    if v in (None, ""):
        return None
    return float(v)


# ------------------------------------------------------------------ nhập Excel
@perm_required("data", "create")
def import_page(request):
    form = f.ExcelImportForm(request.POST or None, request.FILES or None)
    result = None
    if request.method == "POST" and form.is_valid():
        try:
            result = s.import_records(form.cleaned_data["file"], request.user,
                                      valid_only=form.cleaned_data["valid_only"],
                                      dry_run="preview" in request.POST)
            if "preview" in request.POST:
                messages.info(request, "Đây là kết quả kiểm tra thử, chưa có dữ liệu nào được lưu.")
            elif result["created"]:
                messages.success(request, f"Đã nhập {result['created']} phiếu (trạng thái lưu tạm).")
            else:
                messages.error(request, "Không có phiếu nào được nhập. Hãy sửa các dòng lỗi và thử lại.")
        except s.WorkflowError as e:
            messages.error(request, str(e))
    return render(request, "surveys/import.html", {"form": form, "result": result})


@perm_required("data", "create")
def import_template(request):
    resp = HttpResponse(s.build_template_xlsx(),
                        content_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet")
    resp["Content-Disposition"] = 'attachment; filename="mau_nhap_phieu_dieu_tra.xlsx"'
    return resp


# Giao diện quản lý Biểu mẫu & Chuẩn hóa QCVN (Mockup 6)
@perm_required("plans", "view")
def template_catalog(request):
    """Trang tổng quan danh mục biểu mẫu với chi tiết cấu trúc trường và rule engine."""
    from core.audit import history_for
    
    templates = m.FormTemplate.objects.select_related("crop", "pest", "method").order_by("-is_active", "code")
    if request.GET.get("q"):
        q = request.GET["q"]
        templates = templates.filter(Q(code__icontains=q) | Q(name__icontains=q) | Q(description__icontains=q))
    if request.GET.get("crop"):
        templates = templates.filter(crop_id=request.GET["crop"])
    if request.GET.get("is_active"):
        templates = templates.filter(is_active=request.GET["is_active"] == "True")
    
    sel_id = request.GET.get("template_id")
    sel_template = None
    if sel_id:
        try:
            sel_template = templates.get(pk=int(sel_id))
        except (m.FormTemplate.DoesNotExist, ValueError):
            pass
    
    # Nếu chưa chọn, lấy cái đầu tiên
    if not sel_template and templates.exists():
        sel_template = templates.first()
    
    ctx = {
        "templates": templates,
        "sel_template": sel_template,
        "fields": sel_template.fields.all().order_by("order") if sel_template else [],
        "audit": history_for(sel_template) if sel_template else [],
        "crops": cat.Crop.objects.filter(is_active=True),
        "q": request.GET.get("q", ""),
    }
    return render(request, "surveys/template_catalog.html", ctx)


@perm_required("plans", "edit")
def template_detail_edit(request, pk):
    """Chỉnh sửa cấu trúc biểu mẫu (thêm/sửa/xóa field)."""
    template = get_object_or_404(m.FormTemplate, pk=pk)
    if request.method == "POST":
        form = f.FormTemplateForm(request.POST, instance=template)
        if form.is_valid():
            form.save()
            messages.success(request, "Đã cập nhật biểu mẫu.")
            return redirect(f"{reverse('surveys:template_catalog')}?template_id={template.pk}")
    else:
        form = f.FormTemplateForm(instance=template)
    
    ctx = {
        "template": template,
        "form": form,
        "fields": template.fields.all().order_by("order"),
    }
    return render(request, "surveys/template_edit.html", ctx)


# Rule Engine Sandbox Simulator
@perm_required("plans", "edit")
def sandbox_simulator(request):
    """Interactive Rule Engine sandbox para kiểm định dữ liệu."""
    ctx = {
        "presets": [
            {
                "id": 1,
                "name": "Bộ mẫu 1: Tuyến Yên Dũng",
                "status": "HỢP LỆ (PASS)",
                "desc": "GPS an toàn ±2.5m, chuẩn Geofencing, mật độ rầy 650 con/m², ảnh đầy đủ EXIF.",
                "gps_accuracy": 2.5,
                "density": 650,
                "stage": "de_nhanh",
            },
            {
                "id": 2,
                "name": "Bộ mẫu 2: Tuyến Hiệp Hòa",
                "status": "CẢNH BÁO & LỖI ĐA TẦNG",
                "desc": "Lệch GPS 18.5m, vượt Geofence 120m, mật độ rầy 12.500 con/m², xung đột sinh học.",
                "gps_accuracy": 18.5,
                "density": 12500,
                "stage": "de_nhanh",
            },
            {
                "id": 3,
                "name": "Bộ mẫu 3: Tuyến Lục Nam",
                "status": "NGHI GIAN LẬN (MOCK)",
                "desc": "Timestamp ảnh lệch 45 phút, trùng lặp tọa độ, nghi ngờ Anti-Mock.",
                "gps_accuracy": 8.0,
                "density": 2400,
                "stage": "lam_dong",
            },
        ]
    }
    return render(request, "surveys/sandbox.html", ctx)


from django.http import JsonResponse
from django.views.decorators.http import require_POST

@require_POST
@perm_required("plans", "view")
def api_sandbox_simulate(request):
    """API endpoint để evaluate Rule Engine dựa trên input parameters."""
    import json
    try:
        data = json.loads(request.body)
        gps_acc = float(data.get("gps_accuracy", 10))
        density = int(data.get("density", 1000))
        stage = data.get("stage", "de_nhanh")
        
        results = {
            "gps_accuracy": gps_acc,
            "density": density,
            "stage": stage,
            "rules": {},
            "score": 0,
            "fails": 0,
            "warns": 0,
            "passes": 0,
            "overall_status": "UNKNOWN",
        }
        
        # Rule GPS-01: Bán kính sai số
        if gps_acc <= 10.0:
            results["rules"]["GPS-01"] = {"status": "PASS", "color": "primary"}
            results["passes"] += 1
        else:
            results["rules"]["GPS-01"] = {"status": "WARN", "color": "secondary"}
            results["warns"] += 1
        
        # Rule GPS-02: Geofencing (fixed failure in preset 2)
        results["rules"]["GPS-02"] = {"status": "FAIL", "color": "tertiary"}
        results["fails"] += 1
        
        # Rule GPS-03: Anti-Mock (fixed warning)
        results["rules"]["GPS-03"] = {"status": "WARN", "color": "secondary"}
        results["warns"] += 1
        
        # Rule DENS-01: Mật độ
        if density <= 10000:
            results["rules"]["DENS-01"] = {"status": "PASS", "color": "primary"}
            results["passes"] += 1
        else:
            results["rules"]["DENS-01"] = {"status": "FAIL", "color": "tertiary"}
            results["fails"] += 1
        
        # Rule DENS-02: Minh chứng (fixed failure)
        results["rules"]["DENS-02"] = {"status": "FAIL", "color": "tertiary"}
        results["fails"] += 1
        
        # Rule DENS-03: Xung đột sinh học
        if stage == "tro_chin":
            results["rules"]["DENS-03"] = {"status": "PASS", "color": "primary"}
            results["passes"] += 1
        else:
            results["rules"]["DENS-03"] = {"status": "FAIL", "color": "tertiary"}
            results["fails"] += 1
        
        # Calculate score
        results["score"] = min(100, round((results["passes"] * 16.6) + (results["warns"] * 8)))
        
        if results["fails"] > 0:
            results["overall_status"] = "KHÔNG HỢP LỆ - BỊ CHẶN"
            results["verdict_color"] = "tertiary"
        elif results["warns"] > 0:
            results["overall_status"] = "ĐẠT CÓ ĐIỀU KIỆN"
            results["verdict_color"] = "secondary"
        else:
            results["overall_status"] = "HỢP LỆ TOÀN DIỆN"
            results["verdict_color"] = "primary"
        
        return JsonResponse(results)
    except Exception as e:
        return JsonResponse({"error": str(e)}, status=400)
