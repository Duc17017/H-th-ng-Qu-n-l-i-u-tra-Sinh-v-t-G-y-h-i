from django.urls import path

from core.crud import Crud
from . import forms as f
from . import models as m
from . import views as v

app_name = "surveys"

editable_if_open = lambda user, obj: True  # noqa: E731

templates_crud = Crud("templates", m.FormTemplate, f.FormTemplateForm, "Biểu mẫu điều tra", "plans",
                      [("Mã", "code"), ("Tên", "name"), ("Cây trồng", "crop"), ("Đối tượng", "pest"),
                       ("Phiên bản", "version"), ("Áp dụng", "is_active")],
                      search=("code", "name"), filters=("crop", "is_active"), select_related=("crop", "pest"))
fields_crud = Crud("fields", m.FormField, f.FormFieldForm, "Trường biểu mẫu", "plans",
                   [("Biểu mẫu", "template"), ("Khóa", "key"), ("Nhãn", "label"), ("Kiểu", "get_field_type_display"),
                    ("Bắt buộc", "required"), ("Thứ tự", "order")],
                   search=("key", "label"), filters=("template", "field_type"), select_related=("template",))
routes_crud = Crud("routes", m.SurveyRoute, f.RouteForm, "Tuyến điều tra", "plans",
                   [("Kế hoạch", "plan"), ("Mã", "code"), ("Tên tuyến", "name"), ("Đơn vị", "unit")],
                   search=("code", "name"), filters=("plan",), select_related=("plan", "unit"))
points_crud = Crud("points", m.SurveyPoint, f.PointForm, "Điểm điều tra", "plans",
                   [("Mã", "code"), ("Tên", "name"), ("Tuyến", "route"), ("Địa bàn", "division"),
                    ("Vĩ độ", "latitude"), ("Kinh độ", "longitude")],
                   search=("code", "name", "address"), filters=("division", "is_active"),
                   list_qs=lambda r: v.points_for(r.user), select_related=("route", "division"))
tasks_crud = Crud("tasks", m.SurveyTask, f.TaskForm, "Nhiệm vụ điều tra", "plans",
                  [("Kế hoạch", "plan.code"), ("Điểm", "point"), ("Ngày điều tra", "survey_date"),
                   ("Hạn", "due_date"), ("Phụ trách", "assignee"), ("Trạng thái", "get_status_display")],
                  search=("point__name", "point__code", "plan__code"), filters=("status", "plan"),
                  list_qs=lambda r: v.tasks_for(r.user), select_related=("plan", "point", "assignee"))

urlpatterns = [
    path("plans/", v.plan_list, name="plan_list"),
    path("plans/new/", v.plan_create, name="plan_create"),
    path("plans/<int:pk>/", v.plan_detail, name="plan_detail"),
    path("plans/<int:pk>/edit/", v.plan_edit, name="plan_edit"),
    path("plans/<int:pk>/action/<str:action>/", v.plan_action, name="plan_action"),
    path("plans/<int:pk>/generate/", v.plan_generate, name="plan_generate"),
    path("my-tasks/", v.task_list, name="task_list"),
    path("my-tasks/<int:pk>/start/", v.task_start, name="task_start"),
    path("records/", v.record_list, name="record_list"),
    path("records/new/", v.record_create, name="record_create"),
    path("records/<int:pk>/", v.record_detail, name="record_detail"),
    path("records/<int:pk>/edit/", v.record_edit, name="record_edit"),
    path("records/<int:pk>/action/<str:action>/", v.record_action, name="record_action"),
    path("records/<int:pk>/attach/", v.record_attach, name="record_attach"),
    path("attachments/<int:pk>/delete/", v.attachment_delete, name="attachment_delete"),
    path("api/plans/<int:plan_id>/fields/", v.form_fields_api, name="form_fields_api"),
    path("template-catalog/", v.template_catalog, name="template_catalog"),
    path("template/<int:pk>/edit-struct/", v.template_detail_edit, name="template_edit_struct"),
    path("sandbox/", v.sandbox_simulator, name="sandbox"),
    path("api/sandbox/simulate/", v.api_sandbox_simulate, name="api_sandbox_simulate"),
    path("offline/", v.offline_page, name="offline"),
    path("api/sync/", v.sync_api, name="sync_api"),
    path("import/", v.import_page, name="import"),
    path("import/template/", v.import_template, name="import_template"),
]
for c in (templates_crud, fields_crud, routes_crud, points_crud, tasks_crud):
    urlpatterns += c.urls("surveys")
