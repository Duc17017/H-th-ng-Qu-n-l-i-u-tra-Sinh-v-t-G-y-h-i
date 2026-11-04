from django.urls import path

from . import views as v

app_name = "alerts"

urlpatterns = [
    path("alerts/", v.alert_list, name="alert_list"),
    path("alerts/new/", v.alert_create, name="alert_create"),
    path("alerts/from-forecast/<int:forecast_id>/", v.alert_from_forecast, name="alert_from_forecast"),
    path("alerts/<int:pk>/", v.alert_detail, name="alert_detail"),
    path("alerts/<int:pk>/edit/", v.alert_edit, name="alert_edit"),
    path("alerts/<int:pk>/action/<str:action>/", v.alert_action, name="alert_action"),
    path("followups/", v.followup_list, name="followup_list"),
    path("followups/new/", v.followup_create, name="followup_create"),
    path("followups/<int:pk>/", v.followup_detail, name="followup_detail"),
    path("followups/<int:pk>/report/", v.followup_report, name="followup_report"),
]
