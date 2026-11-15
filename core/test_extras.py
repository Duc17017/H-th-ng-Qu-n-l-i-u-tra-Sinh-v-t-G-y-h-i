"""Kiểm thử các chức năng bổ sung: hàng đợi nền, SMS, LDAP, quên mật khẩu, trợ lý AI tùy chọn."""
import io
import re
from unittest import mock

from django.core import mail
from django.core.cache import cache
from django.test import override_settings
from django.urls import reverse

from accounts.models import User
from alerts import models as am
from alerts import services as asv
from cms import models as cm
from core import sms, tasks
from core.models import BackgroundTask
from core.tests import SeededCase


class SmsHelperTests(SeededCase):
    def test_normalize_phone(self):
        self.assertEqual(sms.normalize_phone("+84 912 345 678"), "0912345678")
        self.assertEqual(sms.normalize_phone("84912345678"), "0912345678")
        self.assertEqual(sms.normalize_phone("0912.345.678"), "0912345678")
        self.assertIsNone(sms.normalize_phone("12345"))
        self.assertIsNone(sms.normalize_phone(""))

    def test_fold_removes_accents(self):
        self.assertEqual(sms.fold("Cảnh báo rầy nâu đồng"), "Canh bao ray nau dong")

    @override_settings(ESMS_API_KEY="", ESMS_SECRET_KEY="")
    def test_without_keys_runs_in_dry_mode(self):
        with self.assertLogs("core.sms", level="INFO"):
            self.assertTrue(sms.send_sms("0912345678", "thử"))
        self.assertFalse(sms.send_sms("abc", "thử"))


@override_settings(TASKS_MODE="eager")
class BackgroundTaskTests(SeededCase):
    def test_task_runs_and_is_marked_done(self):
        calls = []
        tasks.register("t_ok")(lambda **kw: calls.append(kw))
        t = tasks.enqueue("t_ok", x=1)
        t.refresh_from_db()
        self.assertEqual((t.status, calls), ("done", [{"x": 1}]))

    def test_failure_is_retried_then_marked_failed(self):
        def boom(**kw):
            raise RuntimeError("hỏng")

        tasks.register("t_fail")(boom)
        with self.assertLogs("core.tasks", level="ERROR"):
            t = tasks.enqueue("t_fail")
        t.refresh_from_db()
        self.assertEqual((t.status, t.attempts), ("pending", 1))
        self.assertIn("hỏng", t.last_error)
        for _ in range(2):
            BackgroundTask.objects.filter(pk=t.pk).update(run_after="2000-01-01T00:00:00Z")
            with self.assertLogs("core.tasks", level="ERROR"):
                tasks.run_pending()
        t.refresh_from_db()
        self.assertEqual((t.status, t.attempts), ("failed", 3))

    def test_same_task_is_not_run_twice(self):
        calls = []
        tasks.register("t_once")(lambda **kw: calls.append(1))
        t = tasks.enqueue("t_once")
        self.assertFalse(tasks.run_task(t.pk))
        self.assertEqual(len(calls), 1)

    def test_process_tasks_command_runs_pending(self):
        calls = []
        tasks.register("t_cmd")(lambda **kw: calls.append(1))
        with override_settings(TASKS_MODE="worker"):
            t = tasks.enqueue("t_cmd")
        self.assertEqual(t.status, "pending")
        from django.core.management import call_command

        call_command("process_tasks", stdout=io.StringIO())
        t.refresh_from_db()
        self.assertEqual((t.status, len(calls)), ("done", 1))


@override_settings(TASKS_MODE="eager")
class AlertSmsEmailTests(SeededCase):
    def _publish(self, channels):
        al = am.Alert.objects.first()
        al.status, al.channels = "draft", channels
        al.save()
        exp, appr = User.objects.get(username="chuyenmon"), User.objects.get(username="pheduyet")
        asv.transition(al, "submit", exp)
        return al, appr

    def test_publish_sends_sms_and_email_via_queue(self):
        al, appr = self._publish(["notify", "email", "sms"])
        User.objects.filter(pk=appr.pk).update(phone="0912345678", email="a@example.com")
        sent = []
        with mock.patch("core.sms.send_sms", side_effect=lambda n, t: sent.append((n, t)) or True):
            asv.transition(al, "approve", appr)
        self.assertTrue(sent)
        self.assertTrue(all(re.match(r"^0\d{9}$", n) for n, _ in sent))
        self.assertTrue(any("a@example.com" in m.to for m in mail.outbox))
        self.assertEqual(BackgroundTask.objects.filter(status="done").count(), 2)

    def test_sms_failure_does_not_block_publish(self):
        al, appr = self._publish(["sms"])
        User.objects.filter(pk=appr.pk).update(phone="0912345678")
        with mock.patch("core.sms.send_sms", side_effect=OSError("mạng đứt")):
            asv.transition(al, "approve", appr)
        al.refresh_from_db()
        self.assertEqual(al.status, "published")


class LdapBackendTests(SeededCase):
    URI = dict(LDAP_SERVER_URI="ldaps://dc.example.vn", LDAP_USER_DN_TEMPLATE="{username}@example.vn",
               LDAP_SEARCH_BASE="")

    def _backend(self):
        from accounts.ldap_backend import LdapBackend

        return LdapBackend()

    def test_disabled_without_server(self):
        self.assertIsNone(self._backend().authenticate(None, username="x", password="y"))

    def test_rejects_injection_characters(self):
        with override_settings(**self.URI), mock.patch("ldap3.Connection") as conn:
            self.assertIsNone(self._backend().authenticate(None, username="a)(uid=*", password="y"))
            conn.assert_not_called()

    def test_success_creates_viewer_never_admin(self):
        with override_settings(**self.URI, LDAP_DEFAULT_ROLE="admin"), mock.patch("ldap3.Connection"):
            user = self._backend().authenticate(None, username="cb.moi", password="ok")
        self.assertEqual(user.role, "viewer")
        self.assertFalse(user.has_usable_password())

    def test_bad_password_returns_none(self):
        from ldap3.core.exceptions import LDAPBindError

        with override_settings(**self.URI), mock.patch("ldap3.Connection", side_effect=LDAPBindError("sai")):
            self.assertIsNone(self._backend().authenticate(None, username="cb.moi", password="sai"))
        self.assertFalse(User.objects.filter(username="cb.moi").exists())

    def test_inactive_local_user_is_refused(self):
        User.objects.filter(username="xem").update(is_active=False)
        with override_settings(**self.URI), mock.patch("ldap3.Connection"):
            self.assertIsNone(self._backend().authenticate(None, username="xem", password="ok"))

    def test_auto_create_off_refuses_unknown_user(self):
        with override_settings(**self.URI, LDAP_AUTO_CREATE=False), mock.patch("ldap3.Connection"):
            self.assertIsNone(self._backend().authenticate(None, username="la.hoan.toan", password="ok"))


class PasswordResetTests(SeededCase):
    def setUp(self):
        cache.clear()
        User.objects.filter(username="xem").update(email="xem@example.com")

    def test_login_page_links_to_reset(self):
        self.assertContains(self.client.get(reverse("accounts:login")), reverse("accounts:password_reset"))

    def test_known_and_unknown_email_look_the_same(self):
        r1 = self.client.post(reverse("accounts:password_reset"), {"email": "xem@example.com"})
        r2 = self.client.post(reverse("accounts:password_reset"), {"email": "khong.co@example.com"})
        self.assertEqual((r1.status_code, r1.url), (302, reverse("accounts:password_reset_done")))
        self.assertEqual((r2.status_code, r2.url), (302, reverse("accounts:password_reset_done")))
        self.assertEqual(len(mail.outbox), 1)

    def test_link_in_email_sets_new_password_once(self):
        self.client.post(reverse("accounts:password_reset"), {"email": "xem@example.com"})
        link = re.search(r"https?://[^/\s]+(/accounts/forgot/[^\s]+)", mail.outbox[0].body).group(1)
        page = self.client.get(link, follow=True)
        self.assertEqual(page.status_code, 200)
        done = self.client.post(page.request["PATH_INFO"], {"new_password1": "Mat-khau-moi-9x!",
                                                            "new_password2": "Mat-khau-moi-9x!"})
        self.assertRedirects(done, reverse("accounts:password_reset_complete"))
        self.assertTrue(User.objects.get(username="xem").check_password("Mat-khau-moi-9x!"))
        again = self.client.get(link, follow=True)
        self.assertContains(again, "không còn hiệu lực")

    def test_rate_limited_per_ip(self):
        for _ in range(5):
            self.client.post(reverse("accounts:password_reset"), {"email": "xem@example.com"})
        mail.outbox.clear()
        resp = self.client.post(reverse("accounts:password_reset"), {"email": "xem@example.com"})
        self.assertEqual(resp.status_code, 200)
        self.assertEqual(len(mail.outbox), 0)


class OptionalAiTests(SeededCase):
    def setUp(self):
        cache.clear()
        self.post = cm.Post.objects.filter(status="published").first()
        self.login("xem")
        self.url = reverse("cms:post_ask", args=[self.post.slug])

    def test_offline_assistant_used_by_default(self):
        with mock.patch("urllib.request.urlopen") as net:
            resp = self.client.post(self.url, {"question": "rầy nâu là gì"})
        self.assertEqual(resp.status_code, 200)
        net.assert_not_called()

    @override_settings(AI_API_URL="https://ai.example/v1/chat", AI_API_KEY="k", AI_MODEL="m")
    def test_ai_answer_used_when_configured(self):
        fake = mock.MagicMock()
        fake.__enter__.return_value.read.return_value = b'{"choices":[{"message":{"content":"Tra loi AI"}}]}'
        with mock.patch("urllib.request.urlopen", return_value=fake):
            data = self.client.post(self.url, {"question": "tóm tắt?"}).json()
        self.assertEqual(data["answer"], "Tra loi AI")

    @override_settings(AI_API_URL="https://ai.example/v1/chat", AI_API_KEY="k", AI_MODEL="m")
    def test_falls_back_to_offline_when_ai_fails(self):
        with mock.patch("urllib.request.urlopen", side_effect=OSError("down")):
            resp = self.client.post(self.url, {"question": "rầy nâu là gì"})
        self.assertEqual(resp.status_code, 200)
        self.assertIn("ok", resp.json())


class XlsxAutoFitTests(SeededCase):
    def test_columns_fit_content_and_header_is_frozen(self):
        from openpyxl import load_workbook
        from reports import builders as b

        rep = {"title": "T", "summary": [("n", 1)], "headers": ["Mã", "Tiêu đề"],
               "rows": [["A", "x" * 30], ["B", "y" * 300]]}
        ws = load_workbook(io.BytesIO(b.to_xlsx(rep))).active
        self.assertGreater(ws.column_dimensions["B"].width, ws.column_dimensions["A"].width)
        self.assertEqual(ws.column_dimensions["B"].width, 60)  # chặn ở mức tối đa, ô tự xuống dòng
        self.assertEqual(ws.freeze_panes, "A6")
        self.assertTrue(ws.auto_filter.ref.startswith("A5"))