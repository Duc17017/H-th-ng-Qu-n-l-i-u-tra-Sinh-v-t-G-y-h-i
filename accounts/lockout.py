"""Chống dò mật khẩu (brute-force) dựa trên LoginHistory.

Không cần thêm bảng mới: đếm các lần đăng nhập thất bại gần đây của cùng một
tài khoản hoặc cùng một địa chỉ IP trong khoảng thời gian khoá.
"""
from datetime import timedelta

from django.conf import settings
from django.utils import timezone

from .models import LoginHistory


def _window():
    return timezone.now() - timedelta(seconds=getattr(settings, "LOGIN_LOCKOUT_SECONDS", 900))


def _max_attempts():
    return getattr(settings, "LOGIN_MAX_ATTEMPTS", 5)


def failed_recently(username=None, ip=None):
    """Số lần đăng nhập thất bại trong khoảng thời gian khoá."""
    from django.db.models import Q

    q = Q()
    if username:
        q |= Q(username=username)
    if ip:
        q |= Q(ip_address=ip)
    if not q:
        return 0
    return LoginHistory.objects.filter(
        success=False, event="login", created_at__gte=_window()).filter(q).count()


def is_locked(username=None, ip=None):
    """True nếu đã vượt ngưỡng đăng nhập sai và còn trong thời gian khoá."""
    return failed_recently(username, ip) >= _max_attempts()


def remaining_seconds(username=None, ip=None):
    """Số giây còn bị khoá (0 nếu không khoá)."""
    from django.db.models import Q

    q = Q()
    if username:
        q |= Q(username=username)
    if ip:
        q |= Q(ip_address=ip)
    if not q:
        return 0
    last = (LoginHistory.objects
            .filter(success=False, event="login", created_at__gte=_window())
            .filter(q)
            .order_by("-created_at")
            .values_list("created_at", flat=True)
            .first())
    if not last:
        return 0
    unlock_at = last + timedelta(seconds=getattr(settings, "LOGIN_LOCKOUT_SECONDS", 900))
    left = int((unlock_at - timezone.now()).total_seconds())
    return max(0, left)
