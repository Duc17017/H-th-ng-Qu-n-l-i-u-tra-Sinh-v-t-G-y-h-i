from django.urls import path

from core.crud import Crud
from . import views as v
from .models import ExternalLayer
from core.forms import StyledModelForm

app_name = "mapview"


class LayerForm(StyledModelForm):
    class Meta:
        model = ExternalLayer
        fields = ["name", "kind", "url", "layers", "attribution", "is_base", "is_active", "order"]


layers = Crud("layers", ExternalLayer, LayerForm, "Lớp bản đồ liên kết", "system",
              [("Tên", "name"), ("Loại", "get_kind_display"), ("Địa chỉ", "url"), ("Nền", "is_base"), ("Sử dụng", "is_active")],
              search=("name", "url"))

urlpatterns = [
    path("", v.map_page, name="map"),
    path("api/points/", v.points_geojson, name="points"),
    path("api/routes/", v.routes_geojson, name="routes"),
    path("api/points/<int:pk>/", v.point_detail, name="point_detail"),
    path("api/timeline/", v.timeline_api, name="timeline"),
    path("export/", v.export_geojson, name="export"),
    path("import/", v.import_geojson, name="import"),
]
urlpatterns += layers.urls("mapview")
