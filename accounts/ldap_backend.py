"""Đăng nhập bằng LDAP / Active Directory. Chỉ hoạt động khi đặt LDAP_SERVER_URI.

Quy trình: xác thực bằng cách "bind" với tài khoản và mật khẩu người dùng nhập. Thành công thì
tìm hoặc tạo tài khoản cục bộ (vai trò mặc định LDAP_DEFAULT_ROLE, không bao giờ là admin).
Mật khẩu không được lưu. Nếu LDAP lỗi hoặc không bật, hệ thống quay về xác thực thường.
"""
import logging

from django.conf import settings
from django.contrib.auth import get_user_model

logger = logging.getLogger(__name__)


def _escape(value):
    from ldap3.utils.conv import escape_filter_chars

    return escape_filter_chars(value)


class LdapBackend:
    def authenticate(self, request, username=None, password=None, **kwargs):
        uri = getattr(settings, "LDAP_SERVER_URI", "")
        template = getattr(settings, "LDAP_USER_DN_TEMPLATE", "")
        if not uri or not template or not username or not password:
            return None
        # Chặn ký tự điều khiển DN/filter để không bị tiêm lệnh vào truy vấn LDAP.
        if any(ch in username for ch in '\\,+"<>;=*()\0/'):
            return None
        from ldap3 import Connection, Server
        from ldap3.core.exceptions import LDAPException

        try:
            server = Server(uri, connect_timeout=8)
            conn = Connection(server, user=template.format(username=username), password=password, auto_bind=True,
                              receive_timeout=8)
        except LDAPException as exc:
            logger.info("LDAP từ chối hoặc không kết nối được cho %s: %s", username, exc)
            return None
        try:
            info = self._lookup(conn, username)
        finally:
            conn.unbind()
        return self._local_user(username, info)

    def _lookup(self, conn, username):
        base = getattr(settings, "LDAP_SEARCH_BASE", "")
        if not base:
            return {}
        q = _escape(username)
        conn.search(base, f"(|(sAMAccountName={q})(uid={q})(userPrincipalName={q}*))",
                    attributes=["givenName", "sn", "cn", "mail", "telephoneNumber"], size_limit=1)
        if not conn.entries:
            return {}
        e = conn.entries[0]

        def val(attr):
            return str(e[attr].value) if attr in e and e[attr].value else ""

        return {"first_name": val("givenName"), "last_name": val("sn") or val("cn"),
                "email": val("mail"), "phone": val("telephoneNumber")}

    def _local_user(self, username, info):
        User = get_user_model()
        try:
            user = User.objects.get(username=username)
        except User.DoesNotExist:
            if not getattr(settings, "LDAP_AUTO_CREATE", True):
                return None
            role = getattr(settings, "LDAP_DEFAULT_ROLE", "viewer")
            if role == "admin":
                role = "viewer"
            user = User(username=username, role=role, is_active=True)
            user.set_unusable_password()
            for k, v in info.items():
                setattr(user, k, v)
            user.save()
            return user
        return user if user.is_active else None

    def get_user(self, user_id):
        User = get_user_model()
        try:
            return User.objects.get(pk=user_id)
        except User.DoesNotExist:
            return None
