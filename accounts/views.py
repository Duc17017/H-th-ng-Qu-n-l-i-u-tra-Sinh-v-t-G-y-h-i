import logging

from django.conf import settings
from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.contrib.auth.views import LoginView, PasswordChangeView
from django.shortcuts import get_object_or_404, redirect, render
from django.urls import reverse_lazy

from core.models import Notification
from core.permissions import ACTIONS, MODULES, landing_url, perm_required
from . import lockout
from .forms import ProfileForm
from .models import RolePermission, User

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


def _client_ip(request):
    """Lấy IP thật khi chạy sau reverse proxy."""
    forwarded = request.META.get("HTTP_X_FORWARDED_FOR", "")
    if forwarded:
        return forwarded.split(",")[0].strip()
    return request.META.get("REMOTE_ADDR")


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
