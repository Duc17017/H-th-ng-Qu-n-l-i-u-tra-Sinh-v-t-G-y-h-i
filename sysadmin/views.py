from django.contrib import messages
from django.core.paginator import Paginator
from django.http import FileResponse, Http404
from django.shortcuts import get_object_or_404, redirect, render

from accounts.models import LoginHistory
from core.models import AuditLog
from core.permissions import perm_required
from . import backup as bk
from . import forms as f
from . import models as m


@perm_required("system", "view")
def index(request):
    links = [
        ("Người dùng", "/accounts/users/", "Tài khoản, trạng thái hoạt động, vai trò, đơn vị, địa bàn"),
        ("Phân quyền theo vai trò", "/accounts/roles/", "Quyền xem, tạo, sửa, xác nhận, phê duyệt, kết xuất"),
        ("Đơn vị", "/accounts/units/", "Danh mục đơn vị thực hiện"),
        ("Địa bàn hành chính", "/accounts/divisions/", "Tỉnh, huyện, xã"),
        ("Danh mục chuyên môn", "/catalog/", "Cây trồng, sinh vật gây hại, giai đoạn, phương pháp, chỉ tiêu"),
        ("Biểu mẫu điều tra", "/surveys/templates/", "Cấu hình trường theo cây trồng, đối tượng, phương pháp"),
        ("Mẫu báo cáo", "/reports/templates/", "Biểu mẫu báo cáo được phê duyệt"),
        ("Lịch gửi báo cáo", "/reports/schedules/", "Tổng hợp, gửi báo cáo tự động"),
        ("Lớp bản đồ liên kết", "/map/layers/", "Kế thừa dịch vụ GIS hiện có của tỉnh"),
        ("Tài liệu, quy trình", "/system/documents/", "Phiên bản áp dụng"),
        ("Cấu hình hệ thống", "/system/configs/", "Tham số hệ thống"),
        ("Nhật ký thao tác", "/system/audit/", "Lịch sử cập nhật và phê duyệt dữ liệu"),
        ("Lịch sử đăng nhập", "/system/logins/", "Đăng nhập thành công và thất bại"),
        ("Sao lưu, khôi phục", "/system/backups/", "pg_dump / pg_restore"),
    ]
    return render(request, "sysadmin/index.html", {"links": links, **_admin_cockpit(request)})


def _admin_cockpit(request):
    """Số liệu thật cho giao diện Phân hệ 9: tài khoản, ma trận quyền, danh mục, nhật ký, sao lưu."""
    from datetime import timedelta

    from django.db.models import Count, Q
    from django.utils import timezone

    from accounts.models import RolePermission, Unit, User
    from catalog import models as cat
    from core.permissions import ACTIONS, MODULES
    from forecasts.models import Threshold

    g = request.GET
    users = User.objects.select_related("unit", "division").order_by("-is_active", "username")
    if g.get("q"):
        q = g["q"]
        users = users.filter(Q(username__icontains=q) | Q(first_name__icontains=q) | Q(last_name__icontains=q) | Q(email__icontains=q))
    if g.get("unit"):
        users = users.filter(unit_id=g["unit"])
    if g.get("role"):
        users = users.filter(role=g["role"])
    page = Paginator(users, 8).get_page(g.get("page"))

    total_users = User.objects.count()
    active_users = User.objects.filter(is_active=True).count()
    with_division = User.objects.filter(is_active=True, division__isnull=False).count()
    since = timezone.now() - timedelta(minutes=30)
    online = LoginHistory.objects.filter(success=True, event="login", created_at__gte=since).values("user").distinct().count()

    # Ma trận quyền của vai trò đang xem (đọc thẳng từ bảng RolePermission trong DB)
    roles = [r for r in User.ROLES if r[0] != "admin"]
    sel_role = g.get("view_role") if g.get("view_role") in dict(roles) else (roles[0][0] if roles else "")
    stored = {rp.module: set(rp.actions) for rp in RolePermission.objects.filter(role=sel_role)}
    role_matrix = [{"module": k, "label": v, "cells": [{"label": ACTIONS[a], "on": a in stored.get(k, set())} for a in ACTIONS]}
                   for k, v in MODULES.items()]
    perm_count = sum(len(a) for a in RolePermission.objects.values_list("actions", flat=True))

    last_backup = m.BackupRecord.objects.filter(action="backup").order_by("-created_at").first()
    fails_24h = LoginHistory.objects.filter(success=False, created_at__gte=timezone.now() - timedelta(hours=24)).count()

    return {
        "page": page, "g": g,
        "units": Unit.objects.filter(is_active=True), "roles_all": User.ROLES,
        "kpi": {
            "total_users": total_users, "active_users": active_users, "online": online,
            "coverage": round(with_division * 100 / active_users) if active_users else 0,
            "units": Unit.objects.filter(is_active=True).count(),
            "role_count": len(User.ROLES), "perm_count": perm_count,
            "pests": cat.PestSpecies.objects.count(), "crops": cat.Crop.objects.count(),
            "stages": cat.GrowthStage.objects.count(), "thresholds": Threshold.objects.filter(is_active=True).count(),
            "last_backup": last_backup, "fails_24h": fails_24h,
        },
        "role_choices": roles, "sel_role": sel_role, "sel_role_label": dict(roles).get(sel_role, ""),
        "role_matrix": role_matrix,
        "top_pests": cat.PestSpecies.objects.filter(is_active=True).annotate(n=Count("crops"))[:4],
        "stages": cat.GrowthStage.objects.filter(is_active=True).select_related("crop")[:4],
        "thresholds": Threshold.objects.filter(is_active=True).select_related("pest")[:3],
        "audit": AuditLog.objects.all()[:8],
        "logins": LoginHistory.objects.filter(success=False)[:3],
    }


@perm_required("system", "view")
def audit_log(request):
    qs = AuditLog.objects.all()
    g = request.GET
    if g.get("user"):
        qs = qs.filter(username__icontains=g["user"])
    if g.get("action"):
        qs = qs.filter(action__icontains=g["action"])
    if g.get("model"):
        qs = qs.filter(model_label__icontains=g["model"])
    if g.get("date_from"):
        qs = qs.filter(created_at__date__gte=g["date_from"])
    if g.get("date_to"):
        qs = qs.filter(created_at__date__lte=g["date_to"])
    return render(request, "sysadmin/audit_log.html", {"page": Paginator(qs, 50).get_page(g.get("page")), "g": g})


@perm_required("system", "view")
def login_history(request):
    qs = LoginHistory.objects.all()
    if request.GET.get("user"):
        qs = qs.filter(username__icontains=request.GET["user"])
    if request.GET.get("failed"):
        qs = qs.filter(success=False)
    return render(request, "sysadmin/login_history.html", {"page": Paginator(qs, 50).get_page(request.GET.get("page"))})


@perm_required("system", "view")
def documents(request):
    return render(request, "sysadmin/documents.html", {"docs": m.Document.objects.prefetch_related("versions")})


@perm_required("system", "view")
def document_download(request, pk):
    v = get_object_or_404(m.DocumentVersion, pk=pk)
    try:
        return FileResponse(v.file.open("rb"), as_attachment=True, filename=v.file.name.rsplit("/", 1)[-1])
    except FileNotFoundError:
        raise Http404


@perm_required("system", "edit")
def backups(request):
    restore_form = f.ConfirmRestoreForm()
    if request.method == "POST":
        action = request.POST.get("action")
        try:
            if action == "backup":
                name = bk.create_backup(request.user)
                messages.success(request, f"Đã sao lưu: {name}")
            elif action == "restore":
                restore_form = f.ConfirmRestoreForm(request.POST)
                if restore_form.is_valid():
                    bk.restore_backup(restore_form.cleaned_data["name"], request.user)
                    messages.success(request, "Đã khôi phục dữ liệu. Hãy đăng nhập lại và kiểm tra.")
                else:
                    messages.error(request, "Cần gõ đúng cụm xác nhận để khôi phục.")
                    return redirect("sysadmin:backups")
        except bk.BackupError as e:
            messages.error(request, str(e))
        except Exception:
            messages.error(request, "Không thực hiện được thao tác sao lưu/khôi phục.")
        return redirect("sysadmin:backups")
    return render(request, "sysadmin/backups.html", {
        "files": bk.list_backups(), "history": m.BackupRecord.objects.select_related("created_by")[:20]})


@perm_required("system", "edit")
def backup_download(request, name):
    if not bk.SAFE_NAME.match(name):
        raise Http404
    path = bk.backup_dir() / name
    if not path.is_file():
        raise Http404
    return FileResponse(open(path, "rb"), as_attachment=True, filename=name)
