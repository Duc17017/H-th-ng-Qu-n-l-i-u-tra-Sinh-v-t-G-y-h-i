from django.apps import AppConfig


class AccountsConfig(AppConfig):
    name = "accounts"
    verbose_name = "Tài khoản"

    def ready(self):
        # Import để đăng ký receiver. Phải nằm trong module cấp cao (accounts/signals.py),
        # không được định nghĩa closure ở đây — xem giải thích trong signals.py.
        from . import signals  # noqa: F401
