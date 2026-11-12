from django.conf import settings
from django.core.exceptions import ValidationError
from django.db import models
from django.utils import timezone

from accounts.models import AdminDivision, Unit
from catalog import models as cat
from core.models import TimeStampedModel


class FormTemplate(TimeStampedModel):
    """Biểu mẫu điều tra điện tử cấu hình theo cây trồng / đối tượng gây hại / phương pháp."""

    code = models.CharField("Mã biểu mẫu", max_length=30, unique=True)
    name = models.CharField("Tên biểu mẫu", max_length=200)
    crop = models.ForeignKey(cat.Crop, null=True, blank=True, on_delete=models.PROTECT, verbose_name="Cây trồng")
    pest = models.ForeignKey(cat.PestSpecies, null=True, blank=True, on_delete=models.PROTECT,
                             verbose_name="Đối tượng gây hại")
    method = models.ForeignKey(cat.SurveyMethod, null=True, blank=True, on_delete=models.PROTECT,
                               verbose_name="Phương pháp điều tra")
    version = models.CharField("Phiên bản", max_length=20, default="1.0")
    description = models.TextField("Mô tả", blank=True)
    is_active = models.BooleanField("Đang áp dụng", default=True)

    class Meta:
        ordering = ["code"]
        verbose_name = "Biểu mẫu điều tra"
        verbose_name_plural = "Biểu mẫu điều tra"

    def __str__(self):
        return f"{self.name} (v{self.version})"


class FormField(models.Model):
    TYPES = [("number", "Số"), ("text", "Văn bản"), ("choice", "Lựa chọn"), ("boolean", "Có/Không")]
    template = models.ForeignKey(FormTemplate, on_delete=models.CASCADE, related_name="fields", verbose_name="Biểu mẫu")
    key = models.SlugField("Khóa trường", max_length=50, help_text="Chữ thường, số, gạch dưới hoặc gạch ngang; không trùng trong biểu mẫu")
    label = models.CharField("Nhãn hiển thị", max_length=200)
    field_type = models.CharField("Kiểu", max_length=10, choices=TYPES, default="number")
    indicator = models.ForeignKey(cat.SurveyIndicator, null=True, blank=True, on_delete=models.PROTECT,
                                  verbose_name="Chỉ tiêu danh mục")
    required = models.BooleanField("Bắt buộc", default=False)
    min_value = models.FloatField("Nhỏ nhất", null=True, blank=True)
    max_value = models.FloatField("Lớn nhất", null=True, blank=True)
    choices = models.TextField("Các lựa chọn (mỗi dòng một giá trị)", blank=True)
    order = models.PositiveSmallIntegerField("Thứ tự", default=0)

    class Meta:
        ordering = ["template", "order", "id"]
        unique_together = ("template", "key")
        verbose_name = "Trường biểu mẫu"
        verbose_name_plural = "Trường biểu mẫu"

    def __str__(self):
        return f"{self.template.code}.{self.key}"

    def choice_list(self):
        return [c.strip() for c in self.choices.splitlines() if c.strip()]

    def clean(self):
        if self.min_value is not None and self.max_value is not None and self.max_value < self.min_value:
            raise ValidationError("Giá trị lớn nhất phải lớn hơn hoặc bằng giá trị nhỏ nhất.")
        if self.field_type == "choice" and not self.choice_list():
            raise ValidationError("Trường kiểu lựa chọn cần có danh sách giá trị.")


class SurveyPlan(TimeStampedModel):
    TYPES = [("periodic", "Điều tra định kỳ"), ("supplement", "Điều tra bổ sung"), ("urgent", "Điều tra đột xuất")]
    STATUSES = [("draft", "Dự thảo"), ("approved", "Đã phê duyệt"), ("running", "Đang thực hiện"),
                ("done", "Hoàn thành"), ("cancelled", "Đã hủy")]
    code = models.CharField("Mã kế hoạch", max_length=30, unique=True)
    name = models.CharField("Tên kế hoạch", max_length=255)
    plan_type = models.CharField("Loại điều tra", max_length=12, choices=TYPES, default="periodic")
    season = models.ForeignKey(cat.Season, null=True, blank=True, on_delete=models.PROTECT, verbose_name="Mùa vụ")
    crop = models.ForeignKey(cat.Crop, on_delete=models.PROTECT, verbose_name="Cây trồng")
    pests = models.ManyToManyField(cat.PestSpecies, blank=True, verbose_name="Đối tượng gây hại")
    method = models.ForeignKey(cat.SurveyMethod, null=True, blank=True, on_delete=models.PROTECT,
                               verbose_name="Phương pháp điều tra")
    form_template = models.ForeignKey(FormTemplate, null=True, blank=True, on_delete=models.PROTECT,
                                      verbose_name="Biểu mẫu áp dụng")
    division = models.ForeignKey(AdminDivision, on_delete=models.PROTECT, verbose_name="Địa bàn")
    start_date = models.DateField("Từ ngày")
    end_date = models.DateField("Đến ngày")
    frequency_days = models.PositiveSmallIntegerField("Chu kỳ lặp (ngày, 0 = không lặp)", default=0)
    status = models.CharField("Trạng thái", max_length=10, choices=STATUSES, default="draft")
    description = models.TextField("Nội dung, yêu cầu", blank=True)
    created_by = models.ForeignKey(settings.AUTH_USER_MODEL, null=True, blank=True, on_delete=models.SET_NULL,
                                   related_name="plans_created", verbose_name="Người lập")

    class Meta:
        ordering = ["-start_date", "-id"]
        verbose_name = "Kế hoạch điều tra"
        verbose_name_plural = "Kế hoạch điều tra"

    def __str__(self):
        return f"{self.code} - {self.name}"

    def clean(self):
        if self.start_date and self.end_date and self.end_date < self.start_date:
            raise ValidationError("Ngày kết thúc phải sau ngày bắt đầu.")

    @property
    def editable(self):
        return self.status in ("draft",)

    def progress(self):
        tasks = self.tasks.all()
        total = tasks.count()
        done = tasks.filter(status="done").count()
        return done, total, (round(done * 100 / total) if total else 0)


class SurveyRoute(TimeStampedModel):
    plan = models.ForeignKey(SurveyPlan, on_delete=models.CASCADE, related_name="routes", verbose_name="Kế hoạch")
    code = models.CharField("Mã tuyến", max_length=30)
    name = models.CharField("Tên tuyến", max_length=200)
    division = models.ForeignKey(AdminDivision, null=True, blank=True, on_delete=models.PROTECT, verbose_name="Địa bàn")
    unit = models.ForeignKey(Unit, null=True, blank=True, on_delete=models.PROTECT, verbose_name="Đơn vị thực hiện")
    description = models.TextField("Mô tả tuyến", blank=True)

    class Meta:
        ordering = ["plan", "code"]
        unique_together = ("plan", "code")
        verbose_name = "Tuyến điều tra"
        verbose_name_plural = "Tuyến điều tra"

    def __str__(self):
        return f"{self.code} - {self.name}"


class SurveyPoint(TimeStampedModel):
    code = models.CharField("Mã điểm", max_length=30, unique=True)
    name = models.CharField("Tên điểm", max_length=200)
    route = models.ForeignKey(SurveyRoute, null=True, blank=True, on_delete=models.SET_NULL, related_name="points",
                              verbose_name="Tuyến điều tra")
    division = models.ForeignKey(AdminDivision, on_delete=models.PROTECT, verbose_name="Địa bàn (xã/phường)")
    crop = models.ForeignKey(cat.Crop, null=True, blank=True, on_delete=models.PROTECT, verbose_name="Cây trồng")
    latitude = models.FloatField("Vĩ độ", null=True, blank=True)
    longitude = models.FloatField("Kinh độ", null=True, blank=True)
    area_ha = models.FloatField("Diện tích đại diện (ha)", null=True, blank=True)
    address = models.CharField("Địa chỉ, vị trí", max_length=255, blank=True)
    is_active = models.BooleanField("Đang sử dụng", default=True)

    class Meta:
        ordering = ["code"]
        verbose_name = "Điểm điều tra"
        verbose_name_plural = "Điểm điều tra"

    def __str__(self):
        return f"{self.code} - {self.name}"

    def clean(self):
        if (self.latitude is None) != (self.longitude is None):
            raise ValidationError("Cần nhập đủ cả vĩ độ và kinh độ, hoặc để trống cả hai.")
        if self.latitude is not None and not (-90 <= self.latitude <= 90):
            raise ValidationError("Vĩ độ phải nằm trong khoảng -90 đến 90.")
        if self.longitude is not None and not (-180 <= self.longitude <= 180):
            raise ValidationError("Kinh độ phải nằm trong khoảng -180 đến 180.")


class SurveyTask(TimeStampedModel):
    STATUSES = [("assigned", "Đã giao"), ("doing", "Đang thực hiện"), ("review", "Chờ kiểm tra"),
                ("revision", "Yêu cầu bổ sung"), ("done", "Hoàn thành")]
    plan = models.ForeignKey(SurveyPlan, on_delete=models.CASCADE, related_name="tasks", verbose_name="Kế hoạch")
    point = models.ForeignKey(SurveyPoint, on_delete=models.PROTECT, related_name="tasks", verbose_name="Điểm điều tra")
    unit = models.ForeignKey(Unit, null=True, blank=True, on_delete=models.PROTECT, verbose_name="Đơn vị thực hiện")
    assignee = models.ForeignKey(settings.AUTH_USER_MODEL, null=True, blank=True, on_delete=models.SET_NULL,
                                 related_name="survey_tasks", verbose_name="Cán bộ được phân công")
    survey_date = models.DateField("Ngày điều tra theo lịch")
    due_date = models.DateField("Hạn hoàn thành", null=True, blank=True)
    status = models.CharField("Trạng thái", max_length=10, choices=STATUSES, default="assigned")
    note = models.TextField("Ghi chú, yêu cầu", blank=True)

    class Meta:
        ordering = ["survey_date", "id"]
        verbose_name = "Nhiệm vụ điều tra"
        verbose_name_plural = "Nhiệm vụ điều tra"

    def __str__(self):
        return f"{self.plan.code} / {self.point.code} / {self.survey_date:%d/%m/%Y}"

    @property
    def overdue(self):
        return bool(self.due_date and self.status != "done" and self.due_date < timezone.localdate())


class SurveyRecord(TimeStampedModel):
    STATUSES = [("draft", "Lưu tạm"), ("submitted", "Chờ xác nhận"), ("revision", "Yêu cầu chỉnh sửa"),
                ("confirmed", "Đã xác nhận")]
    SOURCES = [("web", "Nhập trên web"), ("mobile", "Thiết bị di động"), ("excel", "Nhập từ Excel")]

    task = models.ForeignKey(SurveyTask, null=True, blank=True, on_delete=models.SET_NULL, related_name="records",
                             verbose_name="Nhiệm vụ")
    plan = models.ForeignKey(SurveyPlan, null=True, blank=True, on_delete=models.PROTECT, related_name="records",
                             verbose_name="Kế hoạch")
    point = models.ForeignKey(SurveyPoint, on_delete=models.PROTECT, related_name="records", verbose_name="Điểm điều tra")
    survey_date = models.DateTimeField("Thời gian điều tra")
    unit = models.ForeignKey(Unit, null=True, blank=True, on_delete=models.PROTECT, verbose_name="Đơn vị")
    surveyor = models.ForeignKey(settings.AUTH_USER_MODEL, null=True, blank=True, on_delete=models.SET_NULL,
                                 related_name="records", verbose_name="Cán bộ điều tra")
    crop = models.ForeignKey(cat.Crop, on_delete=models.PROTECT, verbose_name="Cây trồng")
    season = models.ForeignKey(cat.Season, null=True, blank=True, on_delete=models.PROTECT, verbose_name="Mùa vụ")
    stage = models.ForeignKey(cat.GrowthStage, null=True, blank=True, on_delete=models.PROTECT,
                              verbose_name="Giai đoạn sinh trưởng")
    pest = models.ForeignKey(cat.PestSpecies, on_delete=models.PROTECT, verbose_name="Đối tượng gây hại")
    method = models.ForeignKey(cat.SurveyMethod, null=True, blank=True, on_delete=models.PROTECT,
                               verbose_name="Phương pháp điều tra")
    density = models.FloatField("Mật độ (con/m² hoặc đơn vị áp dụng)", null=True, blank=True)
    damage_rate = models.FloatField("Tỷ lệ hại (%)", null=True, blank=True)
    prevalence = models.CharField("Mức độ phổ biến", max_length=100, blank=True)
    damage_level = models.ForeignKey(cat.DamageLevel, null=True, blank=True, on_delete=models.PROTECT,
                                     verbose_name="Mức độ gây hại")
    surveyed_area = models.FloatField("Diện tích điều tra (ha)", null=True, blank=True)
    affected_area = models.FloatField("Diện tích bị hại (ha)", null=True, blank=True)
    latitude = models.FloatField("Vĩ độ GPS", null=True, blank=True)
    longitude = models.FloatField("Kinh độ GPS", null=True, blank=True)
    comment = models.TextField("Nhận xét chuyên môn", blank=True)
    data = models.JSONField("Chỉ tiêu theo biểu mẫu", default=dict, blank=True)
    status = models.CharField("Trạng thái", max_length=10, choices=STATUSES, default="draft", db_index=True)
    source = models.CharField("Nguồn dữ liệu", max_length=10, choices=SOURCES, default="web")
    review_note = models.TextField("Ý kiến kiểm tra", blank=True)
    confirmed_by = models.ForeignKey(settings.AUTH_USER_MODEL, null=True, blank=True, on_delete=models.SET_NULL,
                                     related_name="records_confirmed", verbose_name="Người xác nhận")
    confirmed_at = models.DateTimeField("Thời điểm xác nhận", null=True, blank=True)
    client_uuid = models.CharField(max_length=64, blank=True, db_index=True, editable=False)

    class Meta:
        ordering = ["-survey_date", "-id"]
        verbose_name = "Phiếu điều tra"
        verbose_name_plural = "Phiếu điều tra"

    def __str__(self):
        return f"Phiếu #{self.pk or 'mới'} - {self.point.code} - {self.pest.name}"

    # --- kiểm tra hợp lệ / logic / trùng lặp
    def validate_data(self):
        """Trả về (errors, warnings) về tính đầy đủ, hợp lệ, logic của dữ liệu."""
        errors, warnings = [], []
        if self.survey_date and self.survey_date > timezone.now() + timezone.timedelta(minutes=5):
            errors.append("Thời gian điều tra không được ở tương lai.")
        for label, v, lo, hi in (("Tỷ lệ hại", self.damage_rate, 0, 100), ("Mật độ", self.density, 0, None),
                                 ("Diện tích điều tra", self.surveyed_area, 0, None),
                                 ("Diện tích bị hại", self.affected_area, 0, None)):
            if v is not None and (v < lo or (hi is not None and v > hi)):
                errors.append(f"{label} nằm ngoài phạm vi hợp lệ ({lo}{'–' + str(hi) if hi is not None else ' trở lên'}).")
        if self.surveyed_area is not None and self.affected_area is not None and self.affected_area > self.surveyed_area:
            errors.append("Diện tích bị hại không được lớn hơn diện tích điều tra.")
        if (self.latitude is None) != (self.longitude is None):
            errors.append("GPS cần có đủ cả vĩ độ và kinh độ.")
        if self.latitude is not None and not (-90 <= self.latitude <= 90 and -180 <= self.longitude <= 180):
            errors.append("Tọa độ GPS nằm ngoài phạm vi hợp lệ.")
        if self.density is None and self.damage_rate is None:
            warnings.append("Chưa nhập mật độ hoặc tỷ lệ gây hại.")
        if self.damage_rate and self.damage_rate > 0 and not self.damage_level_id:
            warnings.append("Chưa chọn mức độ gây hại.")
        if not self.comment:
            warnings.append("Chưa có nhận xét chuyên môn.")
        if self.latitude is None and self.point_id and self.point.latitude is None:
            warnings.append("Phiếu và điểm điều tra đều chưa có tọa độ, sẽ không hiển thị trên bản đồ.")
        if self.point_id and self.survey_date:
            dup = SurveyRecord.objects.filter(point_id=self.point_id, pest_id=self.pest_id, crop_id=self.crop_id,
                                              survey_date__date=timezone.localtime(self.survey_date).date())
            if self.pk:
                dup = dup.exclude(pk=self.pk)
            if dup.exists():
                warnings.append("Có dấu hiệu trùng lặp: đã tồn tại phiếu cùng điểm, cây trồng, đối tượng gây hại trong ngày.")
        return errors, warnings

    def effective_coords(self):
        if self.latitude is not None and self.longitude is not None:
            return self.latitude, self.longitude
        if self.point_id and self.point.latitude is not None:
            return self.point.latitude, self.point.longitude
        return None

    @property
    def editable_by_surveyor(self):
        return self.status in ("draft", "revision")


class RecordAttachment(TimeStampedModel):
    record = models.ForeignKey(SurveyRecord, on_delete=models.CASCADE, related_name="attachments", verbose_name="Phiếu")
    file = models.FileField("Tệp", upload_to="records/%Y/%m/")
    caption = models.CharField("Chú thích", max_length=200, blank=True)
    uploaded_by = models.ForeignKey(settings.AUTH_USER_MODEL, null=True, blank=True, on_delete=models.SET_NULL)

    class Meta:
        ordering = ["id"]
        verbose_name = "Tệp đính kèm"
        verbose_name_plural = "Tệp đính kèm"

    @property
    def is_image(self):
        return self.file.name.lower().rsplit(".", 1)[-1] in ("jpg", "jpeg", "png", "gif", "webp")


class RecordHistory(models.Model):
    """Lịch sử xử lý phiếu: gửi, yêu cầu chỉnh sửa, xác nhận."""

    record = models.ForeignKey(SurveyRecord, on_delete=models.CASCADE, related_name="history")
    action = models.CharField("Hành động", max_length=30)
    from_status = models.CharField(max_length=10, blank=True)
    to_status = models.CharField(max_length=10, blank=True)
    note = models.TextField("Ghi chú", blank=True)
    user = models.ForeignKey(settings.AUTH_USER_MODEL, null=True, on_delete=models.SET_NULL)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["-created_at", "-id"]
        verbose_name = "Lịch sử phiếu"
        verbose_name_plural = "Lịch sử phiếu"
