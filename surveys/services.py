"""Nghiệp vụ điều tra: chuyển trạng thái phiếu/nhiệm vụ, nhập Excel, sinh nhiệm vụ."""
import datetime as dt
import io

from django.db import transaction
from django.utils import timezone

from core.audit import write_log
from core.notify import notify, users_with_perm
from catalog import models as cat
from . import models as m

# ---- Quy trình phiếu: draft -> submitted -> (revision | confirmed)
RECORD_FLOW = {
    "submit": ({"draft", "revision"}, "submitted"),
    "confirm": ({"submitted"}, "confirmed"),
    "revise": ({"submitted"}, "revision"),
    "reopen": ({"confirmed"}, "revision"),
}


class WorkflowError(Exception):
    pass


def _sync_task(record):
    """Đồng bộ trạng thái nhiệm vụ theo trạng thái phiếu."""
    task = record.task
    if not task:
        return
    mapping = {"draft": "doing", "submitted": "review", "revision": "revision", "confirmed": "done"}
    new = mapping.get(record.status)
    if new and task.status != new:
        task.status = new
        task.save(update_fields=["status", "updated_at"])


@transaction.atomic
def transition_record(record, action, user, note=""):
    allowed_from, to = RECORD_FLOW[action]
    if record.status not in allowed_from:
        raise WorkflowError("Trạng thái hiện tại của phiếu không cho phép thao tác này.")
    if action == "submit":
        errors, _ = record.validate_data()
        if errors:
            raise WorkflowError("Dữ liệu chưa hợp lệ: " + " ".join(errors))
    if action in ("revise", "reopen") and not note.strip():
        raise WorkflowError("Cần nhập ý kiến khi yêu cầu chỉnh sửa, bổ sung.")
    old = record.status
    record.status = to
    if action == "confirm":
        record.confirmed_by, record.confirmed_at = user, timezone.now()
        if note:
            record.review_note = note
    elif action in ("revise", "reopen"):
        record.review_note = note
        record.confirmed_by, record.confirmed_at = None, None
    record.save()
    m.RecordHistory.objects.create(record=record, action=action, from_status=old, to_status=to, note=note, user=user)
    write_log(f"record_{action}", record, note=note, changes={"status": [old, to]}, user=user)
    _sync_task(record)

    url = f"/surveys/records/{record.pk}/"
    if action == "submit":
        div_ids = record.point.division.parent.descendant_ids() if record.point.division.parent_id else None
        notify([u for u in users_with_perm("records", "confirm", div_ids) if u != user],
               "Phiếu điều tra chờ xác nhận", str(record), url)
    elif action in ("revise", "reopen") and record.surveyor:
        notify([record.surveyor], "Phiếu điều tra cần chỉnh sửa", note, url)
    elif action == "confirm" and record.surveyor and record.surveyor != user:
        notify([record.surveyor], "Phiếu điều tra đã được xác nhận", str(record), url)
    return record


TASK_FLOW = {"start": ({"assigned"}, "doing")}


@transaction.atomic
def start_task(task, user):
    if task.status not in TASK_FLOW["start"][0]:
        raise WorkflowError("Nhiệm vụ không ở trạng thái 'Đã giao'.")
    old = task.status
    task.status = "doing"
    task.save()
    write_log("task_start", task, changes={"status": [old, "doing"]}, user=user)


PLAN_FLOW = {
    "approve": ({"draft"}, "approved"),
    "start": ({"approved"}, "running"),
    "finish": ({"running", "approved"}, "done"),
    "cancel": ({"draft", "approved", "running"}, "cancelled"),
    "reopen": ({"cancelled", "done"}, "draft"),
}


@transaction.atomic
def transition_plan(plan, action, user):
    allowed, to = PLAN_FLOW[action]
    if plan.status not in allowed:
        raise WorkflowError("Trạng thái kế hoạch không cho phép thao tác này.")
    if action == "approve" and not plan.routes.exists() and not plan.tasks.exists():
        raise WorkflowError("Cần có ít nhất một tuyến hoặc nhiệm vụ điều tra trước khi phê duyệt.")
    if action == "finish":
        pending = plan.tasks.exclude(status="done").count()
        if pending:
            raise WorkflowError(f"Còn {pending} nhiệm vụ chưa hoàn thành.")
    old = plan.status
    plan.status = to
    plan.save()
    write_log(f"plan_{action}", plan, changes={"status": [old, to]}, user=user)
    if action == "approve":
        users = [t.assignee for t in plan.tasks.select_related("assignee") if t.assignee]
        notify(users, "Kế hoạch điều tra đã được phê duyệt", str(plan), f"/surveys/plans/{plan.pk}/")


@transaction.atomic
def generate_tasks(plan, unit=None, assignee=None, due_days=3):
    """Sinh nhiệm vụ cho các điểm thuộc tuyến của kế hoạch theo chu kỳ lặp; bỏ qua nhiệm vụ đã có."""
    points = m.SurveyPoint.objects.filter(route__plan=plan, is_active=True).select_related("route")
    if not points:
        raise WorkflowError("Kế hoạch chưa có điểm điều tra thuộc tuyến nào.")
    dates, d = [], plan.start_date
    step = plan.frequency_days
    while d <= plan.end_date:
        dates.append(d)
        if step <= 0:
            break
        d += dt.timedelta(days=step)
    created = 0
    for p in points:
        for d in dates:
            _, was_created = m.SurveyTask.objects.get_or_create(
                plan=plan, point=p, survey_date=d,
                defaults={"unit": unit or p.route.unit, "assignee": assignee,
                          "due_date": d + dt.timedelta(days=due_days)})
            created += was_created
    return created


# ---------------- Nhập Excel ----------------
IMPORT_COLUMNS = [
    ("point_code", "Mã điểm điều tra *"),
    ("survey_date", "Ngày điều tra * (dd/mm/yyyy)"),
    ("crop_code", "Mã cây trồng *"),
    ("pest_code", "Mã sinh vật gây hại *"),
    ("stage_code", "Mã giai đoạn sinh trưởng"),
    ("method_code", "Mã phương pháp"),
    ("density", "Mật độ"),
    ("damage_rate", "Tỷ lệ hại (%)"),
    ("damage_level_code", "Mã mức độ gây hại"),
    ("surveyed_area", "Diện tích điều tra (ha)"),
    ("affected_area", "Diện tích bị hại (ha)"),
    ("latitude", "Vĩ độ"),
    ("longitude", "Kinh độ"),
    ("comment", "Nhận xét"),
]


def build_template_xlsx():
    from openpyxl import Workbook
    from openpyxl.styles import Font

    wb = Workbook()
    ws = wb.active
    ws.title = "Phieu_dieu_tra"
    ws.append([label for _, label in IMPORT_COLUMNS])
    for c in ws[1]:
        c.font = Font(bold=True)
    ws.append(["DD001", "15/10/2026", "LUA", "RAYNAU", "", "", 120, 15, "", 2, 0.3, 10.123, 105.456, "Mẫu"])
    for col in "ABCDEFGHIJKLMN":
        ws.column_dimensions[col].width = 22
    ref = wb.create_sheet("Danh_muc")
    ref.append(["Loại", "Mã", "Tên"])
    for label, qs in (("Cây trồng", cat.Crop.objects.all()), ("Sinh vật gây hại", cat.PestSpecies.objects.all()),
                      ("Giai đoạn", cat.GrowthStage.objects.all()), ("Phương pháp", cat.SurveyMethod.objects.all()),
                      ("Mức độ gây hại", cat.DamageLevel.objects.all())):
        for o in qs:
            ref.append([label, o.code, o.name])
    ref.append(["Điểm điều tra", "", ""])
    for p in m.SurveyPoint.objects.filter(is_active=True):
        ref.append(["Điểm điều tra", p.code, p.name])
    buf = io.BytesIO()
    wb.save(buf)
    return buf.getvalue()


def _to_float(v, label, errs, lo=None, hi=None):
    if v in (None, ""):
        return None
    try:
        f = float(str(v).replace(",", "."))
    except ValueError:
        errs.append(f"{label} không phải số")
        return None
    if lo is not None and f < lo or hi is not None and f > hi:
        errs.append(f"{label} ngoài phạm vi")
    return f


def _to_date(v, errs):
    if isinstance(v, dt.datetime):
        return v
    if isinstance(v, dt.date):
        return dt.datetime.combine(v, dt.time(7, 0))
    for fmt in ("%d/%m/%Y", "%Y-%m-%d", "%d-%m-%Y"):
        try:
            return dt.datetime.strptime(str(v).strip(), fmt).replace(hour=7)
        except ValueError:
            continue
    errs.append("Ngày điều tra không đúng định dạng")
    return None


def import_records(fileobj, user, valid_only=False, dry_run=False):
    """Đọc Excel, kiểm tra từng dòng. Trả về dict: rows (kết quả từng dòng), created, errors."""
    from openpyxl import load_workbook

    try:
        wb = load_workbook(fileobj, read_only=True, data_only=True)
    except Exception:
        raise WorkflowError("Không đọc được tệp Excel. Hãy dùng đúng tệp mẫu .xlsx.")
    ws = wb[wb.sheetnames[0]]
    rows = list(ws.iter_rows(values_only=True))
    if len(rows) < 2:
        raise WorkflowError("Tệp không có dữ liệu.")
    if len(rows) > 5001:
        raise WorkflowError("Tệp vượt quá 5000 dòng dữ liệu.")
    keys = [k for k, _ in IMPORT_COLUMNS]
    points = {p.code: p for p in m.SurveyPoint.objects.select_related("division")}
    crops = {o.code: o for o in cat.Crop.objects.all()}
    pests = {o.code: o for o in cat.PestSpecies.objects.all()}
    stages = {o.code: o for o in cat.GrowthStage.objects.all()}
    methods = {o.code: o for o in cat.SurveyMethod.objects.all()}
    levels = {o.code: o for o in cat.DamageLevel.objects.all()}

    results, objs, seen = [], [], set()
    for idx, raw in enumerate(rows[1:], start=2):
        if raw is None or all(c in (None, "") for c in raw):
            continue
        r = dict(zip(keys, list(raw) + [None] * (len(keys) - len(raw))))
        errs, warns = [], []
        point = points.get(str(r["point_code"] or "").strip())
        crop = crops.get(str(r["crop_code"] or "").strip())
        pest = pests.get(str(r["pest_code"] or "").strip())
        if not point:
            errs.append("Không tìm thấy mã điểm điều tra")
        if not crop:
            errs.append("Không tìm thấy mã cây trồng")
        if not pest:
            errs.append("Không tìm thấy mã sinh vật gây hại")
        when = _to_date(r["survey_date"], errs) if r["survey_date"] not in (None, "") else None
        if r["survey_date"] in (None, ""):
            errs.append("Thiếu ngày điều tra")
        stage = methods_obj = level = None
        if r["stage_code"]:
            stage = stages.get(str(r["stage_code"]).strip())
            if not stage:
                errs.append("Không tìm thấy mã giai đoạn")
        if r["method_code"]:
            methods_obj = methods.get(str(r["method_code"]).strip())
            if not methods_obj:
                errs.append("Không tìm thấy mã phương pháp")
        if r["damage_level_code"]:
            level = levels.get(str(r["damage_level_code"]).strip())
            if not level:
                errs.append("Không tìm thấy mã mức độ gây hại")
        rec = m.SurveyRecord(
            point=point, crop=crop, pest=pest, stage=stage, method=methods_obj, damage_level=level,
            density=_to_float(r["density"], "Mật độ", errs, lo=0),
            damage_rate=_to_float(r["damage_rate"], "Tỷ lệ hại", errs, lo=0, hi=100),
            surveyed_area=_to_float(r["surveyed_area"], "Diện tích điều tra", errs, lo=0),
            affected_area=_to_float(r["affected_area"], "Diện tích bị hại", errs, lo=0),
            latitude=_to_float(r["latitude"], "Vĩ độ", errs, lo=-90, hi=90),
            longitude=_to_float(r["longitude"], "Kinh độ", errs, lo=-180, hi=180),
            comment=str(r["comment"] or ""), source="excel", status="draft", surveyor=user,
            unit=user.unit,
        )
        if when:
            rec.survey_date = timezone.make_aware(when) if timezone.is_naive(when) else when
        if not errs and point and crop and pest and when:
            e2, w2 = rec.validate_data()
            errs += e2
            warns += w2
            key = (point.pk, crop.pk, pest.pk, rec.survey_date.date())
            if key in seen:
                warns.append("Trùng với dòng khác trong tệp")
            seen.add(key)
        results.append({"row": idx, "errors": errs, "warnings": warns, "label": f"{r['point_code']} / {r['pest_code']}"})
        if not errs:
            objs.append(rec)

    n_err = sum(1 for x in results if x["errors"])
    created = 0
    if not dry_run and objs and (n_err == 0 or valid_only):
        with transaction.atomic():
            for rec in objs:
                rec.save()
                m.RecordHistory.objects.create(record=rec, action="import", to_status="draft",
                                               note="Nhập từ Excel", user=user)
                created += 1
        write_log("excel_import", note=f"Nhập {created} phiếu, {n_err} dòng lỗi", user=user)
    return {"rows": results, "created": created, "error_rows": n_err, "total": len(results)}
