from django.conf import settings
from django.db import models

from core.models import TimeStampedModel


class ReportTemplate(TimeStampedModel):
    KINDS = [
        ("progress", "Tiến độ thực hiện kế hoạch điều tra"),
        ("occurrence", "Tình hình phát sinh, mức độ gây hại"),
        ("area", "Diện tích bị ảnh hưởng theo địa bàn"),
        ("forecast", "Nhận định dự tính, dự báo"),
        ("alert", "Bản tin cảnh báo và kết quả theo dõi"),
    ]
    code = models.CharField("Mã mẫu báo cáo", max_length=30, unique=True)
    name = models.CharField("Tên báo cáo", max_length=200)
    kind = models.CharField("Loại báo cáo", max_length=12, choices=KINDS)
    description = models.TextField("Mô tả", blank=True)
    approved_by = models.CharField("Cơ quan phê duyệt biểu mẫu", max_length=200, blank=True)
    is_active = models.BooleanField("Đang áp dụng", default=True)

    class Meta:
        ordering = ["code"]
        verbose_name = "Mẫu báo cáo"
        verbose_name_plural = "Mẫu báo cáo"

    def __str__(self):
        return self.name


class ReportSchedule(TimeStampedModel):
    FREQ = [("daily", "Hằng ngày"), ("weekly", "Hằng tuần"), ("monthly", "Hằng tháng")]
    FORMATS = [("xlsx", "Excel"), ("pdf", "PDF")]
    name = models.CharField("Tên lịch", max_length=200)
    template = models.ForeignKey(ReportTemplate, on_delete=models.PROTECT, verbose_name="Mẫu báo cáo")
    frequency = models.CharField("Tần suất", max_length=8, choices=FREQ, default="weekly")
    fmt = models.CharField("Định dạng", max_length=4, choices=FORMATS, default="xlsx")
    lookback_days = models.PositiveSmallIntegerField("Số ngày dữ liệu tổng hợp", default=7)
    recipients = models.ManyToManyField(settings.AUTH_USER_MODEL, blank=True, verbose_name="Người nhận")
    send_email = models.BooleanField("Gửi kèm email", default=False)
    is_active = models.BooleanField("Đang chạy", default=True)
    last_run = models.DateTimeField("Lần chạy gần nhất", null=True, blank=True)

    class Meta:
        ordering = ["name"]
        verbose_name = "Lịch tổng hợp, gửi báo cáo"
        verbose_name_plural = "Lịch tổng hợp, gửi báo cáo"

    def __str__(self):
        return self.name


class GeneratedReport(models.Model):
    schedule = models.ForeignKey(ReportSchedule, null=True, blank=True, on_delete=models.SET_NULL)
    template = models.ForeignKey(ReportTemplate, on_delete=models.PROTECT)
    title = models.CharField(max_length=255)
    file = models.FileField(upload_to="reports/%Y/%m/")
    period_from = models.DateField()
    period_to = models.DateField()
    created_by = models.ForeignKey(settings.AUTH_USER_MODEL, null=True, blank=True, on_delete=models.SET_NULL)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["-created_at"]
        verbose_name = "Báo cáo đã kết xuất"
        verbose_name_plural = "Báo cáo đã kết xuất"
