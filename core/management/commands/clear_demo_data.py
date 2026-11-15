"""Xóa dữ liệu mẫu/dữ liệu phát sinh, giữ lại phần chức năng của hệ thống.

Giữ lại: phân quyền theo vai trò, tài khoản admin, danh mục chuyên môn (cây trồng, sinh vật,
mức độ hại...), chuyên mục bài viết, biểu mẫu, mẫu báo cáo, lớp bản đồ, ngưỡng, cấu hình hệ thống.
Xóa: người dùng khác admin, địa bàn/đơn vị, kế hoạch, điểm, nhiệm vụ, phiếu điều tra, thời tiết,
dự báo, cảnh báo, báo cáo đã tạo, bài viết, thông báo, nhật ký.

Dùng:  python manage.py clear_demo_data --yes
"""
import json
from pathlib import Path

from django.apps import apps
from django.conf import settings
from django.core import serializers
from django.core.management.base import BaseCommand, CommandError
from django.db import transaction
from django.db.models import ProtectedError
from django.utils import timezone

# Thứ tự: bảng con trước, bảng cha sau.
TARGETS = [
    "surveys.RecordHistory", "surveys.SurveyRecord", "surveys.SurveyTask", "surveys.SurveyRoute",
    "surveys.SurveyPoint", "surveys.SurveyPlan",
    "alerts.AlertRevision", "alerts.FollowUpTask", "alerts.Alert",
    "forecasts.Forecast", "forecasts.WeatherData",
    "reports.GeneratedReport", "reports.ReportSchedule",
    "cms.PostRevision", "cms.Post",
    "sysadmin.BackupRecord",
    "core.Notification",
    "accounts.User", "accounts.Unit", "accounts.AdminDivision",
]

# Danh mục dùng chung: chỉ xóa khi có --catalogs.
CATALOGS = [
    "surveys.FormField", "surveys.FormTemplate", "forecasts.Threshold", "mapview.ExternalLayer",
    "catalog.Season", "catalog.PestSpecies", "catalog.GrowthStage", "catalog.SurveyIndicator",
    "catalog.SurveyMethod", "catalog.MeasureUnit", "catalog.DamageLevel", "catalog.Crop", "cms.Category",
]

# Xóa sau cùng: các lần xóa ở trên tự ghi thêm nhật ký.
LOGS = ["core.AuditLog", "accounts.LoginHistory"]


class Command(BaseCommand):
    help = "Xóa dữ liệu mẫu, chỉ giữ chức năng, phân quyền và tài khoản admin."

    def add_arguments(self, parser):
        parser.add_argument("--yes", action="store_true", help="Xác nhận xóa (bắt buộc).")
        parser.add_argument("--catalogs", action="store_true",
                            help="Xóa luôn danh mục (cây trồng, sinh vật, mức độ hại, chuyên mục, biểu mẫu...).")
        parser.add_argument("--no-backup", action="store_true", help="Không ghi tệp sao lưu JSON trước khi xóa.")

    @staticmethod
    def _delete_all(model, qs):
        """Xóa hết qs. Bảng có khóa cha PROTECT (Unit, AdminDivision) thì xóa từ lá lên gốc."""
        if not any(f.name == "parent" for f in model._meta.fields):
            return qs.delete()[0]
        total = 0
        for _ in range(20):
            ids = list(qs.values_list("pk", flat=True))
            if not ids:
                return total
            leaves = qs.exclude(pk__in=model.objects.filter(parent__in=ids).values("parent"))
            try:
                total += leaves.delete()[0]
            except ProtectedError as exc:
                raise CommandError(f"{model._meta.label} còn được dùng bởi {len(exc.protected_objects)} bản ghi khác.")
        raise CommandError(f"Không xóa hết {model._meta.label}: cây cha–con quá sâu.")

    def handle(self, *args, **opts):
        if not opts["yes"]:
            raise CommandError("Lệnh này xóa dữ liệu vĩnh viễn. Chạy lại với --yes để xác nhận.")

        labels = TARGETS + (CATALOGS if opts["catalogs"] else []) + LOGS
        models = [apps.get_model(label) for label in labels]
        User = apps.get_model("accounts.User")

        def queryset(model):
            qs = model.objects.all()
            return qs.exclude(username="admin") if model is User else qs

        if not User.objects.filter(username="admin").exists():
            raise CommandError("Không có tài khoản 'admin'; dừng lại để tránh khóa mất quyền đăng nhập.")

        if not opts["no_backup"]:
            out_dir = Path(settings.BASE_DIR, "backups")
            out_dir.mkdir(exist_ok=True)
            path = out_dir / f"truoc_khi_xoa_{timezone.now():%Y%m%d_%H%M%S}.json"
            objs = [o for m in reversed(models) for o in queryset(m)]
            path.write_text(serializers.serialize("json", objs, ensure_ascii=False), encoding="utf-8")
            self.stdout.write(f"Đã sao lưu {len(objs)} bản ghi vào {path}")

        with transaction.atomic():
            for model in models:
                total = self._delete_all(model, queryset(model))
                if total:
                    self.stdout.write(f"  {model._meta.label}: xóa {total}")

        kept = "tài khoản admin, phân quyền" + ("" if opts["catalogs"] else " và các danh mục")
        self.stdout.write(self.style.SUCCESS(f"Xong. Còn lại {kept}."))
