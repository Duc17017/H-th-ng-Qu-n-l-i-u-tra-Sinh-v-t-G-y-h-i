from django.conf import settings
from django.conf.urls.static import static
from django.urls import include, path

urlpatterns = [
    path("", include("cms.urls")),
    path("accounts/", include("accounts.urls")),
    path("catalog/", include("catalog.urls")),
    path("surveys/", include("surveys.urls")),
    path("map/", include("mapview.urls")),
    path("forecasts/", include("forecasts.urls")),
    path("alerts/", include("alerts.urls")),
    path("reports/", include("reports.urls")),
    path("system/", include("sysadmin.urls")),
    path("core/", include("core.urls")),
]
# Lưu ý: khi triển khai thật, file media phải được phục vụ qua web server có kiểm soát truy cập.
if settings.DEBUG:
    urlpatterns += static(settings.MEDIA_URL, document_root=settings.MEDIA_ROOT)
