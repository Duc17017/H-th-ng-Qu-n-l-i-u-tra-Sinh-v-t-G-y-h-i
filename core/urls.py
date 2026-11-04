from django.http import JsonResponse
from django.urls import path


def health(request):
    return JsonResponse({"status": "ok"})


app_name = "core"
urlpatterns = [path("health/", health, name="health")]
