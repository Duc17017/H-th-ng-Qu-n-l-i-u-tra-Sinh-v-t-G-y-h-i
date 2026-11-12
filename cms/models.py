from django.db import models
from django.conf import settings
from django.utils import timezone
from django.utils.text import slugify

from core.models import TimeStampedModel


class Category(TimeStampedModel):
    name = models.CharField("Tên chuyên mục", max_length=150)
    slug = models.SlugField("Đường dẫn", max_length=160, unique=True)
    order = models.PositiveSmallIntegerField("Thứ tự", default=0)

    class Meta:
        ordering = ["order", "name"]
        verbose_name = "Chuyên mục"
        verbose_name_plural = "Chuyên mục"

    def __str__(self):
        return self.name


class Post(TimeStampedModel):
    TYPES = [("news", "Tin tức"), ("notice", "Thông báo"), ("bulletin", "Bản tin chuyên ngành"),
             ("guide", "Hướng dẫn kỹ thuật"), ("situation", "Tình hình sinh vật gây hại"),
             ("advice", "Khuyến cáo phòng trừ"), ("forecast", "Bản tin dự tính, dự báo")]
    STATUSES = [("draft", "Dự thảo"), ("review", "Chờ kiểm duyệt"), ("approved", "Đã duyệt"),
                ("published", "Đã đăng"), ("unpublished", "Gỡ bài")]
    title = models.CharField("Tiêu đề", max_length=255)
    slug = models.SlugField("Đường dẫn", max_length=270, unique=True, blank=True)
    post_type = models.CharField("Loại", max_length=12, choices=TYPES, default="news")
    category = models.ForeignKey(Category, null=True, blank=True, on_delete=models.SET_NULL, verbose_name="Chuyên mục")
    summary = models.TextField("Tóm tắt", blank=True)
    content = models.TextField("Nội dung")
    cover = models.ImageField("Ảnh đại diện", upload_to="cms/%Y/%m/", blank=True)
    status = models.CharField("Trạng thái", max_length=12, choices=STATUSES, default="draft", db_index=True)
    is_featured = models.BooleanField("Nổi bật", default=False)
    published_at = models.DateTimeField("Thời điểm đăng", null=True, blank=True)
    author = models.ForeignKey(settings.AUTH_USER_MODEL, null=True, on_delete=models.SET_NULL, related_name="posts",
                               verbose_name="Tác giả")
    reviewed_by = models.ForeignKey(settings.AUTH_USER_MODEL, null=True, blank=True, on_delete=models.SET_NULL,
                                    related_name="posts_reviewed", verbose_name="Người duyệt")
    review_note = models.TextField("Ý kiến kiểm duyệt", blank=True)
    version = models.PositiveSmallIntegerField("Lần cập nhật", default=1)
    alert = models.ForeignKey("alerts.Alert", null=True, blank=True, on_delete=models.SET_NULL, related_name="posts",
                              verbose_name="Bản tin cảnh báo liên quan")
    views = models.PositiveIntegerField("Lượt xem", default=0)
    # Điểm tin nóng do thuật toán nội bộ tính (cms/insights.py), không nhập tay.
    hot_score = models.FloatField("Điểm tin nóng", default=0.0, db_index=True)
    hot_computed_at = models.DateTimeField("Chấm điểm lúc", null=True, blank=True)

    class Meta:
        ordering = ["-published_at", "-created_at"]
        verbose_name = "Bài viết"
        verbose_name_plural = "Bài viết"

    def __str__(self):
        return self.title

    def save(self, *args, **kwargs):
        # Đường dẫn luôn được chuẩn hoá: slug do người dùng nhập cũng phải an toàn
        # cho URL, nếu không reverse() sẽ không tìm được bài và cổng thông tin lỗi.
        if self.slug:
            self.slug = slugify(self.slug.replace("đ", "d").replace("Đ", "D"))[:200]
        if not self.slug:
            base = slugify(self.title.replace("đ", "d").replace("Đ", "D"))[:200] or "bai-viet"
            slug, i = base, 1
            while Post.objects.filter(slug=slug).exclude(pk=self.pk).exists():
                i += 1
                slug = f"{base}-{i}"
            self.slug = slug
        super().save(*args, **kwargs)

    @property
    def editable(self):
        return self.status in ("draft", "unpublished")

    @property
    def is_public(self):
        return self.status == "published" and (self.published_at is None or self.published_at <= timezone.now())


class PostRevision(models.Model):
    """Lịch sử phát hành, cập nhật, điều chỉnh bản tin chuyên ngành."""

    post = models.ForeignKey(Post, on_delete=models.CASCADE, related_name="revisions")
    version = models.PositiveSmallIntegerField()
    action = models.CharField("Hành động", max_length=30)
    title = models.CharField(max_length=255)
    content = models.TextField()
    note = models.TextField(blank=True)
    user = models.ForeignKey(settings.AUTH_USER_MODEL, null=True, on_delete=models.SET_NULL)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["-created_at", "-id"]
