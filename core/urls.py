from django.http import JsonResponse
from django.urls import path, re_path

from .media import serve_media


def health(request):
    return JsonResponse({"status": "ok"})


app_name = "core"
urlpatterns = [
    path("health/", health, name="health"),
    # Phục vụ tệp tải lên khi chạy thật (DEBUG=0), có kiểm soát truy cập.
    # Đặt trong urls của app "core" để dùng chung, nhưng mount ở gốc "/media/".
    re_path(r"^media/(?P<path>.+)$", serve_media, name="media"),
]
