from django.conf import settings
from django.db import models


class TimeStampedModel(models.Model):
    created_at = models.DateTimeField("Ngày tạo", auto_now_add=True)
    updated_at = models.DateTimeField("Ngày cập nhật", auto_now=True)

    class Meta:
        abstract = True


class AuditLog(models.Model):
    """Nhật ký thao tác/cập nhật dữ liệu: ai, lúc nào, thay đổi gì."""

    user = models.ForeignKey(settings.AUTH_USER_MODEL, null=True, blank=True,
                             on_delete=models.SET_NULL, related_name="audit_logs")
    username = models.CharField("Người thực hiện", max_length=150, blank=True)
    action = models.CharField("Hành động", max_length=40, db_index=True)
    model_label = models.CharField("Đối tượng", max_length=100, blank=True, db_index=True)
    object_id = models.CharField(max_length=64, blank=True, db_index=True)
    object_repr = models.CharField("Mô tả", max_length=255, blank=True)
    changes = models.JSONField("Thay đổi", default=dict, blank=True)
    note = models.TextField("Ghi chú", blank=True)
    ip_address = models.GenericIPAddressField("IP", null=True, blank=True)
    created_at = models.DateTimeField("Thời điểm", auto_now_add=True, db_index=True)

    class Meta:
        ordering = ["-created_at", "-id"]
        verbose_name = "Nhật ký thao tác"
        verbose_name_plural = "Nhật ký thao tác"

    def __str__(self):
        return f"{self.created_at:%d/%m/%Y %H:%M} {self.username} {self.action} {self.object_repr}"


class BackgroundTask(models.Model):
    """Hàng đợi tác vụ nền lưu trong database (gửi email, SMS...). Xem core/tasks.py."""

    STATUS = [("pending", "Chờ chạy"), ("running", "Đang chạy"), ("done", "Hoàn tất"), ("failed", "Thất bại")]

    name = models.CharField("Tác vụ", max_length=60, db_index=True)
    payload = models.JSONField("Tham số", default=dict, blank=True)
    status = models.CharField("Trạng thái", max_length=10, choices=STATUS, default="pending", db_index=True)
    attempts = models.PositiveSmallIntegerField("Số lần chạy", default=0)
    max_attempts = models.PositiveSmallIntegerField("Số lần tối đa", default=3)
    run_after = models.DateTimeField("Chạy sau", auto_now_add=True)
    last_error = models.TextField("Lỗi gần nhất", blank=True)
    created_at = models.DateTimeField("Tạo lúc", auto_now_add=True)
    finished_at = models.DateTimeField("Xong lúc", null=True, blank=True)

    class Meta:
        ordering = ["-created_at"]
        verbose_name = "Tác vụ nền"
        verbose_name_plural = "Tác vụ nền"

    def __str__(self):
        return f"{self.name} [{self.status}]"


class Notification(models.Model):
    """Thông báo nội bộ gửi tới cán bộ, đơn vị."""

    user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name="notifications")
    title = models.CharField("Tiêu đề", max_length=255)
    message = models.TextField("Nội dung", blank=True)
    url = models.CharField("Liên kết", max_length=255, blank=True)
    is_read = models.BooleanField("Đã đọc", default=False)
    created_at = models.DateTimeField("Thời điểm", auto_now_add=True)

    class Meta:
        ordering = ["-created_at"]
        verbose_name = "Thông báo"
        verbose_name_plural = "Thông báo"

    def __str__(self):
        return self.title
