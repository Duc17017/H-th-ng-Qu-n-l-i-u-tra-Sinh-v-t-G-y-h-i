from django import forms
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
