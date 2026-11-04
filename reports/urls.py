from django.urls import path

from core.crud import Crud
from core.forms import StyledModelForm
from . import models as m
from . import views as v

app_name = "reports"


class TemplateForm(StyledModelForm):
    class Meta:
        model = m.ReportTemplate
        fields = ["code", "name", "kind", "description", "approved_by", "is_active"]


class ScheduleForm(StyledModelForm):
    class Meta:
        model = m.ReportSchedule
        fields = ["name", "template", "frequency", "fmt", "lookback_days", "recipients", "send_email", "is_active"]


templates = Crud("templates", m.ReportTemplate, TemplateForm, "Mẫu báo cáo", "system",
                 [("Mã", "code"), ("Tên", "name"), ("Loại", "get_kind_display"), ("Áp dụng", "is_active")],
                 search=("code", "name"))
schedules = Crud("schedules", m.ReportSchedule, ScheduleForm, "Lịch tổng hợp, gửi báo cáo", "system",
                 [("Tên", "name"), ("Mẫu", "template"), ("Tần suất", "get_frequency_display"),
                  ("Định dạng", "get_fmt_display"), ("Chạy", "is_active"), ("Lần cuối", "last_run")],
                 search=("name",), select_related=("template",))

urlpatterns = [
    path("dashboard/", v.dashboard, name="dashboard"),
    path("summary/", v.summary, name="summary"),
    path("summary/export/", v.summary_export, name="summary_export"),
    path("", v.report_list, name="list"),
    path("run/<str:code>/", v.report_view, name="view"),
    path("run/<str:code>/export/<str:fmt>/", v.report_export, name="export"),
]
for c in (templates, schedules):
    urlpatterns += c.urls("reports")
