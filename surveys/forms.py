from django import forms
from django.utils import timezone

from accounts.models import Unit, User
from catalog import models as cat
from core.forms import StyledForm, StyledModelForm
from . import models as m


class FormTemplateForm(StyledModelForm):
    class Meta:
        model = m.FormTemplate
        fields = ["code", "name", "crop", "pest", "method", "version", "description", "is_active"]


class FormFieldForm(StyledModelForm):
    class Meta:
        model = m.FormField
        fields = ["template", "key", "label", "field_type", "indicator", "required", "min_value", "max_value",
                  "choices", "order"]
        widgets = {"choices": forms.Textarea(attrs={"rows": 3})}


class PlanForm(StyledModelForm):
    class Meta:
        model = m.SurveyPlan
        fields = ["code", "name", "plan_type", "season", "crop", "pests", "method", "form_template", "division",
                  "start_date", "end_date", "frequency_days", "status", "description"]


class RouteForm(StyledModelForm):
    class Meta:
        model = m.SurveyRoute
        fields = ["plan", "code", "name", "division", "unit", "description"]


class PointForm(StyledModelForm):
    class Meta:
        model = m.SurveyPoint
        fields = ["code", "name", "route", "division", "crop", "latitude", "longitude", "area_ha", "address", "is_active"]


class TaskForm(StyledModelForm):
    class Meta:
        model = m.SurveyTask
        fields = ["plan", "point", "unit", "assignee", "survey_date", "due_date", "status", "note"]

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields["assignee"].queryset = User.objects.filter(is_active=True).order_by("username")

    def clean(self):
        data = super().clean()
        if data.get("due_date") and data.get("survey_date") and data["due_date"] < data["survey_date"]:
            raise forms.ValidationError("Hạn hoàn thành phải sau hoặc bằng ngày điều tra.")
        return data


class RecordForm(StyledModelForm):
    """Phiếu điều tra: các trường cố định + các trường động theo biểu mẫu của kế hoạch."""

    class Meta:
        model = m.SurveyRecord
        fields = ["task", "point", "survey_date", "unit", "crop", "season", "stage", "pest", "method", "density",
                  "damage_rate", "prevalence", "damage_level", "surveyed_area", "affected_area", "latitude",
                  "longitude", "comment"]
        widgets = {"comment": forms.Textarea(attrs={"rows": 3})}

    def __init__(self, *args, user=None, template=None, **kwargs):
        super().__init__(*args, **kwargs)
        self.user = user
        self.template = template
        if not self.instance.pk and not self.initial.get("survey_date"):
            self.initial["survey_date"] = timezone.localtime().strftime("%Y-%m-%dT%H:%M")
        if self.instance.pk and self.instance.survey_date:
            self.initial["survey_date"] = timezone.localtime(self.instance.survey_date).strftime("%Y-%m-%dT%H:%M")
        self.fields["point"].queryset = m.SurveyPoint.objects.filter(is_active=True)
        self.fields["task"].required = False
        self.fields["unit"].required = False
        self.dynamic_names = []
        tpl = template or (self.instance.task.plan.form_template if self.instance.pk and self.instance.task_id else None)
        self.template = tpl
        if tpl:
            existing = (self.instance.data or {}) if self.instance.pk else {}
            for ff in tpl.fields.all():
                name = f"x_{ff.key}"
                self.dynamic_names.append(name)
                if ff.field_type == "number":
                    fld = forms.FloatField(label=ff.label, required=ff.required, min_value=ff.min_value, max_value=ff.max_value)
                elif ff.field_type == "choice":
                    fld = forms.ChoiceField(label=ff.label, required=ff.required,
                                            choices=[("", "---------")] + [(c, c) for c in ff.choice_list()])
                elif ff.field_type == "boolean":
                    fld = forms.BooleanField(label=ff.label, required=False)
                else:
                    fld = forms.CharField(label=ff.label, required=ff.required)
                fld.initial = existing.get(ff.key)
                self.fields[name] = fld
            self._style()

    def clean(self):
        data = super().clean()
        point, task = data.get("point"), data.get("task")
        if task and point and task.point_id != point.pk:
            self.add_error("task", "Nhiệm vụ không thuộc điểm điều tra đã chọn.")
        return data

    def save(self, commit=True):
        obj = super().save(commit=False)
        if obj.task_id:
            obj.plan = obj.task.plan
            if not obj.surveyor_id and obj.task.assignee_id:
                obj.surveyor = obj.task.assignee
        if not obj.surveyor_id and self.user:
            obj.surveyor = self.user
        if not obj.unit_id and obj.surveyor_id and obj.surveyor.unit_id:
            obj.unit = obj.surveyor.unit
        extra = dict(obj.data or {})
        for name in self.dynamic_names:
            extra[name[2:]] = self.cleaned_data.get(name)
        obj.data = extra
        if commit:
            obj.save()
            self.save_m2m()
        return obj


class RecordFilterForm(StyledForm):
    q = forms.CharField(label="Tìm kiếm", required=False)
    status = forms.ChoiceField(label="Trạng thái", required=False, choices=[("", "Tất cả")] + m.SurveyRecord.STATUSES)
    crop = forms.ModelChoiceField(label="Cây trồng", required=False, queryset=cat.Crop.objects.all())
    pest = forms.ModelChoiceField(label="Sinh vật gây hại", required=False, queryset=cat.PestSpecies.objects.all())
    date_from = forms.DateField(label="Từ ngày", required=False)
    date_to = forms.DateField(label="Đến ngày", required=False)


class AttachmentForm(StyledModelForm):
    class Meta:
        model = m.RecordAttachment
        fields = ["file", "caption"]

    def clean_file(self):
        f = self.cleaned_data["file"]
        allowed = ("jpg", "jpeg", "png", "gif", "webp", "pdf", "doc", "docx", "xls", "xlsx")
        ext = f.name.lower().rsplit(".", 1)[-1] if "." in f.name else ""
        if ext not in allowed:
            raise forms.ValidationError("Định dạng tệp không được hỗ trợ.")
        if f.size > 10 * 1024 * 1024:
            raise forms.ValidationError("Tệp vượt quá 10 MB.")
        return f


class ExcelImportForm(StyledForm):
    file = forms.FileField(label="Tệp Excel (.xlsx)")
    valid_only = forms.BooleanField(label="Chỉ nhập các dòng hợp lệ nếu có dòng lỗi", required=False)

    def clean_file(self):
        f = self.cleaned_data["file"]
        if not f.name.lower().endswith(".xlsx"):
            raise forms.ValidationError("Chỉ hỗ trợ tệp .xlsx.")
        if f.size > 10 * 1024 * 1024:
            raise forms.ValidationError("Tệp vượt quá 10 MB.")
        return f


class ReviewForm(StyledForm):
    note = forms.CharField(label="Ý kiến", required=False, widget=forms.Textarea(attrs={"rows": 3}))


class GenerateTasksForm(StyledForm):
    unit = forms.ModelChoiceField(label="Đơn vị thực hiện", required=False, queryset=Unit.objects.filter(is_active=True))
    assignee = forms.ModelChoiceField(label="Cán bộ phụ trách", required=False,
                                      queryset=User.objects.filter(is_active=True))
    due_days = forms.IntegerField(label="Số ngày cho phép hoàn thành sau ngày điều tra", min_value=0, initial=3)
