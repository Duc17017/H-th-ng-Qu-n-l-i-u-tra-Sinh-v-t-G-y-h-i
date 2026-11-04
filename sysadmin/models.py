from django.conf import settings
from django.db import models

from core.models import TimeStampedModel


class SystemConfig(TimeStampedModel):
    key = models.CharField("Khóa cấu hình", max_length=100, unique=True)
    value = models.TextField("Giá trị", blank=True)
    description = models.CharField("Mô tả", max_length=255, blank=True)

    class Meta:
        ordering = ["key"]
        verbose_name = "Cấu hình hệ thống"
        verbose_name_plural = "Cấu hình hệ thống"

    def __str__(self):
        return self.key


class Document(TimeStampedModel):
    KINDS = [("guide", "Tài liệu hướng dẫn"), ("process", "Quy trình kỹ thuật"), ("ref", "Tài liệu tham chiếu")]
    code = models.CharField("Mã tài liệu", max_length=40, unique=True)
    title = models.CharField("Tên tài liệu", max_length=255)
    kind = models.CharField("Loại", max_length=8, choices=KINDS, default="guide")
    description = models.TextField("Mô tả", blank=True)
    current_version = models.CharField("Phiên bản áp dụng", max_length=20, blank=True)

    class Meta:
        ordering = ["code"]
        verbose_name = "Tài liệu"
        verbose_name_plural = "Tài liệu"

    def __str__(self):
        return f"{self.code} - {self.title}"

    def current(self):
        return self.versions.filter(is_current=True).first() or self.versions.first()


class DocumentVersion(TimeStampedModel):
    document = models.ForeignKey(Document, on_delete=models.CASCADE, related_name="versions", verbose_name="Tài liệu")
    version = models.CharField("Phiên bản", max_length=20)
    file = models.FileField("Tệp", upload_to="documents/%Y/%m/")
    issued_date = models.DateField("Ngày ban hành", null=True, blank=True)
    note = models.CharField("Ghi chú thay đổi", max_length=255, blank=True)
    is_current = models.BooleanField("Đang áp dụng", default=False)

    class Meta:
        ordering = ["-created_at", "-id"]
        unique_together = ("document", "version")
        verbose_name = "Phiên bản tài liệu"
        verbose_name_plural = "Phiên bản tài liệu"

    def __str__(self):
        return f"{self.document.code} v{self.version}"

    def save(self, *args, **kwargs):
        super().save(*args, **kwargs)
        if self.is_current:
            DocumentVersion.objects.filter(document=self.document).exclude(pk=self.pk).update(is_current=False)
            Document.objects.filter(pk=self.document_id).update(current_version=self.version)


class BackupRecord(models.Model):
    ACTIONS = [("backup", "Sao lưu"), ("restore", "Khôi phục")]
    action = models.CharField(max_length=10, choices=ACTIONS)
    filename = models.CharField(max_length=255)
    size_bytes = models.BigIntegerField(default=0)
    success = models.BooleanField(default=False)
    message = models.TextField(blank=True)
    created_by = models.ForeignKey(settings.AUTH_USER_MODEL, null=True, blank=True, on_delete=models.SET_NULL)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["-created_at"]
        verbose_name = "Lịch sử sao lưu"
        verbose_name_plural = "Lịch sử sao lưu"
