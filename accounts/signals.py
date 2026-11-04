"""Ghi nhật ký đăng nhập / đăng xuất.

Phải khai báo hàm ở cấp module. Nếu định nghĩa closure bên trong
`AppConfig.ready()` thì Django chỉ giữ weak reference tới receiver — không còn
ai tham chiếu tới closure nên nó bị garbage collector thu hồi ngay, và nhật ký
đăng nhập lặng lẽ không ghi được gì.
"""
from django.contrib.auth.signals import user_logged_in, user_logged_out, user_login_failed
from django.dispatch import receiver

from .models import LoginHistory


def _ip(request):
    return request.META.get("REMOTE_ADDR") if request else None


def _ua(request):
    return request.META.get("HTTP_USER_AGENT", "")[:255] if request else ""


@receiver(user_logged_in, dispatch_uid="lh_login")
def on_login(sender, request, user, **kw):
    LoginHistory.objects.create(user=user, username=user.username, success=True, event="login",
                                ip_address=_ip(request), user_agent=_ua(request))


@receiver(user_logged_out, dispatch_uid="lh_logout")
def on_logout(sender, request, user, **kw):
    if user:
        LoginHistory.objects.create(user=user, username=user.username, success=True, event="logout",
                                    ip_address=_ip(request), user_agent=_ua(request))


@receiver(user_login_failed, dispatch_uid="lh_failed")
def on_fail(sender, credentials, request=None, **kw):
    LoginHistory.objects.create(username=str(credentials.get("username", ""))[:150], success=False,
                                event="login", ip_address=_ip(request), user_agent=_ua(request))
