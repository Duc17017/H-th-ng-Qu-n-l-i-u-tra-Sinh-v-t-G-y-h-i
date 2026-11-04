from django.core.exceptions import PermissionDenied
from django.contrib.auth.views import redirect_to_login
from functools import wraps

MODULES = {
    "cms": "Trang thông tin",
    "catalog": "Danh mục chuyên môn",
    "plans": "Kế hoạch điều tra",
    "records": "Dữ liệu hiện trường",
    "data": "Tổng hợp dữ liệu",
    "map": "Bản đồ GIS",
    "forecast": "Dự tính, dự báo",
    "alert": "Cảnh báo",
    "report": "Báo cáo, bảng điều hành",
    "system": "Quản trị hệ thống",
}
ACTIONS = {
    "view": "Xem",
    "create": "Tạo mới",
    "edit": "Chỉnh sửa",
    "confirm": "Xác nhận",
    "approve": "Phê duyệt",
    "export": "Kết xuất",
}


def _all():
    return {m: set(ACTIONS) for m in MODULES}


def perm_map(user):
    if not getattr(user, "is_authenticated", False):
        return {}
    cached = getattr(user, "_perm_map", None)
    if cached is not None:
        return cached
    if user.is_superuser or user.role == "admin":
        result = _all()
    else:
        from accounts.models import RolePermission

        result = {m: set() for m in MODULES}
        for rp in RolePermission.objects.filter(role=user.role):
            result[rp.module] = set(rp.actions or [])
    user._perm_map = result
    return result


def has_perm(user, module, action="view"):
    return action in perm_map(user).get(module, set())


def perm_required(module, action="view"):
    def deco(view):
        @wraps(view)
        def wrapper(request, *args, **kwargs):
            if not request.user.is_authenticated:
                return redirect_to_login(request.get_full_path())
            if not has_perm(request.user, module, action):
                raise PermissionDenied
            return view(request, *args, **kwargs)

        return wrapper

    return deco


def division_ids_for(user):
    """None = không giới hạn; ngược lại là danh sách id địa bàn được phép (gồm địa bàn con)."""
    if not user.is_authenticated or user.is_superuser or user.role == "admin" or not user.division_id:
        return None
    return user.division.descendant_ids()


def scope_qs(user, qs, field):
    ids = division_ids_for(user)
    if ids is None:
        return qs
    return qs.filter(**{f"{field}__in": ids})


# Trang đích sau khi đăng nhập, theo thứ tự ưu tiên. Chỉ chọn trang mà vai trò
# thực sự có quyền xem, tránh việc vừa đăng nhập đã bị 403.
LANDING_ROUTES = [
    ("report", "view", "reports:dashboard"),
    ("plans", "view", "surveys:task_list"),
    ("records", "view", "surveys:record_list"),
    ("map", "view", "mapview:map"),
    ("forecast", "view", "forecasts:list"),
    ("alert", "view", "alerts:alert_list"),
    ("cms", "view", "cms:manage_list"),
    ("catalog", "view", "catalog:index"),
    ("system", "view", "sysadmin:index"),
]


def landing_url(user):
    """URL đầu tiên người dùng được phép vào, dùng làm đích sau khi đăng nhập."""
    from django.urls import NoReverseMatch, reverse

    for module, action, url_name in LANDING_ROUTES:
        if has_perm(user, module, action):
            try:
                return reverse(url_name)
            except NoReverseMatch:
                continue
    return reverse("cms:home")
