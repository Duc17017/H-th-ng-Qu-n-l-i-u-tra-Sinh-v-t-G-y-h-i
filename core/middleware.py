import threading

_state = threading.local()


def get_current_user():
    return getattr(_state, "user", None)


def get_current_ip():
    return getattr(_state, "ip", None)


class CurrentUserMiddleware:
    """Lưu người dùng/IP hiện tại để ghi nhật ký thay đổi dữ liệu."""

    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        user = getattr(request, "user", None)
        _state.user = user if user is not None and user.is_authenticated else None
        _state.ip = request.META.get("REMOTE_ADDR")
        try:
            return self.get_response(request)
        finally:
            _state.user = None
            _state.ip = None
