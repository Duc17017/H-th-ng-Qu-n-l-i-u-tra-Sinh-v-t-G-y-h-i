from django.urls import path
from django.contrib.auth.views import LogoutView

from core.crud import Crud
from . import views
from .forms import DivisionForm, UnitForm, UserCreateForm, UserEditForm
from .models import AdminDivision, Unit, User

app_name = "accounts"

units = Crud("units", Unit, UnitForm, "Đơn vị", "system",
             [("Mã", "code"), ("Tên đơn vị", "name"), ("Địa bàn", "division"), ("Hoạt động", "is_active")],
             search=("code", "name"), filters=("is_active",), select_related=("division",))
divisions = Crud("divisions", AdminDivision, DivisionForm, "Địa bàn hành chính", "system",
                 [("Mã", "code"), ("Tên", "name"), ("Cấp", "get_level_display"), ("Thuộc", "parent")],
                 search=("code", "name"), filters=("level",), select_related=("parent",))
users = Crud("users", User, UserEditForm, "Người dùng", "system",
             [("Tài khoản", "username"), ("Họ tên", "display_name"), ("Vai trò", "get_role_display"),
              ("Đơn vị", "unit"), ("Hoạt động", "is_active")],
             search=("username", "first_name", "last_name", "email"), filters=("role", "is_active"),
             delete=False, select_related=("unit",))

urlpatterns = [
    path("login/", views.SiteLoginView.as_view(), name="login"),
    path("logout/", LogoutView.as_view(), name="logout"),
    path("profile/", views.profile, name="profile"),
    path("password/", views.SitePasswordChangeView.as_view(), name="password_change"),
    path("notifications/", views.notifications, name="notifications"),
    path("notifications/<int:pk>/", views.notification_open, name="notification_open"),
    path("roles/", views.role_matrix, name="role_matrix"),
]
for c in (users, units, divisions):
    urlpatterns += c.urls("accounts")
