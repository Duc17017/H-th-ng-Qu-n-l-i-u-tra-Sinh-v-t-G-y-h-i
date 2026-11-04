from django.utils import timezone
from django.utils.functional import SimpleLazyObject

from .permissions import MODULES, landing_url, perm_map


def _live_alert():
    from alerts.models import Alert

    today = timezone.localdate()
    return Alert.objects.filter(status__in=['published', 'updated'], valid_from__lte=today, valid_to__gte=today).order_by('-published_at').first()


def _current_season():
    from catalog.models import Season

    today = timezone.localdate()
    return Season.objects.filter(start_date__lte=today, end_date__gte=today).first() or Season.objects.first()


def app_context(request):
    ctx = {"APP_NAME": "Hệ thống quản lý điều tra sinh vật gây hại", "MODULES": MODULES}
    user = getattr(request, "user", None)
    if user is not None and user.is_authenticated:
        from .models import Notification

        ctx["perms_map"] = perm_map(user)
        ctx["unread_count"] = Notification.objects.filter(user=user, is_read=False).count()
    else:
        ctx["perms_map"] = {}
        ctx["unread_count"] = 0
    ctx["live_alert"] = SimpleLazyObject(_live_alert)
    ctx["current_season"] = SimpleLazyObject(_current_season)
    if user is not None and user.is_authenticated:
        ctx["home_url"] = SimpleLazyObject(lambda: landing_url(user))
    else:
        ctx["home_url"] = "/"
    return ctx
