from django import forms

from core.forms import StyledModelForm
from . import models as m


def make_form(model, extra=()):
    base = ["code", "name"] + list(extra) + ["description", "is_active"]
    meta = type("Meta", (), {"model": model, "fields": base})
    return type(f"{model.__name__}Form", (StyledModelForm,), {"Meta": meta})


CropForm = make_form(m.Crop, ["scientific_name"])
PestForm = make_form(m.PestSpecies, ["scientific_name", "pest_type", "crops", "control_guidance"])
StageForm = make_form(m.GrowthStage, ["crop"])
UnitMeasureForm = make_form(m.MeasureUnit, ["symbol"])
MethodForm = make_form(m.SurveyMethod)
IndicatorForm = make_form(m.SurveyIndicator, ["data_type", "unit", "min_value", "max_value"])
SeasonForm = make_form(m.Season, ["start_date", "end_date"])
DamageForm = make_form(m.DamageLevel, ["rank", "min_rate", "max_rate"])


def _season_clean(self):
    data = super(SeasonForm, self).clean()
    if data.get("start_date") and data.get("end_date") and data["end_date"] < data["start_date"]:
        raise forms.ValidationError("Ngày kết thúc phải sau ngày bắt đầu.")
    return data


SeasonForm.clean = _season_clean


def _damage_clean(self):
    data = super(DamageForm, self).clean()
    lo, hi = data.get("min_rate"), data.get("max_rate")
    if lo is not None and hi is not None and hi < lo:
        raise forms.ValidationError("Tỷ lệ hại 'đến' phải lớn hơn hoặc bằng 'từ'.")
    return data


DamageForm.clean = _damage_clean
