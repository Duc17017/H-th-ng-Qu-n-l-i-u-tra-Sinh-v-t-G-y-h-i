from django.db import models

from core.models import TimeStampedModel


class ExternalLayer(TimeStampedModel):
    """Lớp bản đồ nền / dịch vụ GIS hiện có của tỉnh (WMS hoặc XYZ) để kế thừa, không đầu tư trùng lặp."""

    KINDS = [("xyz", "Ô ảnh XYZ (tile)"), ("wms", "WMS")]
    name = models.CharField("Tên lớp", max_length=150)
    kind = models.CharField("Loại dịch vụ", max_length=5, choices=KINDS, default="xyz")
    url = models.URLField("Địa chỉ dịch vụ", max_length=500)
    layers = models.CharField("Tên lớp WMS", max_length=200, blank=True)
    attribution = models.CharField("Nguồn dữ liệu", max_length=200, blank=True)
    is_base = models.BooleanField("Là bản đồ nền", default=False)
    is_active = models.BooleanField("Đang sử dụng", default=True)
    order = models.PositiveSmallIntegerField("Thứ tự", default=0)

    class Meta:
        ordering = ["order", "name"]
        verbose_name = "Lớp bản đồ liên kết"
        verbose_name_plural = "Lớp bản đồ liên kết"

    def __str__(self):
        return self.name
