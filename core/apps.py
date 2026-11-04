from django.apps import AppConfig


class CoreConfig(AppConfig):
    name = "core"
    verbose_name = "Lõi hệ thống"

    def ready(self):
        from . import audit

        audit.register_tracked_models()
