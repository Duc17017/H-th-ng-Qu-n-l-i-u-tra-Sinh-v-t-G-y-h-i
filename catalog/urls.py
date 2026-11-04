from django.shortcuts import render

from core.crud import Crud
from core.permissions import perm_required
from . import forms as f
from . import models as m

app_name = "catalog"

BASIC = [("Mã", "code"), ("Tên", "name"), ("Sử dụng", "is_active")]
S = ("code", "name")

cruds = [
    Crud("crops", m.Crop, f.CropForm, "Cây trồng", "catalog", BASIC[:2] + [("Tên khoa học", "scientific_name"), BASIC[2]], search=S + ("scientific_name",)),
    Crud("pests", m.PestSpecies, f.PestForm, "Sinh vật gây hại", "catalog",
         BASIC[:2] + [("Nhóm", "get_pest_type_display"), BASIC[2]], search=S + ("scientific_name",), filters=("pest_type",)),
    Crud("stages", m.GrowthStage, f.StageForm, "Giai đoạn sinh trưởng", "catalog",
         BASIC[:2] + [("Cây trồng", "crop"), BASIC[2]], search=S, filters=("crop",), select_related=("crop",)),
    Crud("measures", m.MeasureUnit, f.UnitMeasureForm, "Đơn vị đo", "catalog", BASIC[:2] + [("Ký hiệu", "symbol")], search=S),
    Crud("methods", m.SurveyMethod, f.MethodForm, "Phương pháp điều tra", "catalog", BASIC, search=S),
    Crud("indicators", m.SurveyIndicator, f.IndicatorForm, "Chỉ tiêu điều tra", "catalog",
         BASIC[:2] + [("Kiểu", "get_data_type_display"), ("Đơn vị", "unit")], search=S, filters=("data_type",), select_related=("unit",)),
    Crud("seasons", m.Season, f.SeasonForm, "Mùa vụ", "catalog",
         BASIC[:2] + [("Từ", "start_date"), ("Đến", "end_date")], search=S),
    Crud("damage", m.DamageLevel, f.DamageForm, "Mức độ gây hại", "catalog",
         [("Thứ tự", "rank"), ("Mã", "code"), ("Tên", "name"), ("Từ %", "min_rate"), ("Đến %", "max_rate")], search=S),
]


@perm_required("catalog", "view")
def index(request):
    return render(request, "crud/index.html", {
        "title": "Danh mục chuyên môn",
        "items": [(c.title, c.url("list"), c.model.objects.count()) for c in cruds],
    })


urlpatterns = []
from django.urls import path  # noqa: E402

urlpatterns.append(path("", index, name="index"))
for c in cruds:
    urlpatterns += c.urls("catalog")
