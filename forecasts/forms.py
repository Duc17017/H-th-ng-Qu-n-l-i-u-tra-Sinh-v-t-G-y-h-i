from django import forms

from core.forms import StyledForm, StyledModelForm
from accounts.models import AdminDivision
from . import models as m


class WeatherForm(StyledModelForm):
    class Meta:
        model = m.WeatherData
        fields = ["division", "date", "temp_avg", "temp_min", "temp_max", "humidity", "rainfall", "source", "source_note"]


class ThresholdForm(StyledModelForm):
    class Meta:
        model = m.Threshold
        fields = ["name", "crop", "pest", "stage", "metric", "medium_from", "high_from", "very_high_from",
                  "temp_min", "temp_max", "humidity_min", "weather_condition", "basis", "approved_by",
                  "effective_from", "is_active"]
        widgets = {"weather_condition": forms.Textarea(attrs={"rows": 2})}


class ForecastForm(StyledModelForm):
    class Meta:
        model = m.Forecast
        fields = ["title", "pest", "crop", "division", "stage", "valid_from", "valid_to", "risk_level",
                  "expected_rate", "expected_area", "basis", "recommendation", "threshold"]
        widgets = {"basis": forms.Textarea(attrs={"rows": 4}), "recommendation": forms.Textarea(attrs={"rows": 4})}


class SuggestForm(StyledForm):
    threshold = forms.ModelChoiceField(label="Tiêu chí nguy cơ", queryset=m.Threshold.objects.filter(is_active=True))
    division = forms.ModelChoiceField(label="Địa bàn", queryset=AdminDivision.objects.all())
    lookback_days = forms.IntegerField(label="Số ngày dữ liệu phân tích", min_value=7, max_value=365, initial=30)


class NoteForm(StyledForm):
    note = forms.CharField(label="Ý kiến", required=False, widget=forms.Textarea(attrs={"rows": 3}))


class AnalysisForm(StyledForm):
    from catalog.models import Crop, PestSpecies, Season

    date_from = forms.DateField(label="Từ ngày", required=False)
    date_to = forms.DateField(label="Đến ngày", required=False)
    crop = forms.ModelChoiceField(label="Cây trồng", required=False, queryset=Crop.objects.all())
    pest = forms.ModelChoiceField(label="Sinh vật gây hại", required=False, queryset=PestSpecies.objects.all())
    season = forms.ModelChoiceField(label="Mùa vụ", required=False, queryset=Season.objects.all())
    division = forms.ModelChoiceField(label="Địa bàn", required=False, queryset=AdminDivision.objects.all())
    period = forms.ChoiceField(label="Gom theo kỳ", choices=[("day", "Ngày"), ("week", "Tuần"), ("month", "Tháng")],
                               initial="week")
