from django.contrib.auth.models import AbstractUser
from django.db import models

from core.models import TimeStampedModel


class AdminDivision(TimeStampedModel):
    LEVELS = [(1, "Tỉnh/Thành phố"), (2, "Quận/Huyện"), (3, "Xã/Phường")]
    code = models.CharField("Mã", max_length=20, unique=True)
    name = models.CharField("Tên", max_length=150)
    level = models.PositiveSmallIntegerField("Cấp", choices=LEVELS, default=1)
    parent = models.ForeignKey("self", null=True, blank=True, on_delete=models.PROTECT,
                               related_name="children", verbose_name="Thuộc")

    class Meta:
        ordering = ["code"]
        verbose_name = "Địa bàn hành chính"
        verbose_name_plural = "Địa bàn hành chính"

    def __str__(self):
        return f"{self.name}"

    def descendant_ids(self):
        ids, frontier = {self.pk}, [self.pk]
        while frontier:
            frontier = list(AdminDivision.objects.filter(parent_id__in=frontier).values_list("pk", flat=True))
            frontier = [i for i in frontier if i not in ids]
            ids.update(frontier)
        return list(ids)

    @property
    def full_name(self):
        parts, node = [], self
        while node:
            parts.append(node.name)
            node = node.parent
        return ", ".join(parts)


class Unit(TimeStampedModel):
    code = models.CharField("Mã đơn vị", max_length=30, unique=True)
    name = models.CharField("Tên đơn vị", max_length=200)
    division = models.ForeignKey(AdminDivision, null=True, blank=True, on_delete=models.PROTECT,
                                 verbose_name="Địa bàn")
    parent = models.ForeignKey("self", null=True, blank=True, on_delete=models.PROTECT,
                               related_name="children", verbose_name="Đơn vị cấp trên")
    phone = models.CharField("Điện thoại", max_length=30, blank=True)
    email = models.EmailField("Email", blank=True)
    is_active = models.BooleanField("Đang hoạt động", default=True)

    class Meta:
        ordering = ["code"]
        verbose_name = "Đơn vị"
        verbose_name_plural = "Đơn vị"

    def __str__(self):
        return self.name


class User(AbstractUser):
    ROLES = [
        ("admin", "Quản trị hệ thống"),
        ("leader", "Lãnh đạo"),
        ("approver", "Người phê duyệt"),
        ("expert", "Cán bộ chuyên môn"),
        ("editor", "Biên tập viên"),
        ("surveyor", "Cán bộ điều tra"),
        ("viewer", "Người xem"),
    ]
    role = models.CharField("Vai trò", max_length=20, choices=ROLES, default="viewer")
    unit = models.ForeignKey(Unit, null=True, blank=True, on_delete=models.PROTECT, verbose_name="Đơn vị")
    division = models.ForeignKey(AdminDivision, null=True, blank=True, on_delete=models.PROTECT,
                                 verbose_name="Địa bàn phụ trách")
    phone = models.CharField("Điện thoại", max_length=30, blank=True)
    position = models.CharField("Chức vụ", max_length=100, blank=True)
    self_registered = models.BooleanField("Tự đăng ký", default=False,
                                          help_text="Tài khoản do người dùng tự tạo từ cổng thông tin.")

    class Meta:
        ordering = ["username"]
        verbose_name = "Người dùng"
        verbose_name_plural = "Người dùng"

    def __str__(self):
        return self.get_full_name() or self.username

    @property
    def display_name(self):
        return self.get_full_name() or self.username


class RolePermission(models.Model):
    """Ma trận quyền: vai trò x phân hệ -> danh sách hành động được phép."""

    role = models.CharField("Vai trò", max_length=20, choices=User.ROLES)
    module = models.CharField("Phân hệ", max_length=30)
    actions = models.JSONField("Hành động", default=list)

    class Meta:
        unique_together = ("role", "module")
        ordering = ["role", "module"]
        verbose_name = "Phân quyền vai trò"
        verbose_name_plural = "Phân quyền vai trò"

    def __str__(self):
        return f"{self.get_role_display()} / {self.module}: {','.join(self.actions)}"


class LoginHistory(models.Model):
    user = models.ForeignKey(User, null=True, blank=True, on_delete=models.SET_NULL)
    username = models.CharField("Tài khoản", max_length=150)
    success = models.BooleanField("Thành công", default=True)
    event = models.CharField("Sự kiện", max_length=20, default="login")
    ip_address = models.GenericIPAddressField("IP", null=True, blank=True)
    user_agent = models.CharField(max_length=255, blank=True)
    created_at = models.DateTimeField("Thời điểm", auto_now_add=True)

    class Meta:
        ordering = ["-created_at"]
        verbose_name = "Lịch sử đăng nhập"
        verbose_name_plural = "Lịch sử đăng nhập"
