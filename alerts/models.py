from django.conf import settings
from django.core.exceptions import ValidationError
from django.db import models
from django.utils import timezone

from accounts.models import AdminDivision, Unit
from catalog import models as cat
from core.models import TimeStampedModel
from forecasts.models import RISK_LEVELS, Forecast


class Alert(TimeStampedModel):
    STATUSES = [("draft", "Dự thảo"), ("pending", "Chờ phê duyệt"), ("published", "Đã phát hành"),
                ("updated", "Đã cập nhật"), ("expired", "Hết hiệu lực")]
    CHANNELS = [("web", "Trang thông tin"), ("notify", "Thông báo nội bộ"), ("email", "Email"), ("sms", "Tin nhắn SMS")]
    code = models.CharField("Số hiệu bản tin", max_length=40, unique=True)
    title = models.CharField("Tiêu đề", max_length=255)
    pest = models.ForeignKey(cat.PestSpecies, on_delete=models.PROTECT, verbose_name="Sinh vật gây hại")
    crop = models.ForeignKey(cat.Crop, on_delete=models.PROTECT, verbose_name="Cây trồng")
    divisions = models.ManyToManyField(AdminDivision, verbose_name="Phạm vi địa bàn")
    valid_from = models.DateField("Hiệu lực từ")
    valid_to = models.DateField("Hiệu lực đến")
    risk_level = models.CharField("Mức độ nguy cơ", max_length=10, choices=RISK_LEVELS, default="medium")
    forecast = models.ForeignKey(Forecast, null=True, blank=True, on_delete=models.PROTECT, verbose_name="Nhận định dự báo")
    basis = models.TextField("Căn cứ nhận định")
    guidance = models.TextField("Hướng dẫn phòng trừ")
    recipient_units = models.ManyToManyField(Unit, blank=True, verbose_name="Đơn vị nhận")
    channels = models.JSONField("Kênh phát hành", default=list, blank=True)
    status = models.CharField("Trạng thái", max_length=10, choices=STATUSES, default="draft", db_index=True)
    version = models.PositiveSmallIntegerField("Lần ban hành", default=1)
    created_by = models.ForeignKey(settings.AUTH_USER_MODEL, null=True, on_delete=models.SET_NULL,
                                   related_name="alerts_created", verbose_name="Người soạn")
    approved_by = models.ForeignKey(settings.AUTH_USER_MODEL, null=True, blank=True, on_delete=models.SET_NULL,
                                    related_name="alerts_approved", verbose_name="Người phê duyệt")
    published_at = models.DateTimeField("Thời điểm phát hành", null=True, blank=True)
    review_note = models.TextField("Ý kiến phê duyệt", blank=True)

    class Meta:
        ordering = ["-created_at", "-id"]
        verbose_name = "Bản tin cảnh báo"
        verbose_name_plural = "Bản tin cảnh báo"

    def __str__(self):
        return f"{self.code} - {self.title}"

    def clean(self):
        if self.valid_from and self.valid_to and self.valid_to < self.valid_from:
            raise ValidationError("Hiệu lực đến phải sau hiệu lực từ.")

    @property
    def editable(self):
        return self.status in ("draft", "updated")

    @property
    def is_live(self):
        today = timezone.localdate()
        return self.status in ("published", "updated") and self.valid_from <= today <= self.valid_to

    def channel_names(self):
        d = dict(self.CHANNELS)
        return [d.get(c, c) for c in (self.channels or [])]


class AlertRevision(models.Model):
    """Lịch sử biên tập, phê duyệt, phát hành, điều chỉnh bản tin."""

    alert = models.ForeignKey(Alert, on_delete=models.CASCADE, related_name="revisions")
    action = models.CharField("Hành động", max_length=30)
    version = models.PositiveSmallIntegerField(default=1)
    snapshot = models.JSONField(default=dict)
    note = models.TextField(blank=True)
    user = models.ForeignKey(settings.AUTH_USER_MODEL, null=True, on_delete=models.SET_NULL)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["-created_at", "-id"]


class FollowUpTask(TimeStampedModel):
    STATUSES = [("assigned", "Đã giao"), ("doing", "Đang thực hiện"), ("done", "Hoàn thành")]
    alert = models.ForeignKey(Alert, on_delete=models.CASCADE, related_name="followups", verbose_name="Bản tin")
    title = models.CharField("Nội dung nhiệm vụ", max_length=255)
    division = models.ForeignKey(AdminDivision, null=True, blank=True, on_delete=models.PROTECT, verbose_name="Địa bàn")
    unit = models.ForeignKey(Unit, null=True, blank=True, on_delete=models.PROTECT, verbose_name="Đơn vị thực hiện")
    assignee = models.ForeignKey(settings.AUTH_USER_MODEL, null=True, blank=True, on_delete=models.SET_NULL,
                                 related_name="followups", verbose_name="Cán bộ phụ trách")
    due_date = models.DateField("Hạn hoàn thành")
    status = models.CharField("Trạng thái", max_length=10, choices=STATUSES, default="assigned")
    result = models.TextField("Kết quả kiểm tra thực tế", blank=True)
    area_treated = models.FloatField("Diện tích đã phòng trừ (ha)", null=True, blank=True)
    rate_after = models.FloatField("Tỷ lệ hại sau xử lý (%)", null=True, blank=True)
    effectiveness = models.CharField("Đánh giá hiệu quả", max_length=10, blank=True,
                                     choices=[("good", "Tốt"), ("fair", "Trung bình"), ("poor", "Chưa hiệu quả")])
    completed_at = models.DateTimeField("Hoàn thành lúc", null=True, blank=True)

    class Meta:
        ordering = ["due_date", "id"]
        verbose_name = "Nhiệm vụ theo dõi sau cảnh báo"
        verbose_name_plural = "Nhiệm vụ theo dõi sau cảnh báo"

    def __str__(self):
        return self.title

    @property
    def overdue(self):
        return self.status != "done" and self.due_date < timezone.localdate()

    def clean(self):
        if self.rate_after is not None and not 0 <= self.rate_after <= 100:
            raise ValidationError("Tỷ lệ hại sau xử lý phải trong khoảng 0–100%.")
        if self.area_treated is not None and self.area_treated < 0:
            raise ValidationError("Diện tích đã phòng trừ không được âm.")
