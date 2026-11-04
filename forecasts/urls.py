from django.urls import path

from core.crud import Crud
from . import forms as f
from . import models as m
from . import views as v

app_name = "forecasts"

weather = Crud("weather", m.WeatherData, f.WeatherForm, "Dữ liệu thời tiết", "forecast",
               [("Địa bàn", "division"), ("Ngày", "date"), ("Nhiệt độ TB", "temp_avg"), ("Độ ẩm", "humidity"),
                ("Mưa (mm)", "rainfall"), ("Nguồn", "get_source_display")],
               search=("division__name", "source_note"), filters=("division", "source"), select_related=("division",))
thresholds = Crud("thresholds", m.Threshold, f.ThresholdForm, "Ngưỡng, tiêu chí nguy cơ", "forecast",
                  [("Tên", "name"), ("Sinh vật", "pest"), ("Cây trồng", "crop"), ("Chỉ tiêu", "get_metric_display"),
                   ("TB từ", "medium_from"), ("Cao từ", "high_from"), ("Rất cao từ", "very_high_from"), ("Áp dụng", "is_active")],
                  search=("name", "pest__name"), filters=("pest", "is_active"), select_related=("pest", "crop"))

urlpatterns = [
    path("analysis/", v.analysis, name="analysis"),
    path("compare/", v.compare, name="compare"),
    path("forecasts/", v.forecast_list, name="list"),
    path("forecasts/new/", v.forecast_create, name="create"),
    path("forecasts/suggest/", v.suggest_view, name="suggest"),
    path("forecasts/<int:pk>/", v.forecast_detail, name="detail"),
    path("forecasts/<int:pk>/edit/", v.forecast_edit, name="edit"),
    path("forecasts/<int:pk>/action/<str:action>/", v.forecast_action, name="action"),
]
for c in (weather, thresholds):
    urlpatterns += c.urls("forecasts")
