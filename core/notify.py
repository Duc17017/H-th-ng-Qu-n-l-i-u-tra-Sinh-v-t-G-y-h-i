from django.contrib.auth import get_user_model

from .models import Notification


def notify(users, title, message="", url=""):
    """Gửi thông báo nội bộ; bỏ qua người dùng trùng/không hợp lệ."""
    seen = set()
    for u in users:
        if u is None or u.pk in seen:
            continue
        seen.add(u.pk)
        Notification.objects.create(user=u, title=title[:255], message=message, url=url)


def users_with_perm(module, action, division_ids=None):
    """Người dùng đang hoạt động có quyền (module, action); có thể giới hạn theo địa bàn."""
    from accounts.models import RolePermission

    User = get_user_model()
    roles = {"admin"}
    for rp in RolePermission.objects.filter(module=module):
        if action in (rp.actions or []):
            roles.add(rp.role)
    qs = User.objects.filter(is_active=True, role__in=roles)
    if division_ids is not None:
        from django.db.models import Q

        qs = qs.filter(Q(division__isnull=True) | Q(division_id__in=division_ids))
    return list(qs)
