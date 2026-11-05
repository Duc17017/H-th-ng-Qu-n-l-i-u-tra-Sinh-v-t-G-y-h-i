from django import forms
from django.conf import settings
from django.contrib.auth.forms import UserCreationForm

from core.forms import StyledModelForm
from .models import AdminDivision, RolePermission, Unit, User


class DivisionForm(StyledModelForm):
    class Meta:
        model = AdminDivision
        fields = ["code", "name", "level", "parent"]


class UnitForm(StyledModelForm):
    class Meta:
        model = Unit
        fields = ["code", "name", "division", "parent", "phone", "email", "is_active"]


class UserCreateForm(UserCreationForm):
    class Meta:
        model = User
        fields = ["username", "first_name", "last_name", "email", "phone", "position", "role", "unit", "division", "is_active"]

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        for f in self.fields.values():
            if not isinstance(f.widget, forms.CheckboxInput):
                f.widget.attrs["class"] = "form-select" if isinstance(f.widget, forms.Select) else "form-control"


class UserEditForm(StyledModelForm):
    new_password = forms.CharField(label="Đặt lại mật khẩu (bỏ trống nếu không đổi)", required=False,
                                   widget=forms.PasswordInput(render_value=False))

    class Meta:
        model = User
        fields = ["username", "first_name", "last_name", "email", "phone", "position", "role", "unit", "division", "is_active"]

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        if self.instance.pk is None:
            self.fields["new_password"].label = "Mật khẩu"
            self.fields["new_password"].required = True

    def clean_new_password(self):
        pw = self.cleaned_data.get("new_password")
        if pw:
            from django.contrib.auth.password_validation import validate_password

            validate_password(pw, self.instance)
        return pw

    def save(self, commit=True):
        user = super().save(commit=False)
        if self.cleaned_data.get("new_password"):
            user.set_password(self.cleaned_data["new_password"])
        if commit:
            user.save()
        return user


class ProfileForm(StyledModelForm):
    class Meta:
        model = User
        fields = ["first_name", "last_name", "email", "phone", "position"]


class RegistrationForm(UserCreationForm):
    """Đăng ký công khai: chỉ tạo được tài khoản Người xem, không chọn được vai trò."""

    full_name = forms.CharField(
        label="Họ và tên", max_length=150,
        widget=forms.TextInput(attrs={"placeholder": "Nguyễn Văn A", "autocomplete": "name"}))
    email = forms.EmailField(
        label="Thư điện tử",
        widget=forms.EmailInput(attrs={"placeholder": "ten@donvi.gov.vn", "autocomplete": "email"}))
    phone = forms.CharField(
        label="Điện thoại", max_length=30, required=False,
        widget=forms.TextInput(attrs={"placeholder": "09xx xxx xxx", "autocomplete": "tel"}))
    position = forms.CharField(
        label="Chức vụ / đơn vị công tác", max_length=100, required=False,
        widget=forms.TextInput(attrs={"placeholder": "Cán bộ Trạm Trồng trọt và BVTV"}))
    agree = forms.BooleanField(
        label="Tôi đồng ý với quy định sử dụng và việc ghi nhận nhật ký truy cập",
        error_messages={"required": "Bạn cần đồng ý quy định sử dụng để tiếp tục."})

    # Bẫy bot: người thật không nhìn thấy ô này, điền vào là dấu hiệu tự động.
    website = forms.CharField(required=False, widget=forms.HiddenInput, label="")

    class Meta:
        model = User
        fields = ["username", "full_name", "email", "phone", "position"]

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields["username"].label = "Tên đăng nhập"
        self.fields["username"].widget.attrs.update({
            "placeholder": "vd: nguyenvanan", "autocomplete": "username"})
        self.fields["username"].help_text = "Chỉ dùng chữ, số và các ký tự @ . + - _"
        self.fields["password1"].label = "Mật khẩu"
        self.fields["password2"].label = "Nhập lại mật khẩu"
        for name in ("password1", "password2"):
            self.fields[name].widget.attrs.update({"autocomplete": "new-password"})
        self.fields["password1"].help_text = "Tối thiểu 8 ký tự, không dùng mật khẩu quá phổ biến."
        # Trường chỉ để chống bot, không bao giờ lưu vào CSDL.
        self.fields["website"].widget = forms.HiddenInput()

    def clean_website(self):
        if self.cleaned_data.get("website"):
            raise forms.ValidationError("Đăng ký không hợp lệ.")
        return ""

    def clean_email(self):
        email = (self.cleaned_data.get("email") or "").strip().lower()
        if not email:
            raise forms.ValidationError("Cần nhập thư điện tử để liên hệ khi cần thiết.")
        if User.objects.filter(email__iexact=email).exists():
            raise forms.ValidationError("Thư điện tử này đã được dùng cho một tài khoản khác.")
        domains = getattr(settings, "REGISTRATION_EMAIL_DOMAINS", [])
        if domains:
            domain = email.rsplit("@", 1)[-1]
            if domain not in domains:
                raise forms.ValidationError(
                    "Chỉ chấp nhận thư điện tử thuộc: " + ", ".join(domains))
        return email

    def clean_full_name(self):
        name = (self.cleaned_data.get("full_name") or "").strip()
        if len(name) < 3:
            raise forms.ValidationError("Cần nhập họ và tên đầy đủ.")
        return name

    def save(self, commit=True):
        user = super().save(commit=False)
        # Người tự đăng ký luôn là Người xem, không bao giờ được cấp quyền cao hơn.
        user.role = "viewer"
        user.first_name = self.cleaned_data["full_name"]
        user.email = self.cleaned_data["email"]
        user.phone = self.cleaned_data.get("phone", "")
        user.position = self.cleaned_data.get("position", "")
        user.self_registered = True
        user.is_active = getattr(settings, "REGISTRATION_AUTO_ACTIVE", True)
        if commit:
            user.save()
        return user
