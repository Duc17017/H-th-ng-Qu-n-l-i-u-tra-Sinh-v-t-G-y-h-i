import logging
from datetime import timedelta

from django.conf import settings
from django.contrib import messages
from django.contrib.auth import login
from django.contrib.auth.decorators import login_required
from django.contrib.auth.views import LoginView, PasswordChangeView, PasswordResetView
from django.shortcuts import get_object_or_404, redirect, render
from django.urls import reverse_lazy
from django.utils import timezone

from core.models import AuditLog, Notification
from core.permissions import ACTIONS, MODULES, landing_url, perm_required
from . import lockout
from .forms import ProfileForm, RegistrationForm
from .models import LoginHistory, RolePermission, User

logger = logging.getLogger(__name__)


class SiteLoginView(LoginView):
    template_name = "registration/login.html"
    redirect_authenticated_user = True

    def get_success_url(self):
        """Ưu tiên `next`; nếu không có thì về trang đầu tiên vai trò được phép xem.

        Trước đây luôn trả về `reports:dashboard` khiến điều tra viên (không có
        quyền module báo cáo) đăng nhập xong bị 403 ngay.
        """
        return self.get_redirect_url() or landing_url(self.request.user)

    def post(self, request, *args, **kwargs):
        """Chặn dò mật khẩu: quá số lần sai cho phép thì tạm khoá theo tài khoản và IP."""
        username = (request.POST.get("username") or "").strip()
        ip = _client_ip(request)
        if lockout.is_locked(username=username, ip=ip):
            wait = lockout.remaining_seconds(username=username, ip=ip)
            messages.error(
                request,
                f"Đăng nhập sai quá {settings.LOGIN_MAX_ATTEMPTS} lần. "
                f"Vui lòng thử lại sau {max(1, wait // 60)} phút.",
            )
            logger.warning("Đăng nhập bị khoá tạm thời: username=%s ip=%s còn=%ss", username, ip, wait)
            return self.render_to_response(self.get_context_data(form=self.get_form()))
        return super().post(request, *args, **kwargs)


class SitePasswordResetView(PasswordResetView):
    """Quên mật khẩu qua email. Luôn trả về cùng một trang kết quả để không lộ email nào có trong hệ thống.

    Tài khoản đăng nhập qua LDAP (không có mật khẩu cục bộ) bị Django tự bỏ qua.
    Giới hạn theo IP để không bị lợi dụng gửi thư hàng loạt.
    """
    template_name = "registration/password_reset_form.html"
    email_template_name = "registration/password_reset_email.txt"
    subject_template_name = "registration/password_reset_subject.txt"
    success_url = reverse_lazy("accounts:password_reset_done")

    def post(self, request, *args, **kwargs):
        from django.core.cache import cache

        key = f"pwreset:{_client_ip(request)}"
        count = cache.get(key, 0)
        if count >= 5:
            messages.error(request, "Bạn đã yêu cầu quá nhiều lần. Vui lòng thử lại sau một giờ.")
            return self.render_to_response(self.get_context_data(form=self.get_form()))
        cache.set(key, count + 1, 3600)
        return super().post(request, *args, **kwargs)


def _client_ip(request):
    """Lấy IP thật khi chạy sau reverse proxy."""
    forwarded = request.META.get("HTTP_X_FORWARDED_FOR", "")
    if forwarded:
        return forwarded.split(",")[0].strip()
    return request.META.get("REMOTE_ADDR")


def register(request):
    """Đăng ký công khai — chỉ tạo được tài khoản Người xem.

    An toàn:
        * Vai trò bị ép về `viewer` trong form, không nhận từ POST.
        * Khoá theo IP nếu đăng ký quá nhiều trong một giờ (chống spam).
        * Ghi LoginHistory + AuditLog để truy vết.
        * Có thể tắt hoàn toàn bằng REGISTRATION_OPEN=0.
    """
    if not getattr(settings, "REGISTRATION_OPEN", True):
        messages.error(request, "Cổng thông tin hiện không mở đăng ký. Vui lòng liên hệ Chi cục để được cấp tài khoản.")
        return redirect("accounts:login")

    if request.user.is_authenticated:
        return redirect(landing_url(request.user))

    ip = _client_ip(request)
    limit = getattr(settings, "REGISTRATION_MAX_PER_IP", 3)
    if ip and LoginHistory.objects.filter(
            event="register", ip_address=ip,
            created_at__gte=timezone.now() - timedelta(hours=1)).count() >= limit:
        messages.error(request, "Đã có quá nhiều đăng ký từ địa chỉ này trong một giờ. Vui lòng thử lại sau.")
        logger.warning("Chặn đăng ký quá nhiều: ip=%s", ip)
        return render(request, "registration/register.html", {"form": RegistrationForm(), "blocked": True})

    form = RegistrationForm(request.POST or None)
    if request.method == "POST" and form.is_valid():
        user = form.save()
        LoginHistory.objects.create(
            user=user, username=user.username, success=True, event="register", ip_address=ip,
            user_agent=(request.META.get("HTTP_USER_AGENT") or "")[:255])
        AuditLog.objects.create(
            user=user, username=user.username, action="register", model_label="accounts.User",
            object_id=str(user.pk), object_repr=user.display_name,
            note="Tự đăng ký từ cổng thông tin", ip_address=ip)
        if user.is_active:
            login(request, user, backend="django.contrib.auth.backends.ModelBackend")
            messages.success(request, "Đã tạo tài khoản. Bạn có thể đọc toàn bộ nội dung cổng thông tin.")
            return redirect(request.POST.get("next") or "cms:post_list")
        messages.success(request, "Đã gửi đăng ký. Tài khoản sẽ dùng được sau khi quản trị viên kích hoạt.")
        return redirect("accounts:login")

    return render(request, "registration/register.html", {"form": form, "next": request.GET.get("next", "")})


class SitePasswordChangeView(PasswordChangeView):
    template_name = "accounts/password_change.html"
    success_url = reverse_lazy("accounts:profile")

    def form_valid(self, form):
        messages.success(self.request, "Đã đổi mật khẩu.")
        return super().form_valid(form)


@login_required
def profile(request):
    form = ProfileForm(request.POST or None, instance=request.user)
    if request.method == "POST" and form.is_valid():
        form.save()
        messages.success(request, "Đã cập nhật thông tin cá nhân.")
        return redirect("accounts:profile")
    return render(request, "accounts/profile.html", {"form": form})


@login_required
def notifications(request):
    qs = Notification.objects.filter(user=request.user)
    if request.method == "POST":
        qs.filter(is_read=False).update(is_read=True)
        return redirect("accounts:notifications")
    return render(request, "accounts/notifications.html", {"items": qs[:100]})


@login_required
def notification_open(request, pk):
    n = get_object_or_404(Notification, pk=pk, user=request.user)
    n.is_read = True
    n.save(update_fields=["is_read"])
    return redirect(n.url or "accounts:notifications")


@perm_required("system", "edit")
def role_matrix(request):
    roles = [r for r in User.ROLES if r[0] != "admin"]
    if request.method == "POST":
        for role, _ in roles:
            for module in MODULES:
                actions = [a for a in ACTIONS if request.POST.get(f"{role}__{module}__{a}")]
                RolePermission.objects.update_or_create(role=role, module=module, defaults={"actions": actions})
        messages.success(request, "Đã lưu ma trận phân quyền.")
        return redirect("accounts:role_matrix")
    current = {(rp.role, rp.module): set(rp.actions) for rp in RolePermission.objects.all()}
    matrix = []
    for role, label in roles:
        mods = []
        for module, mlabel in MODULES.items():
            have = current.get((role, module), set())
            mods.append({"module": module, "label": mlabel,
                         "cells": [{"action": a, "name": f"{role}__{module}__{a}", "on": a in have} for a in ACTIONS]})
        matrix.append({"role": role, "label": label, "mods": mods})
    return render(request, "accounts/role_matrix.html", {"matrix": matrix, "actions": ACTIONS})
