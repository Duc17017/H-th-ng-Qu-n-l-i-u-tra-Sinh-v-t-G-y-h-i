from django.urls import path

from core.crud import Crud
from . import forms as f
from . import models as m
from . import views as v

app_name = "cms"

categories = Crud("categories", m.Category, f.CategoryForm, "Chuyên mục", "cms",
                  [("Tên", "name"), ("Đường dẫn", "slug"), ("Thứ tự", "order")], search=("name",))

urlpatterns = [
    path("", v.home, name="home"),
    path("tin-tuc/", v.post_list, name="post_list"),
    path("tin-tuc/<slug:slug>/", v.post_public, name="post_public"),
    path("cms/posts/", v.manage_list, name="manage_list"),
    path("cms/posts/new/", v.manage_create, name="manage_create"),
    path("cms/posts/<int:pk>/", v.manage_detail, name="manage_detail"),
    path("cms/posts/<int:pk>/edit/", v.manage_edit, name="manage_edit"),
    path("cms/posts/<int:pk>/action/<str:action>/", v.manage_action, name="manage_action"),
]
urlpatterns += categories.urls("cms")
