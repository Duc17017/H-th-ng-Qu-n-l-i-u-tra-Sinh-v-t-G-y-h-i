from django import forms

from accounts.models import User
from core.forms import StyledForm, StyledModelForm
from forecasts.models import Forecast
from . import models as m


class AlertForm(StyledModelForm):
    channels = forms.MultipleChoiceField(label="Kênh phát hành", required=False, choices=m.Alert.CHANNELS,
                                         widget=forms.CheckboxSelectMultiple)

    class Meta:
        model = m.Alert
        fields = ["code", "title", "pest", "crop", "divisions", "valid_from", "valid_to", "risk_level", "forecast",
                  "basis", "guidance", "recipient_units", "channels"]
        widgets = {"basis": forms.Textarea(attrs={"rows": 4}), "guidance": forms.Textarea(attrs={"rows": 5})}

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        # Chỉ cho chọn nhận định đã được chuyên môn xác nhận
        self.fields["forecast"].queryset = Forecast.objects.filter(status="confirmed")
        self.fields["forecast"].required = False
        self.fields["channels"].widget.attrs["class"] = ""
        if self.instance.pk:
            self.initial["channels"] = self.instance.channels

    def clean_channels(self):
        return list(self.cleaned_data.get("channels") or [])


class AlertFromForecastForm(StyledForm):
    code = forms.CharField(label="Số hiệu bản tin", max_length=40)


class FollowUpForm(StyledModelForm):
    class Meta:
        model = m.FollowUpTask
        fields = ["alert", "title", "division", "unit", "assignee", "due_date", "status"]

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields["assignee"].queryset = User.objects.filter(is_active=True)


class FollowUpResultForm(StyledModelForm):
    class Meta:
        model = m.FollowUpTask
        fields = ["status", "result", "area_treated", "rate_after", "effectiveness"]

    def clean(self):
        d = super().clean()
        if d.get("status") == "done" and not (d.get("result") or "").strip():
            raise forms.ValidationError("Cần nhập kết quả kiểm tra thực tế trước khi hoàn thành.")
        return d


class NoteForm(StyledForm):
    note = forms.CharField(label="Ý kiến", required=False, widget=forms.Textarea(attrs={"rows": 3}))
