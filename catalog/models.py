from django.db import models

from core.models import TimeStampedModel


class CatalogBase(TimeStampedModel):
    code = models.CharField("Mã", max_length=30, unique=True)
    name = models.CharField("Tên", max_length=200)
    description = models.TextField("Mô tả", blank=True)
    is_active = models.BooleanField("Đang sử dụng", default=True)

    class Meta:
        abstract = True
        ordering = ["code"]

    def __str__(self):
        return self.name


class Crop(CatalogBase):
    scientific_name = models.CharField("Tên khoa học", max_length=200, blank=True)

    class Meta(CatalogBase.Meta):
        verbose_name = "Cây trồng"
        verbose_name_plural = "Cây trồng"


class PestSpecies(CatalogBase):
    TYPES = [("insect", "Côn trùng"), ("disease", "Bệnh hại"), ("weed", "Cỏ dại"),
             ("rodent", "Chuột"), ("mollusc", "Ốc, nhuyễn thể"), ("other", "Khác")]
    scientific_name = models.CharField("Tên khoa học", max_length=200, blank=True)
    pest_type = models.CharField("Nhóm", max_length=20, choices=TYPES, default="insect")
    crops = models.ManyToManyField(Crop, blank=True, related_name="pests", verbose_name="Cây trồng bị hại")
    control_guidance = models.TextField("Hướng dẫn phòng trừ chung", blank=True)

    class Meta(CatalogBase.Meta):
        verbose_name = "Sinh vật gây hại"
        verbose_name_plural = "Sinh vật gây hại"


class GrowthStage(CatalogBase):
    crop = models.ForeignKey(Crop, null=True, blank=True, on_delete=models.PROTECT, related_name="stages",
                             verbose_name="Cây trồng")

    class Meta(CatalogBase.Meta):
        verbose_name = "Giai đoạn sinh trưởng"
        verbose_name_plural = "Giai đoạn sinh trưởng"


class MeasureUnit(CatalogBase):
    symbol = models.CharField("Ký hiệu", max_length=20)

    class Meta(CatalogBase.Meta):
        verbose_name = "Đơn vị đo"
        verbose_name_plural = "Đơn vị đo"


class SurveyMethod(CatalogBase):
    class Meta(CatalogBase.Meta):
        verbose_name = "Phương pháp điều tra"
        verbose_name_plural = "Phương pháp điều tra"


class SurveyIndicator(CatalogBase):
    DATATYPES = [("number", "Số"), ("text", "Văn bản"), ("choice", "Lựa chọn")]
    data_type = models.CharField("Kiểu dữ liệu", max_length=10, choices=DATATYPES, default="number")
    unit = models.ForeignKey(MeasureUnit, null=True, blank=True, on_delete=models.PROTECT, verbose_name="Đơn vị đo")
    min_value = models.FloatField("Giá trị nhỏ nhất", null=True, blank=True)
    max_value = models.FloatField("Giá trị lớn nhất", null=True, blank=True)

    class Meta(CatalogBase.Meta):
        verbose_name = "Chỉ tiêu điều tra"
        verbose_name_plural = "Chỉ tiêu điều tra"


class Season(CatalogBase):
    start_date = models.DateField("Từ ngày")
    end_date = models.DateField("Đến ngày")

    class Meta(CatalogBase.Meta):
        ordering = ["-start_date"]
        verbose_name = "Mùa vụ"
        verbose_name_plural = "Mùa vụ"


class DamageLevel(CatalogBase):
    rank = models.PositiveSmallIntegerField("Thứ tự (0 = không hại)", default=0)
    min_rate = models.FloatField("Tỷ lệ hại từ (%)", default=0)
    max_rate = models.FloatField("Tỷ lệ hại đến (%)", default=100)

    class Meta(CatalogBase.Meta):
        ordering = ["rank"]
        verbose_name = "Mức độ gây hại"
        verbose_name_plural = "Mức độ gây hại"
