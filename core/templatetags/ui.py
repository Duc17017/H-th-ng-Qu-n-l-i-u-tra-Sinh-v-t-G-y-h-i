import datetime as dt

from django import template
from django.utils import timezone
from django.utils.safestring import mark_safe

register = template.Library()


@register.filter
def get_item(d, key):
    try:
        return d.get(key)
    except AttributeError:
        return None


@register.filter
def has_action(perms, module_action):
    module, _, action = module_action.partition(":")
    return action in perms.get(module, ())


@register.filter
def vn_date(value):
    if not value:
        return ""
    if isinstance(value, dt.datetime):
        value = timezone.localtime(value) if timezone.is_aware(value) else value
        return value.strftime("%d/%m/%Y %H:%M")
    return value.strftime("%d/%m/%Y")


@register.filter
def num(value, digits=2):
    if value is None or value == "":
        return "-"
    try:
        return f"{float(value):,.{int(digits)}f}".rstrip("0").rstrip(".") if "." in f"{float(value):.{int(digits)}f}" else f"{float(value):,.0f}"
    except (TypeError, ValueError):
        return value


# ───────────────────────────── huy hiệu (badge) ──────────────────────────────
_BADGE_BASE = "inline-flex items-center gap-1 px-2.5 py-0.5 rounded-full font-label-sm text-label-sm whitespace-nowrap"

# Trạng thái nghiệp vụ dùng chung cho mọi phân hệ
STATE = {
    # SurveyRecord
    "draft": ("Lưu tạm / Dự thảo", "bg-surface-container text-on-surface-variant"),
    "submitted": ("Chờ xác nhận", "bg-secondary-fixed text-on-secondary-fixed"),
    "revision": ("Yêu cầu chỉnh sửa", "bg-error-container text-on-error-container"),
    "confirmed": ("Đã xác nhận", "bg-primary-fixed text-on-primary-fixed"),
    # SurveyPlan
    "approved": ("Đã phê duyệt", "bg-primary-fixed text-on-primary-fixed"),
    "running": ("Đang thực hiện", "bg-primary-container text-white"),
    "done": ("Hoàn thành", "bg-primary-fixed text-on-primary-fixed"),
    "cancelled": ("Đã hủy", "bg-surface-container-high text-on-surface-variant"),
    # Forecast / Alert / Post
    "pending": ("Chờ phê duyệt", "bg-secondary-fixed text-on-secondary-fixed"),
    "published": ("Đã phát hành", "bg-primary-container text-white"),
    "updated": ("Đã cập nhật", "bg-primary-fixed text-on-primary-fixed"),
    "expired": ("Hết hiệu lực", "bg-surface-container-high text-on-surface-variant"),
    "rejected": ("Không thông qua", "bg-error-container text-on-error-container"),
    "review": ("Chờ duyệt", "bg-secondary-fixed text-on-secondary-fixed"),
    "unpublished": ("Đã gỡ bài", "bg-surface-container-high text-on-surface-variant"),
    # SurveyTask
    "assigned": ("Đã giao", "bg-surface-container text-on-surface"),
    "doing": ("Đang thực hiện", "bg-secondary-container text-white"),
    # FollowUpTask
    "open": ("Chưa xử lý", "bg-surface-container text-on-surface"),
}

RISK = {
    "low": ("Thấp", "bg-primary-fixed text-on-primary-fixed"),
    "medium": ("Trung bình", "bg-secondary-fixed text-on-secondary-fixed"),
    "high": ("Cao", "bg-secondary-container text-white"),
    "very_high": ("Rất cao", "bg-tertiary-container text-white"),
}

ROLE = {
    "admin": ("Quản trị", "bg-tertiary-fixed text-tertiary"),
    "leader": ("Lãnh đạo", "bg-surface-container-highest text-on-surface"),
    "approver": ("Phê duyệt", "bg-surface-container-highest text-on-surface"),
    "expert": ("Chuyên môn", "bg-secondary-fixed text-on-secondary-fixed"),
    "editor": ("Biên tập", "bg-secondary-fixed text-on-secondary-fixed"),
    "surveyor": ("Điều tra", "bg-primary-fixed text-on-primary-fixed"),
    "viewer": ("Xem", "bg-surface-container text-on-surface-variant"),
}


def _pill(text, cls, icon=None):
    ic = f'<span class="msym text-[13px]">{icon}</span>' if icon else ""
    return mark_safe(f'<span class="{_BADGE_BASE} {cls}">{ic}{text}</span>')


@register.filter
def state_badge(obj, attr="status"):
    """Huy hiệu trạng thái: {% obj|state_badge %} hoặc {% obj|state_badge:'risk_level' %}."""
    raw = getattr(obj, attr, obj) if not isinstance(obj, str) else obj
    label, cls = STATE.get(str(raw), (str(raw), "bg-surface-container text-on-surface-variant"))
    disp = None
    if not isinstance(obj, str):
        getter = getattr(obj, f"get_{attr}_display", None)
        disp = getter() if callable(getter) else None
    return _pill(disp or label, cls)


@register.filter
def risk_badge(value):
    """Huy hiệu mức độ nguy cơ (low/medium/high/very_high)."""
    if hasattr(value, "get_risk_level_display"):
        key, label = value.risk_level, value.get_risk_level_display()
    else:
        key = str(value)
        label = RISK.get(key, (key, ""))[0]
    _, cls = RISK.get(key, ("", "bg-surface-container text-on-surface-variant"))
    icon = "priority_high" if key in ("high", "very_high") else "info"
    return _pill(label, cls, icon)


@register.filter
def role_badge(role):
    """Huy hiệu vai trò RBAC (nhận mã hoặc đối tượng User)."""
    key = getattr(role, "role", role)
    label, cls = ROLE.get(str(key), (str(key), "bg-surface-container text-on-surface-variant"))
    if hasattr(role, "get_role_display"):
        label = role.get_role_display()
    return _pill(label, cls)


@register.filter
def initials(user):
    """Hai chữ cái đầu của họ tên (dùng làm avatar)."""
    name = (getattr(user, "display_name", "") or str(user)).split()
    if not name:
        return "?"
    return (name[0][0] + (name[-1][0] if len(name) > 1 else "")).upper()


AUDIT_ICON = {
    "create": ("add_circle", "bg-primary-fixed text-primary"),
    "update": ("edit", "bg-primary-fixed text-primary"),
    "delete": ("delete", "bg-error-container text-on-error-container"),
    "approve": ("verified", "bg-primary-fixed text-primary"),
    "confirm": ("task_alt", "bg-primary-fixed text-primary"),
    "submit": ("send", "bg-secondary-fixed text-on-secondary-fixed"),
    "backup": ("cloud_sync", "bg-primary-fixed text-primary"),
    "restore": ("settings_backup_restore", "bg-secondary-fixed text-on-secondary-fixed"),
    "login": ("login", "bg-surface-container text-on-surface-variant"),
}


@register.filter
def audit_icon(action, part="icon"):
    """Biểu tượng + màu cho dòng nhật ký kiểm toán theo loại hành động."""
    key = next((k for k in AUDIT_ICON if k in (action or "").lower()), None)
    icon, cls = AUDIT_ICON.get(key, ("history", "bg-surface-container text-on-surface-variant"))
    return icon if part == "icon" else cls


@register.filter
def pct(part, whole):
    try:
        return round(float(part) * 100 / float(whole)) if whole else 0
    except (TypeError, ValueError, ZeroDivisionError):
        return 0


@register.simple_tag(takes_context=True)
def qs_without(context, *names):
    q = context["request"].GET.copy()
    for n in names:
        q.pop(n, None)
    return q.urlencode()


@register.simple_tag(takes_context=True)
def qs_set(context, **kwargs):
    """Giữ tham số truy vấn hiện tại, ghi đè một số khóa: {% qs_set page=2 %}."""
    q = context["request"].GET.copy()
    for k, v in kwargs.items():
        if v in (None, ""):
            q.pop(k, None)
        else:
            q[k] = v
    return q.urlencode()


@register.inclusion_tag("partials/ui_field.html")
def ui_field(field, label=None):
    """Kết xuất một trường form Django bằng Tailwind."""
    return {"field": field, "label": label}


@register.filter
def field_widget(field, css="tw-input"):
    """Gán class Tailwind cho widget của trường form."""
    try:
        field.field.widget.attrs["class"] = f'{field.field.widget.attrs.get("class", "")} {css}'.strip()
    except AttributeError:
        pass
    return field
