from django.conf import settings
from django.core.exceptions import ValidationError
from django.db import models

from accounts.models import AdminDivision
from catalog import models as cat
from core.models import TimeStampedModel

RISK_LEVELS = [("low", "Thấp"), ("medium", "Trung bình"), ("high", "Cao"), ("very_high", "Rất cao")]


class WeatherData(TimeStampedModel):
    SOURCES = [("manual", "Nhập tay"), ("excel", "Nhập từ Excel"), ("api", "Nguồn dữ liệu liên kết")]
    division = models.ForeignKey(AdminDivision, on_delete=models.PROTECT, verbose_name="Địa bàn")
    date = models.DateField("Ngày")
    temp_avg = models.FloatField("Nhiệt độ TB (°C)", null=True, blank=True)
    temp_min = models.FloatField("Nhiệt độ thấp nhất (°C)", null=True, blank=True)
    temp_max = models.FloatField("Nhiệt độ cao nhất (°C)", null=True, blank=True)
    humidity = models.FloatField("Độ ẩm TB (%)", null=True, blank=True)
    rainfall = models.FloatField("Lượng mưa (mm)", null=True, blank=True)
    source = models.CharField("Nguồn dữ liệu", max_length=10, choices=SOURCES, default="manual")
    source_note = models.CharField("Đơn vị cung cấp", max_length=200, blank=True)

    class Meta:
        ordering = ["-date"]
        unique_together = ("division", "date")
        verbose_name = "Dữ liệu thời tiết"
        verbose_name_plural = "Dữ liệu thời tiết"

    def __str__(self):
        return f"{self.division} {self.date:%d/%m/%Y}"

    def clean(self):
        if self.humidity is not None and not 0 <= self.humidity <= 100:
            raise ValidationError("Độ ẩm phải trong khoảng 0–100%.")
        if self.rainfall is not None and self.rainfall < 0:
            raise ValidationError("Lượng mưa không được âm.")
        if self.temp_min is not None and self.temp_max is not None and self.temp_max < self.temp_min:
            raise ValidationError("Nhiệt độ cao nhất phải lớn hơn hoặc bằng nhiệt độ thấp nhất.")


class Threshold(TimeStampedModel):
    """Ngưỡng chuyên môn do cơ quan chuyên môn phê duyệt để đánh giá nguy cơ."""

    METRICS = [("damage_rate", "Tỷ lệ hại TB (%)"), ("density", "Mật độ TB"), ("affected_area", "Diện tích bị hại (ha)")]
    name = models.CharField("Tên tiêu chí", max_length=200)
    crop = models.ForeignKey(cat.Crop, null=True, blank=True, on_delete=models.PROTECT, verbose_name="Cây trồng")
    pest = models.ForeignKey(cat.PestSpecies, on_delete=models.PROTECT, verbose_name="Sinh vật gây hại")
    stage = models.ForeignKey(cat.GrowthStage, null=True, blank=True, on_delete=models.PROTECT, verbose_name="Giai đoạn")
    metric = models.CharField("Chỉ tiêu đánh giá", max_length=20, choices=METRICS, default="damage_rate")
    medium_from = models.FloatField("Ngưỡng nguy cơ trung bình từ")
    high_from = models.FloatField("Ngưỡng nguy cơ cao từ")
    very_high_from = models.FloatField("Ngưỡng nguy cơ rất cao từ")
    weather_condition = models.TextField("Điều kiện thời tiết thuận lợi phát sinh", blank=True)
    temp_min = models.FloatField("Nhiệt độ TB thuận lợi từ (°C)", null=True, blank=True)
    temp_max = models.FloatField("Nhiệt độ TB thuận lợi đến (°C)", null=True, blank=True)
    humidity_min = models.FloatField("Độ ẩm thuận lợi từ (%)", null=True, blank=True)
    basis = models.CharField("Căn cứ ban hành (văn bản, quy trình)", max_length=255, blank=True)
    approved_by = models.CharField("Cơ quan phê duyệt", max_length=200, blank=True)
    effective_from = models.DateField("Có hiệu lực từ", null=True, blank=True)
    is_active = models.BooleanField("Đang áp dụng", default=True)

    class Meta:
        ordering = ["pest__name", "name"]
        verbose_name = "Ngưỡng, tiêu chí nguy cơ"
        verbose_name_plural = "Ngưỡng, tiêu chí nguy cơ"

    def __str__(self):
        return self.name

    def clean(self):
        if not (self.medium_from <= self.high_from <= self.very_high_from):
            raise ValidationError("Các ngưỡng phải tăng dần: trung bình ≤ cao ≤ rất cao.")

    def evaluate(self, value):
        if value is None:
            return None
        if value >= self.very_high_from:
            return "very_high"
        if value >= self.high_from:
            return "high"
        if value >= self.medium_from:
            return "medium"
        return "low"


class Forecast(TimeStampedModel):
    STATUSES = [("draft", "Dự thảo"), ("pending", "Chờ xác nhận"), ("confirmed", "Đã xác nhận"),
                ("rejected", "Không thông qua")]
    ORIGINS = [("manual", "Chuyên môn lập"), ("auto", "Gợi ý tự động")]
    title = models.CharField("Tiêu đề nhận định", max_length=255)
    pest = models.ForeignKey(cat.PestSpecies, on_delete=models.PROTECT, verbose_name="Sinh vật gây hại")
    crop = models.ForeignKey(cat.Crop, on_delete=models.PROTECT, verbose_name="Cây trồng")
    division = models.ForeignKey(AdminDivision, on_delete=models.PROTECT, verbose_name="Phạm vi dự báo (địa bàn)")
    stage = models.ForeignKey(cat.GrowthStage, null=True, blank=True, on_delete=models.PROTECT, verbose_name="Giai đoạn sinh trưởng")
    valid_from = models.DateField("Thời gian dự báo từ")
    valid_to = models.DateField("Thời gian dự báo đến")
    risk_level = models.CharField("Mức độ nguy cơ", max_length=10, choices=RISK_LEVELS, default="low")
    expected_rate = models.FloatField("Tỷ lệ hại dự kiến (%)", null=True, blank=True)
    expected_area = models.FloatField("Diện tích dự kiến bị hại (ha)", null=True, blank=True)
    basis = models.TextField("Căn cứ dữ liệu")
    recommendation = models.TextField("Khuyến nghị chuyên môn", blank=True)
    threshold = models.ForeignKey(Threshold, null=True, blank=True, on_delete=models.SET_NULL, verbose_name="Tiêu chí áp dụng")
    origin = models.CharField("Nguồn lập", max_length=10, choices=ORIGINS, default="manual")
    analysis_meta = models.JSONField("Nguồn dữ liệu, tiêu chí phân tích tự động", default=dict, blank=True)
    status = models.CharField("Trạng thái", max_length=10, choices=STATUSES, default="draft", db_index=True)
    created_by = models.ForeignKey(settings.AUTH_USER_MODEL, null=True, on_delete=models.SET_NULL,
                                   related_name="forecasts_created", verbose_name="Người lập")
    confirmed_by = models.ForeignKey(settings.AUTH_USER_MODEL, null=True, blank=True, on_delete=models.SET_NULL,
                                     related_name="forecasts_confirmed", verbose_name="Người xác nhận")
    confirmed_at = models.DateTimeField("Thời điểm xác nhận", null=True, blank=True)
    review_note = models.TextField("Ý kiến xác nhận", blank=True)
    # đối chiếu thực tế
    actual_rate = models.FloatField("Tỷ lệ hại thực tế (%)", null=True, blank=True)
    actual_area = models.FloatField("Diện tích bị hại thực tế (ha)", null=True, blank=True)
    actual_level = models.CharField("Mức độ thực tế", max_length=10, choices=RISK_LEVELS, blank=True)
    evaluation_note = models.TextField("Đánh giá kết quả dự báo", blank=True)
    evaluated_at = models.DateTimeField("Thời điểm đánh giá", null=True, blank=True)

    class Meta:
        ordering = ["-valid_from", "-id"]
        verbose_name = "Nhận định dự tính, dự báo"
        verbose_name_plural = "Nhận định dự tính, dự báo"

    def __str__(self):
        return self.title

    def clean(self):
        if self.valid_from and self.valid_to and self.valid_to < self.valid_from:
            raise ValidationError("Thời gian dự báo đến phải sau thời gian từ.")
        if self.expected_rate is not None and not 0 <= self.expected_rate <= 100:
            raise ValidationError("Tỷ lệ hại dự kiến phải trong khoảng 0–100%.")

    @property
    def editable(self):
        return self.status in ("draft", "rejected")

    @property
    def is_confirmed(self):
        return self.status == "confirmed"
