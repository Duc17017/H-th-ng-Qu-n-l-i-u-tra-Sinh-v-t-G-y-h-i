"""Kiểm tra các kết nối ngoài bằng thông tin trong .env. Chạy một lần khi bàn giao hoặc sau khi đổi cấu hình.

    python manage.py check_integrations --email can.bo@donvi.gov.vn
    python manage.py check_integrations --ldap-user ten.dangnhap        (hỏi mật khẩu khi chạy)
    python manage.py check_integrations --sms 0912345678                (gửi một tin thật, có tính phí)

Mỗi mục báo ĐẠT, KHÔNG ĐẠT (kèm lý do) hoặc BỎ QUA (chưa cấu hình). Không in khoá hay mật khẩu.
"""
import getpass
import json
import urllib.request

from django.conf import settings
from django.core.mail import send_mail
from django.core.management.base import BaseCommand


class Command(BaseCommand):
    help = "Thử kết nối email, SMS, LDAP và dịch vụ AI bằng cấu hình hiện tại."

    def add_arguments(self, parser):
        parser.add_argument("--email", help="Địa chỉ nhận thư thử")
        parser.add_argument("--sms", help="Số điện thoại nhận tin thử (gửi thật, có tính phí)")
        parser.add_argument("--ldap-user", help="Tài khoản LDAP để thử đăng nhập")

    def report(self, name, state, detail=""):
        tag = {"ok": "ĐẠT", "fail": "KHÔNG ĐẠT", "skip": "BỎ QUA"}[state]
        self.stdout.write(f"[{tag}] {name}" + (f": {detail}" if detail else ""))
        self.failed = self.failed or state == "fail"

    def handle(self, *args, **opts):
        self.failed = False
        self.check_email(opts["email"])
        self.check_sms(opts["sms"])
        self.check_ldap(opts["ldap_user"])
        self.check_ai()
        if self.failed:
            raise SystemExit(1)

    def check_email(self, to):
        if "console" in settings.EMAIL_BACKEND:
            return self.report("Email", "skip", "chưa đặt EMAIL_HOST, thư chỉ in ra màn hình")
        if not to:
            return self.report("Email", "skip", "thêm --email để gửi thư thử")
        try:
            send_mail("Thư thử từ hệ thống", "Cấu hình email hoạt động.", settings.DEFAULT_FROM_EMAIL, [to])
            self.report("Email", "ok", f"đã gửi tới {to}, hãy kiểm tra hộp thư")
        except Exception as exc:  # noqa: BLE001
            self.report("Email", "fail", str(exc)[:200])

    def check_sms(self, phone):
        if not (settings.ESMS_API_KEY and settings.ESMS_SECRET_KEY):
            return self.report("SMS eSMS", "skip", "chưa đặt ESMS_API_KEY / ESMS_SECRET_KEY")
        url = ("https://rest.esms.vn/MainService.svc/json/GetBalance/"
               f"{settings.ESMS_API_KEY}/{settings.ESMS_SECRET_KEY}/")
        try:
            with urllib.request.urlopen(url, timeout=15) as resp:  # noqa: S310
                data = json.loads(resp.read().decode())
        except Exception as exc:  # noqa: BLE001
            return self.report("SMS eSMS", "fail", f"không gọi được eSMS ({type(exc).__name__})")
        if str(data.get("CodeResponse")) != "100":
            return self.report("SMS eSMS", "fail", f"eSMS từ chối khoá: {data.get('ErrorMessage', data)}")
        self.report("SMS eSMS", "ok", f"khoá hợp lệ, số dư {data.get('Balance')}")
        if phone:
            from core.sms import normalize_phone, send_sms

            number = normalize_phone(phone)
            if not number:
                return self.report("SMS gửi thử", "fail", "số điện thoại không hợp lệ")
            try:
                ok = send_sms(number, "Tin thu tu he thong quan ly dieu tra sinh vat gay hai")
                self.report("SMS gửi thử", "ok" if ok else "fail", f"tới {number}")
            except Exception as exc:  # noqa: BLE001
                self.report("SMS gửi thử", "fail", str(exc)[:200])

    def check_ldap(self, user):
        if not settings.LDAP_SERVER_URI:
            return self.report("LDAP", "skip", "chưa đặt LDAP_SERVER_URI")
        if not user:
            return self.report("LDAP", "skip", "thêm --ldap-user để thử đăng nhập")
        from ldap3 import Connection, Server
        from ldap3.core.exceptions import LDAPException

        pwd = getpass.getpass(f"Mật khẩu LDAP của {user}: ")
        try:
            Connection(Server(settings.LDAP_SERVER_URI, connect_timeout=8),
                       user=settings.LDAP_USER_DN_TEMPLATE.format(username=user), password=pwd, auto_bind=True).unbind()
            self.report("LDAP", "ok", f"{user} đăng nhập được")
        except LDAPException as exc:
            self.report("LDAP", "fail", f"{type(exc).__name__}: {str(exc)[:150]}")

    def check_ai(self):
        from core import llm

        if not llm.enabled():
            return self.report("Trợ lý AI", "skip", "chưa đặt AI_API_URL / AI_API_KEY / AI_MODEL, dùng trợ lý offline")
        text = llm.ask("Bài thử", "Rầy nâu là sinh vật hại lúa.", "Rầy nâu hại cây gì?")
        self.report("Trợ lý AI", "ok" if text else "fail", text[:80] if text else "dịch vụ không trả lời, xem logs/app.log")
