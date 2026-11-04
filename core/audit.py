from django.apps import apps
from django.db.models.signals import post_delete, post_save, pre_save

from .middleware import get_current_ip, get_current_user

# Các model được tự động ghi nhật ký tạo/sửa/xóa (lịch sử kế hoạch, phân công, kết quả...)
TRACKED = [
    "accounts.User", "accounts.Unit", "accounts.AdminDivision", "accounts.RolePermission",
    "catalog.Crop", "catalog.PestSpecies", "catalog.GrowthStage", "catalog.SurveyMethod",
    "catalog.SurveyIndicator", "catalog.MeasureUnit", "catalog.Season", "catalog.DamageLevel",
    "surveys.FormTemplate", "surveys.FormField", "surveys.SurveyPlan", "surveys.SurveyRoute",
    "surveys.SurveyPoint", "surveys.SurveyTask", "surveys.SurveyRecord",
    "forecasts.Threshold", "forecasts.Forecast", "forecasts.WeatherData",
    "alerts.Alert", "alerts.FollowUpTask",
    "cms.Post", "cms.Category",
    "reports.ReportTemplate", "reports.ReportSchedule",
    "sysadmin.SystemConfig", "sysadmin.Document", "sysadmin.DocumentVersion",
]
SKIP_FIELDS = {"updated_at", "created_at", "password", "last_login"}


def _snapshot(instance):
    data = {}
    for f in instance._meta.concrete_fields:
        if f.name in SKIP_FIELDS:
            continue
        v = getattr(instance, f.attname, None)
        data[f.name] = None if v is None else str(v)
    return data


def write_log(action, obj=None, note="", changes=None, user=None):
    from .models import AuditLog

    user = user or get_current_user()
    return AuditLog.objects.create(
        user=user if user is not None and getattr(user, "pk", None) else None,
        username=getattr(user, "username", "") if user else "",
        action=action,
        model_label=obj._meta.label if obj is not None else "",
        object_id=str(obj.pk) if obj is not None and obj.pk is not None else "",
        object_repr=str(obj)[:255] if obj is not None else "",
        changes=changes or {},
        note=note,
        ip_address=get_current_ip(),
    )


def _pre_save(sender, instance, **kwargs):
    if instance.pk:
        old = sender.objects.filter(pk=instance.pk).first()
        instance._audit_old = _snapshot(old) if old else None
    else:
        instance._audit_old = None


def _post_save(sender, instance, created, **kwargs):
    new = _snapshot(instance)
    if created:
        write_log("create", instance, changes={})
        return
    old = getattr(instance, "_audit_old", None) or {}
    diff = {k: [old.get(k), v] for k, v in new.items() if old.get(k) != v}
    if diff:
        write_log("update", instance, changes=diff)


def _post_delete(sender, instance, **kwargs):
    write_log("delete", instance)


def register_tracked_models():
    for label in TRACKED:
        model = apps.get_model(label)
        pre_save.connect(_pre_save, sender=model, dispatch_uid=f"audit_pre_{label}")
        post_save.connect(_post_save, sender=model, dispatch_uid=f"audit_post_{label}")
        post_delete.connect(_post_delete, sender=model, dispatch_uid=f"audit_del_{label}")


def history_for(obj, limit=50):
    from .models import AuditLog

    return AuditLog.objects.filter(model_label=obj._meta.label, object_id=str(obj.pk))[:limit]
