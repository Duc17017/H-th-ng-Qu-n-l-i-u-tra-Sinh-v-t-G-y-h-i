from django.conf import settings
from django.conf.urls.static import static
from django.urls import include, path, re_path

from core.media import serve_media

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

# Tệp tải lên: khi DEBUG=1 thì Django tự phục vụ; khi chạy thật phải có đường dẫn riêng,
# nếu không toàn bộ ảnh hiện trường, ảnh bìa bài viết và tệp báo cáo sẽ trả 404.
if settings.DEBUG:
    urlpatterns += static(settings.MEDIA_URL, document_root=settings.MEDIA_ROOT)
else:
    urlpatterns += [re_path(r"^media/(?P<path>.+)$", serve_media, name="media_serve")]
