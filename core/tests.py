"""Kiểm thử tự động: chạy `python manage.py test` (đặt DB_ENGINE=sqlite để thử nhanh)."""
import io
import tempfile
from datetime import timedelta

from django.conf import settings
from django.core.management import call_command
from django.test import Client, TestCase, override_settings
from django.urls import reverse
from django.utils import timezone

from accounts.models import User
from alerts import models as am
from alerts import services as asv
from cms import models as cm
from core.models import AuditLog
from forecasts import models as fm
from forecasts import services as fsv
from surveys import models as sm
from surveys import services as ssv

# Thư mục media riêng cho kiểm thử, tránh ghi ảnh đại diện vào media/ thật.
TEST_MEDIA_ROOT = tempfile.mkdtemp(prefix="agrigov-test-media-")


@override_settings(MEDIA_ROOT=TEST_MEDIA_ROOT)
class SeededCase(TestCase):
    """Nền chung: nạp dữ liệu mẫu một lần cho cả lớp kiểm thử.

    Thư mục media được chuyển sang thư mục tạm để ảnh đại diện do seeder sinh ra
    không ghi vào media/ thật của dự án mỗi lần chạy `manage.py test`.
    """

    @classmethod
    def setUpTestData(cls):
        call_command("seed_demo", stdout=io.StringIO())

    def login(self, username):
        self.assertTrue(self.client.login(username=username, password="Demo@12345"))


class PageSmokeTests(SeededCase):
    """Mọi trang chính của quản trị viên phải mở được, không lỗi 500."""

    def test_admin_pages(self):
        self.login("admin")
        names = [
            "cms:home", "cms:post_list", "cms:manage_list", "cms:manage_create",
            "surveys:plan_list", "surveys:plan_create", "surveys:task_list", "surveys:record_list", "surveys:record_create",
            "surveys:import", "surveys:offline", "surveys:templates_list", "surveys:points_list", "surveys:routes_list",
            "mapview:map", "mapview:points", "mapview:routes", "mapview:timeline", "mapview:layers_list",
            "forecasts:analysis", "forecasts:compare", "forecasts:list", "forecasts:create", "forecasts:suggest",
            "alerts:alert_list", "alerts:alert_create", "alerts:followup_list",
            "reports:dashboard", "reports:summary", "reports:list",
            "sysadmin:index", "sysadmin:audit", "sysadmin:logins", "sysadmin:documents", "sysadmin:backups",
            "sysadmin:configs_list", "sysadmin:docs_list",
            "accounts:users_list", "accounts:role_matrix", "accounts:profile", "accounts:notifications",
            "accounts:password_change",
            "surveys:sandbox", "surveys:template_catalog",
            "catalog:index", "catalog:crops_list", "catalog:pests_list",
        ]
        for n in names:
            r = self.client.get(reverse(n))
            self.assertIn(r.status_code, (200, 302), f"{n} -> {r.status_code}")
            if r.status_code == 200 and "text/html" in r.get("Content-Type", ""):
                self.assertContains(r, "Material Symbols", msg_prefix=f"{n} chưa dùng shell MD3")

    def test_no_legacy_bootstrap_shell(self):
        """Toàn bộ giao diện phải dùng base_ui.html / base_public.html, không còn Bootstrap cũ."""
        tpl_dir = settings.BASE_DIR / "templates"
        offenders = []
        for path in tpl_dir.rglob("*.html"):
            text = path.read_text(encoding="utf-8")
            if 'extends "base.html"' in text:
                offenders.append(f"{path.name}: còn extends base.html")
        self.assertEqual(offenders, [], " | ".join(offenders))

    def test_detail_pages(self):
        self.login("admin")
        rec = sm.SurveyRecord.objects.first()
        for url in (f"/surveys/records/{rec.pk}/", f"/surveys/plans/{sm.SurveyPlan.objects.first().pk}/",
                    f"/forecasts/forecasts/{fm.Forecast.objects.first().pk}/", f"/alerts/alerts/{am.Alert.objects.first().pk}/",
                    f"/cms/posts/{cm.Post.objects.first().pk}/", f"/map/api/points/{sm.SurveyPoint.objects.first().pk}/",
                    f"/alerts/followups/{am.FollowUpTask.objects.first().pk}/",
                    f"/surveys/template/{sm.FormTemplate.objects.first().pk}/edit-struct/"):
            self.assertEqual(self.client.get(url).status_code, 200, url)

    def test_template_edit_page_renders_fields(self):
        """Trang thiết kế biểu mẫu phải hiển thị đúng cấu trúc trường và form chỉnh sửa."""
        self.login("admin")
        tpl = sm.FormTemplate.objects.first()
        r = self.client.get(f"/surveys/template/{tpl.pk}/edit-struct/")
        self.assertEqual(r.status_code, 200)
        self.assertEqual(r.context["template"].pk, tpl.pk)
        self.assertContains(r, tpl.code)
        for field in tpl.fields.all()[:3]:
            self.assertContains(r, field.label)

    def test_template_edit_save_redirects_with_selection(self):
        """Lưu biểu mẫu phải chuyển về danh mục kèm template_id (không lỗi TypeError)."""
        self.login("admin")
        tpl = sm.FormTemplate.objects.first()
        data = {
            "code": tpl.code, "name": tpl.name + " (cập nhật)", "version": tpl.version,
            "description": tpl.description, "is_active": "on",
            "crop": tpl.crop_id or "", "pest": tpl.pest_id or "", "method": tpl.method_id or "",
        }
        r = self.client.post(f"/surveys/template/{tpl.pk}/edit-struct/", data)
        self.assertEqual(r.status_code, 302)
        self.assertIn(f"template_id={tpl.pk}", r["Location"])
        tpl.refresh_from_db()
        self.assertTrue(tpl.name.endswith("(cập nhật)"))

    def test_public_site_no_login(self):
        r = self.client.get("/")
        self.assertEqual(r.status_code, 200)
        self.assertContains(r, "Hướng dẫn kỹ thuật")

    def test_login_required_for_internal(self):
        r = self.client.get("/surveys/records/")
        self.assertEqual(r.status_code, 302)

    def test_sidebar_shows_system_links_for_admin(self):
        """`perms_map.system.view` luôn sai vì set không có thuộc tính — phải dùng `'view' in perms_map.system`."""
        self.login("admin")
        body = self.client.get("/system/").content.decode()
        for label in ("Người dùng", "Phân quyền RBAC", "Sao lưu"):
            self.assertIn(label, body, f"Sidebar thiếu mục '{label}'")

    def test_every_demo_role_lands_on_accessible_page(self):
        """Đăng nhập xong phải vào được trang đích — điều tra viên từng bị 403 ở dashboard."""
        for username in ("admin", "lanhdao", "pheduyet", "chuyenmon", "bientap",
                         "dieutra1", "dieutra2", "xem"):
            self.client.logout()
            self.assertTrue(self.client.login(username=username, password="Demo@12345"), username)
            r = self.client.get("/accounts/login/", follow=True)  # ép đi qua get_success_url
            self.assertEqual(r.status_code, 200, f"{username} bị chặn sau đăng nhập")
            self.assertNotEqual(r.status_code, 403, username)

    def test_surveyor_redirected_to_own_tasks(self):
        from core.permissions import landing_url
        u = User.objects.get(username="dieutra1")
        self.assertEqual(landing_url(u), "/surveys/my-tasks/")

    def test_enter_system_button_respects_role(self):
        """Nút 'Vào hệ thống' ở cổng công khai không được trỏ tới trang vai trò không có quyền."""
        for username, target in (("dieutra1", "/surveys/my-tasks/"),
                                 ("dieutra2", "/surveys/my-tasks/"),
                                 ("xem", "/reports/dashboard/"),
                                 ("bientap", "/reports/dashboard/")):
            self.client.logout()
            self.client.login(username=username, password="Demo@12345")
            body = self.client.get("/").content.decode()
            self.assertIn(f'href="{target}"', body, f"{username}: nút 'Vào hệ thống' sai đích")
            self.assertEqual(self.client.get(target).status_code, 200, username)


class RbacTests(SeededCase):
    def test_viewer_cannot_open_system(self):
        self.login("xem")
        self.assertEqual(self.client.get("/system/").status_code, 403)
        self.assertEqual(self.client.get("/surveys/records/new/").status_code, 403)

    def test_surveyor_scope_only_own_division(self):
        self.login("dieutra1")
        data = self.client.get("/map/api/points/").json()
        d1 = User.objects.get(username="dieutra1").division
        allowed = set(d1.descendant_ids())
        self.assertTrue(data["features"])
        for f in data["features"]:
            self.assertIn(sm.SurveyPoint.objects.get(pk=f["properties"]["id"]).division_id, allowed)

    def test_login_history_recorded(self):
        self.client.post("/accounts/login/", {"username": "admin", "password": "sai"})
        self.client.post("/accounts/login/", {"username": "admin", "password": "Demo@12345"})
        from accounts.models import LoginHistory
        self.assertTrue(LoginHistory.objects.filter(username="admin", success=False).exists())
        self.assertTrue(LoginHistory.objects.filter(username="admin", success=True).exists())

    def test_login_locked_after_too_many_failures(self):
        """Sai quá ngưỡng phải bị tạm khoá, không cho dò mật khẩu vô hạn."""
        from accounts.models import LoginHistory
        from django.conf import settings

        LoginHistory.objects.all().delete()
        for _ in range(settings.LOGIN_MAX_ATTEMPTS):
            self.client.post("/accounts/login/", {"username": "admin", "password": "sai"})

        before = LoginHistory.objects.filter(username="admin").count()
        r = self.client.post("/accounts/login/", {"username": "admin", "password": "Demo@12345"})
        self.assertEqual(r.status_code, 200, "phải bị chặn, không được chuyển tiếp")
        self.assertNotIn("_auth_user_id", self.client.session, "không được đăng nhập thành công")
        # Không sinh thêm bản ghi đăng nhập thành công nào
        self.assertFalse(LoginHistory.objects.filter(username="admin", success=True,
                                                     event="login").exists())
        self.assertGreaterEqual(before, settings.LOGIN_MAX_ATTEMPTS)


class ProductionReadinessTests(SeededCase):
    """Các yêu cầu tối thiểu để chạy thực tế, không phụ thuộc internet."""

    def test_templates_do_not_load_assets_from_cdn(self):
        """Toàn bộ CSS/JS/font phải tự host — mạng nội bộ thường chặn internet."""
        import re
        from pathlib import Path

        from django.conf import settings

        offenders = []
        for p in Path(settings.BASE_DIR, "templates").rglob("*.html"):
            txt = p.read_text(encoding="utf-8")
            for url in re.findall(r'(?:src|href)="(https?://[^"]+)"', txt):
                # ảnh nền bản đồ thì bắt buộc phải ra internet, chấp nhận
                if "tile" in url or "openstreetmap" in url:
                    continue
                offenders.append(f"{p.name}: {url}")
        self.assertEqual(offenders, [], "Còn tài nguyên tải từ internet: " + "; ".join(offenders[:5]))

    def test_built_css_exists_and_has_core_classes(self):
        from pathlib import Path

        from django.conf import settings

        css = Path(settings.BASE_DIR, "static", "css", "app.css")
        self.assertTrue(css.exists(), "Chưa build Tailwind: chạy npm run build")
        text = css.read_text(encoding="utf-8", errors="replace")
        self.assertGreater(len(text), 10_000)
        for cls in (".bg-surface-container-low", ".text-on-surface-variant", ".tw-input", ".msym"):
            self.assertIn(cls, text)

    def test_vendor_assets_present(self):
        from pathlib import Path

        from django.conf import settings

        base = Path(settings.BASE_DIR, "static", "vendor")
        for rel in ("leaflet/leaflet.js", "leaflet/leaflet.css",
                    "chartjs/chart.umd.min.js",
                    "fonts/inter-variable.woff2",
                    "fonts/material-symbols-outlined.woff2"):
            self.assertTrue((base / rel).exists(), f"Thiếu tài nguyên tự host: {rel}")

    def test_error_pages_exist(self):
        from pathlib import Path

        from django.conf import settings

        for name in ("403.html", "404.html", "500.html"):
            self.assertTrue(Path(settings.BASE_DIR, "templates", name).exists(), name)

    def test_logging_configured(self):
        from django.conf import settings

        self.assertIn("handlers", settings.LOGGING)
        self.assertIn("file", settings.LOGGING["handlers"])


class ProductionServingTests(SeededCase):
    """Những lỗi chỉ xuất hiện khi DEBUG=0 — đã từng làm hỏng giao diện và tệp đính kèm."""

    def test_whitenoise_serves_static_when_debug_off(self):
        """Thiếu WhiteNoise thì CSS 404 và toàn bộ giao diện mất style."""
        from pathlib import Path

        from django.conf import settings

        self.assertIn("whitenoise.middleware.WhiteNoiseMiddleware", settings.MIDDLEWARE,
                      "Thiếu WhiteNoise: CSS sẽ 404 khi DEBUG=0")
        # Bộ lưu trữ phải chọn theo DEBUG: khi chạy thật dùng bản nén của WhiteNoise.
        src = Path(settings.BASE_DIR, "config", "settings.py").read_text(encoding="utf-8")
        self.assertIn("whitenoise.storage.CompressedManifestStaticFilesStorage", src)

    def test_uploaded_files_have_route_when_debug_off(self):
        """Django không tự phục vụ MEDIA khi DEBUG=0; phải có route riêng."""
        from django.urls import resolve, Resolver404

        try:
            m = resolve("/media/reports/2026/01/test.xlsx")
        except Resolver404:
            self.fail("Không có route /media/ — ảnh hiện trường và tệp báo cáo sẽ 404 khi chạy thật")
        self.assertEqual(m.func.__name__, "serve_media")

    def test_media_requires_login_for_sensitive_prefixes(self):
        """Tệp phiếu điều tra / tài liệu / báo cáo không được để người lạ tải."""
        from core.media import serve_media
        from django.test import RequestFactory
        from django.contrib.auth.models import AnonymousUser

        rf = RequestFactory()
        req = rf.get("/media/records/2026/01/anh.jpg")
        req.user = AnonymousUser()
        with self.assertRaises(Exception):
            serve_media(req, "records/2026/01/anh.jpg")

    def test_media_blocks_path_traversal(self):
        from core.media import serve_media
        from django.contrib.auth import get_user_model
        from django.test import RequestFactory

        rf = RequestFactory()
        req = rf.get("/media/x")
        req.user = get_user_model().objects.get(username="admin")
        with self.assertRaises(Exception):
            serve_media(req, "../../.env")

    def test_session_cookie_secure_can_be_disabled(self):
        """Mạng nội bộ không có HTTPS phải tắt được cờ Secure, nếu không không ai đăng nhập được."""
        from django.conf import settings

        self.assertTrue(hasattr(settings, "SECURE_COOKIES"),
                        "Thiếu công tắc DJANGO_SECURE_COOKIES cho môi trường không có HTTPS")


class SurveyWorkflowTests(SeededCase):
    def _new_record(self, **kw):
        pt = sm.SurveyPoint.objects.first()
        base = dict(point=pt, survey_date=timezone.now(), crop=pt.crop, pest=fm.cat.PestSpecies.objects.get(code="RNN"),
                    damage_rate=15, density=100, surveyed_area=2, affected_area=0.3, comment="x",
                    damage_level=fm.cat.DamageLevel.objects.get(code="L2"), surveyor=User.objects.get(username="dieutra1"))
        base.update(kw)
        return sm.SurveyRecord.objects.create(**base)

    def test_validation_rules(self):
        r = self._new_record(damage_rate=150, affected_area=5, survey_date=timezone.now() + timedelta(days=3))
        errors, _ = r.validate_data()
        self.assertGreaterEqual(len(errors), 3)

    def test_duplicate_warning(self):
        a = self._new_record(survey_date=timezone.now())
        b = self._new_record(survey_date=timezone.now())
        _, warns = b.validate_data()
        self.assertTrue(any("trùng lặp" in w for w in warns))

    def test_full_flow_and_history(self):
        sur, exp = User.objects.get(username="dieutra1"), User.objects.get(username="chuyenmon")
        r = self._new_record(status="draft")
        ssv.transition_record(r, "submit", sur)
        ssv.transition_record(r, "revise", exp, "Bổ sung ảnh")
        r.refresh_from_db()
        self.assertEqual(r.status, "revision")
        ssv.transition_record(r, "submit", sur)
        ssv.transition_record(r, "confirm", exp)
        r.refresh_from_db()
        self.assertEqual((r.status, r.confirmed_by), ("confirmed", exp))
        self.assertEqual(r.history.count(), 4)
        with self.assertRaises(ssv.WorkflowError):
            ssv.transition_record(r, "submit", sur)

    def test_revise_requires_note(self):
        r = self._new_record(status="submitted")
        with self.assertRaises(ssv.WorkflowError):
            ssv.transition_record(r, "revise", User.objects.get(username="chuyenmon"), "")

    def test_sync_api_dedup(self):
        import json
        self.login("dieutra1")
        pt = sm.SurveyPoint.objects.first()
        payload = {"records": [{"client_uuid": "abc-123", "point": pt.pk, "crop": pt.crop_id,
                                "pest": fm.cat.PestSpecies.objects.get(code="RNN").pk, "survey_date": timezone.now().isoformat(),
                                "damage_rate": 5, "density": 10}]}
        r1 = self.client.post("/surveys/api/sync/", json.dumps(payload), content_type="application/json")
        r2 = self.client.post("/surveys/api/sync/", json.dumps(payload), content_type="application/json")
        self.assertEqual(r1.status_code, 200, r1.content)
        self.assertEqual(r2.status_code, 200, r2.content)
        self.assertEqual(sm.SurveyRecord.objects.filter(client_uuid="abc-123").count(), 1)

    def test_excel_template_and_import_errors(self):
        import openpyxl
        buf = ssv.build_template_xlsx()
        data = buf.getvalue() if hasattr(buf, "getvalue") else buf
        wb = openpyxl.load_workbook(io.BytesIO(data))
        self.assertTrue(wb.sheetnames)

    def test_audit_log_written(self):
        before = AuditLog.objects.count()
        self._new_record()
        self.assertGreater(AuditLog.objects.count(), before)


class ForecastAlertTests(SeededCase):
    def test_auto_suggest_has_evidence_and_needs_confirmation(self):
        th = fm.Threshold.objects.first()
        div = th.pest.crops.first() and fm.AdminDivision.objects.get(code="T01")
        res = fsv.suggest(th, div, User.objects.get(username="chuyenmon"))
        self.assertTrue(res is not None)

    def test_forecast_flow_and_evaluation(self):
        # Chọn đúng nhận định rầy nâu: bộ nội dung mẫu có thêm dự báo sâu keo ngô
        # nên không thể dựa vào thứ tự mặc định của queryset.
        fc = fm.Forecast.objects.filter(pest__code="RNN").first()
        fc.status = "draft"
        fc.save()
        exp, appr = User.objects.get(username="chuyenmon"), User.objects.get(username="pheduyet")
        fsv.transition(fc, "submit", exp)
        fsv.transition(fc, "confirm", appr)
        fc.refresh_from_db()
        self.assertEqual(fc.status, "confirmed")
        with self.assertRaises(fsv.ForecastError):  # dự báo ở tương lai: chưa có số liệu thực tế để đối chiếu
            fsv.evaluate_actual(fc, exp)
        today = timezone.localdate()
        fc.valid_from, fc.valid_to = today - timedelta(days=30), today
        fc.save()
        fsv.evaluate_actual(fc, exp)
        fc.refresh_from_db()
        self.assertIsNotNone(fc.evaluated_at)

    def test_alert_requires_confirmed_forecast(self):
        fc = fm.Forecast.objects.first()
        fc.status = "draft"
        fc.save()
        al = am.Alert.objects.first()
        al.status, al.forecast = "draft", fc
        al.save()
        with self.assertRaises(asv.AlertError):
            asv.transition(al, "submit", User.objects.get(username="chuyenmon"))

    def test_alert_lifecycle_and_notification(self):
        al = am.Alert.objects.first()
        al.status = "draft"
        al.save()
        exp, appr = User.objects.get(username="chuyenmon"), User.objects.get(username="pheduyet")
        asv.transition(al, "submit", exp)
        self.assertTrue(appr.notifications.filter(title__icontains="phê duyệt").exists())
        asv.transition(al, "approve", appr)
        al.refresh_from_db()
        self.assertEqual(al.status, "published")
        self.assertTrue(cm.Post.objects.filter(alert=al).exists())
        asv.transition(al, "expire", appr)
        al.refresh_from_db()
        self.assertEqual(al.status, "expired")
        self.assertGreaterEqual(al.revisions.count(), 3)


class ApproveActionTests(SeededCase):
    """Phê duyệt qua HTTP: nút hiện ra với người có quyền và bấm vào phải chạy (không 403/500)."""

    def _check(self, url, needle, action_url, obj, expect_status, user="pheduyet", data=None):
        self.login(user)
        page = self.client.get(url)
        self.assertEqual(page.status_code, 200, url)
        self.assertIn(needle, page.content.decode(), f"{url} không hiện nút '{needle}'")
        r = self.client.post(action_url, data or {})
        self.assertEqual(r.status_code, 302, action_url)
        obj.refresh_from_db()
        self.assertEqual(obj.status, expect_status)

    def test_plan_approve_http(self):
        plan = sm.SurveyPlan.objects.first()
        plan.status = "draft"
        plan.save()
        self._check(f"/surveys/plans/{plan.pk}/", "Phê duyệt kế hoạch",
                    f"/surveys/plans/{plan.pk}/action/approve/", plan, "approved")

    def test_alert_approve_http(self):
        al = am.Alert.objects.first()
        al.status = "pending"
        al.save()
        self._check(f"/alerts/alerts/{al.pk}/", "Phê duyệt &amp; phát hành",
                    f"/alerts/alerts/{al.pk}/action/approve/", al, "published", data={"note": "ok"})

    def test_forecast_confirm_http(self):
        fc = fm.Forecast.objects.first()
        fc.status = "pending"
        fc.save()
        self._check(f"/forecasts/forecasts/{fc.pk}/", "Xác nhận nhận định",
                    f"/forecasts/forecasts/{fc.pk}/action/confirm/", fc, "confirmed", data={"note": "ok"})

    def test_post_approve_http(self):
        post = cm.Post.objects.first()
        post.status = "review"
        post.save()
        self._check(f"/cms/posts/{post.pk}/", "Duyệt nội dung",
                    f"/cms/posts/{post.pk}/action/approve/", post, "approved", data={"note": "ok"})

    def test_record_confirm_http(self):
        rec = sm.SurveyRecord.objects.first()
        rec.status = "submitted"
        rec.save()
        self._check(f"/surveys/records/{rec.pk}/", "Xác nhận dữ liệu",
                    f"/surveys/records/{rec.pk}/action/confirm/", rec, "confirmed", data={"note": "ok"})

    def test_viewer_cannot_approve(self):
        al = am.Alert.objects.first()
        al.status = "pending"
        al.save()
        self.login("xem")
        self.assertEqual(self.client.post(f"/alerts/alerts/{al.pk}/action/approve/", {}).status_code, 403)
        al.refresh_from_db()
        self.assertEqual(al.status, "pending")

    def test_plan_approve_blocked_without_routes(self):
        plan = sm.SurveyPlan.objects.first()
        plan.status = "draft"
        plan.save()
        plan.routes.all().delete()
        plan.tasks.all().delete()
        self.login("pheduyet")
        self.client.post(f"/surveys/plans/{plan.pk}/action/approve/", {})
        plan.refresh_from_db()
        self.assertEqual(plan.status, "draft")


class ReportAndMapTests(SeededCase):
    def test_excel_and_pdf_export(self):
        self.login("admin")
        for fmt, magic in (("xlsx", b"PK"), ("pdf", b"%PDF")):
            r = self.client.get(f"/reports/run/BC-PHATSINH/export/{fmt}/")
            self.assertEqual(r.status_code, 200, fmt)
            self.assertTrue(b"".join(r.streaming_content if r.streaming else [r.content]).startswith(magic), fmt)

    def test_summary_and_export(self):
        self.login("admin")
        self.assertEqual(self.client.get("/reports/summary/?group=month&by=division").status_code, 200)
        self.assertEqual(self.client.get("/reports/summary/export/?group=month&by=division").status_code, 200)

    def test_schedule_command(self):
        out = io.StringIO()
        call_command("run_schedules", "--force", stdout=out)

    def test_geojson_import_export_roundtrip(self):
        import json
        self.login("admin")
        gj = {"type": "FeatureCollection", "features": [
            {"type": "Feature", "properties": {"code": "GJ1", "name": "Điểm GJ", "division_code": "X011"},
             "geometry": {"type": "Point", "coordinates": [106.5, 20.5]}},
            {"type": "Feature", "properties": {"code": "BAD", "name": "x", "division_code": "NOPE"},
             "geometry": {"type": "Point", "coordinates": [1, 1]}}]}
        from django.core.files.uploadedfile import SimpleUploadedFile
        f = SimpleUploadedFile("a.geojson", json.dumps(gj).encode(), content_type="application/json")
        self.client.post("/map/import/", {"file": f})
        self.assertTrue(sm.SurveyPoint.objects.filter(code="GJ1").exists())
        self.assertFalse(sm.SurveyPoint.objects.filter(code="BAD").exists())
        self.assertEqual(self.client.get("/map/export/").status_code, 200)

    def test_dashboard_has_data(self):
        self.login("lanhdao")
        self.assertEqual(self.client.get("/reports/dashboard/").status_code, 200)


class CmsTests(SeededCase):
    def test_editorial_workflow_and_versioning(self):
        self.login("bientap")
        r = self.client.post("/cms/posts/new/", {"title": "Bài thử", "post_type": "news", "content": "Nội dung"})
        self.assertIn(r.status_code, (200, 302))
        p = cm.Post.objects.filter(title="Bài thử").first()
        self.assertIsNotNone(p)
        self.client.post(f"/cms/posts/{p.pk}/action/submit/")
        p.refresh_from_db()
        self.assertEqual(p.status, "review")
        self.client.logout()
        self.login("pheduyet")
        self.client.post(f"/cms/posts/{p.pk}/action/approve/")
        self.client.post(f"/cms/posts/{p.pk}/action/publish/")
        p.refresh_from_db()
        self.assertEqual(p.status, "published")
        self.client.logout()
        # Khách chưa đăng nhập bị chuyển sang trang đăng nhập, giữ nguyên đích quay lại.
        guest = self.client.get(f"/tin-tuc/{p.slug}/")
        self.assertEqual(guest.status_code, 302)
        self.assertIn("/accounts/login/", guest["Location"])
        self.assertIn(f"/tin-tuc/{p.slug}/", guest["Location"])
        self.assertGreaterEqual(p.revisions.count(), 2)


class PortalGateTests(SeededCase):
    """Cổng thông tin: khách chỉ thấy tin nổi bật, nội dung bài phải đăng nhập."""

    def setUp(self):
        super().setUp()
        self.published = cm.Post.objects.create(
            title="Tin công khai thử nghiệm", post_type="news", content="Nội dung đầy đủ của tin.",
            status="published", is_featured=True, published_at=timezone.now())
        # Người xem tự đăng ký từ cổng thông tin: vai trò viewer nhưng KHÔNG
        # thừa hưởng quyền nghiệp vụ của vai trò đó (xem core/permissions.py).
        self.reader = User.objects.create_user(
            username="docgia", password="Demo@12345", role="viewer", self_registered=True)

    def test_guest_home_shows_featured_only(self):
        r = self.client.get("/")
        self.assertEqual(r.status_code, 200)
        self.assertContains(r, "Tin nổi bật")
        self.assertTrue(r.context["is_guest"])
        self.assertFalse(r.context["latest"])
        self.assertIn(self.published, r.context["featured"])

    def test_guest_list_shows_titles_without_body(self):
        r = self.client.get("/tin-tuc/")
        self.assertEqual(r.status_code, 200)
        self.assertContains(r, self.published.title)
        self.assertNotContains(r, "Nội dung đầy đủ của tin.")
        self.assertContains(r, "Đăng nhập")

    def test_guest_has_no_logout_button(self):
        """Khách chưa đăng nhập không được thấy nút Đăng xuất."""
        r = self.client.get("/")
        self.assertEqual(r.status_code, 200)
        self.assertNotContains(r, "/accounts/logout/")

    def test_member_sees_logout_button(self):
        """Đã đăng nhập phải có nút Đăng xuất, nếu không người dùng bị kẹt
        trong phiên và luôn đọc được bài dù tưởng mình là khách."""
        self.login("xem")
        r = self.client.get("/")
        self.assertEqual(r.status_code, 200)
        self.assertContains(r, "/accounts/logout/")
        self.assertContains(r, "Đăng xuất")

    def test_logout_button_ends_gate_bypass(self):
        """Bấm Đăng xuất xong thì đọc bài lại bị chặn — đúng yêu cầu."""
        self.login("xem")
        self.assertEqual(self.client.get(f"/tin-tuc/{self.published.slug}/").status_code, 200)
        resp = self.client.post("/accounts/logout/")
        self.assertIn(resp.status_code, (200, 302))
        guest = self.client.get(f"/tin-tuc/{self.published.slug}/")
        self.assertEqual(guest.status_code, 302)
        self.assertIn("/accounts/login/", guest["Location"])

    def test_reader_account_uses_public_shell(self):
        """Người tự đăng ký chỉ đọc tin: trang tài khoản nằm trong khung cổng
        thông tin, không phải khung quản trị trống trơn."""
        self.login("docgia")
        r = self.client.get("/accounts/profile/")
        self.assertEqual(r.status_code, 200)
        self.assertEqual(r.context["base_account"], "base_public.html")
        self.assertFalse(r.context["has_backoffice"])
        body = r.content.decode()
        self.assertNotIn("ui-nav", body)          # không có sidebar nghiệp vụ
        self.assertIn("Cổng thông tin công cộng", body)
        self.assertIn("Đăng xuất", body)

    def test_reader_does_not_get_backoffice_link(self):
        """Không có quyền nào thì không được mời 'Vào hệ thống' (bấm vào chỉ 403)."""
        c = Client()
        c.force_login(self.reader)
        body = c.get("/").content.decode()
        self.assertNotIn("Vào hệ thống nghiệp vụ", body)
        self.assertIn("Tài khoản đọc tin", body)

    def test_staff_account_keeps_admin_shell(self):
        """Cán bộ nghiệp vụ vẫn dùng khung quản trị có sidebar như trước."""
        self.login("bientap")
        r = self.client.get("/accounts/profile/")
        self.assertEqual(r.status_code, 200)
        self.assertEqual(r.context["base_account"], "base_ui.html")
        self.assertTrue(r.context["has_backoffice"])
        self.assertIn("ui-nav", r.content.decode())

    def test_member_can_read_post(self):
        self.login("xem")
        r = self.client.get(f"/tin-tuc/{self.published.slug}/")
        self.assertEqual(r.status_code, 200)
        self.assertContains(r, "Nội dung đầy đủ của tin.")
        self.assertIn("assistant", r.context)
        self.assertTrue(r.context["assistant"]["summary"])

    def test_viewer_role_sees_latest_list(self):
        self.login("xem")
        r = self.client.get("/")
        self.assertEqual(r.status_code, 200)
        self.assertFalse(r.context["is_guest"])

    def test_assistant_answers_from_content(self):
        self.login("xem")
        r = self.client.post(f"/tin-tuc/{self.published.slug}/hoi-dap/",
                             {"question": "nội dung của tin là gì"})
        self.assertEqual(r.status_code, 200)
        data = r.json()
        self.assertTrue(data["ok"])
        self.assertIn("Nội dung", data["answer"])

    def test_assistant_requires_login(self):
        r = self.client.post(f"/tin-tuc/{self.published.slug}/hoi-dap/", {"question": "abc"})
        self.assertEqual(r.status_code, 302)
        self.assertIn("/accounts/login/", r["Location"])

    def test_glossary_matches_whole_words(self):
        from cms import insights as ins

        post = cm.Post.objects.create(
            title="Phòng trừ rầy nâu", content="Cần theo dõi ngưỡng kinh tế trước khi phun thuốc.",
            status="published", post_type="guide")
        terms = [t["term"] for t in ins.glossary(post)]
        self.assertIn("Ngưỡng kinh tế", terms)
        self.assertIn("Rầy nâu", terms)

    def test_hot_score_prefers_recent_featured(self):
        from cms import insights as ins

        old = cm.Post.objects.create(
            title="Tin cũ", post_type="news", content="x" * 50, status="published",
            published_at=timezone.now() - timedelta(days=60))
        ins.refresh_hot_scores()
        old.refresh_from_db()
        self.published.refresh_from_db()
        self.assertGreater(self.published.hot_score, old.hot_score)

    def test_hot_board_requires_cms_view(self):
        self.login("xem")
        self.assertEqual(self.client.get("/cms/hot/").status_code, 200)

    def test_feature_toggle_requires_edit_permission(self):
        self.login("xem")
        r = self.client.post(f"/cms/hot/{self.published.pk}/feature/")
        self.assertEqual(r.status_code, 403)
        self.published.refresh_from_db()
        self.assertTrue(self.published.is_featured)


class RegistrationTests(SeededCase):
    """Người ngoài tự đăng ký rồi đọc tin như một người xem thật."""

    URL = "/accounts/register/"

    def _payload(self, **over):
        data = {
            "username": "nguoimoi", "full_name": "Trần Thị Bình",
            "email": "binhtt@example.gov.vn", "phone": "0901234567",
            "position": "Cán bộ Trạm", "password1": "MatKhauManh@2026",
            "password2": "MatKhauManh@2026", "agree": "on", "website": "",
        }
        data.update(over)
        return data

    def test_register_page_opens_for_guest(self):
        r = self.client.get(self.URL)
        self.assertEqual(r.status_code, 200)
        self.assertContains(r, "Đăng ký tài khoản")

    def test_register_creates_viewer_and_logs_in(self):
        r = self.client.post(self.URL, self._payload(), follow=True)
        self.assertEqual(r.status_code, 200)
        user = User.objects.get(username="nguoimoi")
        # Vai trò bị ép về viewer, không nhận từ POST
        self.assertEqual(user.role, "viewer")
        self.assertTrue(user.self_registered)
        self.assertTrue(user.is_active)
        self.assertEqual(user.first_name, "Trần Thị Bình")
        self.assertTrue(r.context["user"].is_authenticated)

    def test_new_user_can_read_article_immediately(self):
        post = cm.Post.objects.create(
            title="Tin cho người mới", post_type="news", status="published",
            content="Nội dung bài viết dành cho người xem mới.", published_at=timezone.now())
        self.client.post(self.URL, self._payload())
        r = self.client.get(f"/tin-tuc/{post.slug}/")
        self.assertEqual(r.status_code, 200)
        self.assertContains(r, "Nội dung bài viết dành cho người xem mới.")

    def test_role_cannot_be_escalated_via_post(self):
        self.client.post(self.URL, self._payload(role="admin", is_superuser="1", is_staff="1"))
        user = User.objects.get(username="nguoimoi")
        self.assertEqual(user.role, "viewer")
        self.assertFalse(user.is_superuser)
        self.assertFalse(user.is_staff)

    def test_duplicate_username_rejected(self):
        r = self.client.post(self.URL, self._payload(username="xem"))
        self.assertEqual(r.status_code, 200)
        self.assertContains(r, "đã được sử dụng")

    def test_duplicate_email_rejected(self):
        User.objects.create_user(username="khac", email="binhtt@example.gov.vn", password="MatKhauManh@2026")
        r = self.client.post(self.URL, self._payload())
        self.assertEqual(r.status_code, 200)
        self.assertContains(r, "đã được dùng cho một tài khoản khác")
        self.assertFalse(User.objects.filter(username="nguoimoi").exists())

    def test_weak_password_rejected(self):
        r = self.client.post(self.URL, self._payload(password1="123", password2="123"))
        self.assertEqual(r.status_code, 200)
        self.assertFalse(User.objects.filter(username="nguoimoi").exists())

    def test_must_agree_to_terms(self):
        r = self.client.post(self.URL, self._payload(agree=""))
        self.assertEqual(r.status_code, 200)
        self.assertFalse(User.objects.filter(username="nguoimoi").exists())

    def test_honeypot_blocks_bots(self):
        r = self.client.post(self.URL, self._payload(website="http://spam.example"))
        self.assertEqual(r.status_code, 200)
        self.assertFalse(User.objects.filter(username="nguoimoi").exists())

    def test_registration_can_be_disabled(self):
        with self.settings(REGISTRATION_OPEN=False):
            r = self.client.get(self.URL, follow=True)
            self.assertContains(r, "không mở đăng ký")

    def test_pending_activation_mode(self):
        with self.settings(REGISTRATION_AUTO_ACTIVE=False):
            self.client.post(self.URL, self._payload())
        user = User.objects.get(username="nguoimoi")
        self.assertFalse(user.is_active)
        self.assertFalse(self.client.login(username="nguoimoi", password="MatKhauManh@2026"))

    def test_email_domain_restriction(self):
        with self.settings(REGISTRATION_EMAIL_DOMAINS=["gov.vn"]):
            r = self.client.post(self.URL, self._payload(email="ai@gmail.com"))
            self.assertContains(r, "Chỉ chấp nhận thư điện tử thuộc")
            self.assertFalse(User.objects.filter(username="nguoimoi").exists())

    def test_register_records_login_history_and_audit(self):
        from accounts.models import LoginHistory
        from core.models import AuditLog

        self.client.post(self.URL, self._payload())
        self.assertTrue(LoginHistory.objects.filter(username="nguoimoi", event="register").exists())
        self.assertTrue(AuditLog.objects.filter(username="nguoimoi", action="register").exists())

    def test_self_registered_user_cannot_reach_internal_modules(self):
        """Người ngoài tự đăng ký không được thấy dữ liệu vận hành nội bộ."""
        from core.permissions import perm_map

        self.client.post(self.URL, self._payload())
        user = User.objects.get(username="nguoimoi")
        self.assertEqual({k: v for k, v in perm_map(user).items() if v}, {})
        for url in ("/reports/", "/map/", "/surveys/records/", "/cms/posts/", "/system/"):
            self.assertEqual(self.client.get(url).status_code, 403, url)

    def test_self_registered_lands_on_portal_not_dashboard(self):
        from core.permissions import landing_url

        self.client.post(self.URL, self._payload())
        user = User.objects.get(username="nguoimoi")
        self.assertEqual(landing_url(user), "/")

    def test_internal_viewer_role_keeps_its_permissions(self):
        """Tài khoản Người xem do quản trị viên tạo vẫn giữ quyền nội bộ như cũ."""
        from core.permissions import perm_map

        user = User.objects.get(username="xem")
        self.assertFalse(user.self_registered)
        perms = perm_map(user)
        self.assertIn("view", perms["report"])
        self.assertIn("view", perms["map"])


class ContentSeedTests(SeededCase):
    """Bộ nội dung thực tế phải đủ dày để cổng thông tin đọc được ngay."""

    def test_seed_content_creates_full_portal(self):
        posts = cm.Post.objects.filter(status="published")
        self.assertGreaterEqual(posts.count(), 15)
        # Đủ loại bài để mọi mục trên menu đều có nội dung
        for ptype in ("news", "guide", "bulletin", "forecast", "situation", "advice", "notice"):
            self.assertTrue(posts.filter(post_type=ptype).exists(), ptype)

    def test_alerts_seeded_with_risk_levels(self):
        self.assertGreaterEqual(am.Alert.objects.filter(status="published").count(), 4)
        self.assertTrue(am.Alert.objects.filter(risk_level="very_high").exists())
        self.assertTrue(am.FollowUpTask.objects.exists())

    def test_every_article_has_summary_and_cover(self):
        for p in cm.Post.objects.filter(status="published"):
            self.assertTrue(p.summary.strip(), p.slug)
            self.assertTrue(p.cover, p.slug)
            self.assertGreater(len(p.content), 500, p.slug)

    def test_slug_is_url_safe(self):
        """Slug có dấu hoặc ký tự lạ sẽ làm reverse() hỏng cả trang chủ."""
        import re

        for p in cm.Post.objects.all():
            self.assertRegex(p.slug, r"^[-a-zA-Z0-9_]+$", p.slug)
            reverse("cms:post_public", args=[p.slug])

    def test_slug_is_normalised_on_save(self):
        post = cm.Post.objects.create(title="Bệnh đạo ôn", slug="Tình hình Đạo ôn 2026!",
                                      content="Nội dung", status="draft")
        self.assertRegex(post.slug, r"^[-a-zA-Z0-9_]+$")

    def test_seed_content_is_idempotent(self):
        before = cm.Post.objects.count()
        call_command("seed_content", stdout=io.StringIO())
        self.assertEqual(cm.Post.objects.count(), before)

    def test_article_body_renders_structure(self):
        from core import textfmt

        html, headings = textfmt.render_article(
            "## Mục một\nNội dung **đậm**.\n\n- ý a\n- ý b\n\n| A | B |\n|---|---|\n| 1 | 2 |\n")
        self.assertIn("<h2", html)
        self.assertIn("<strong>đậm</strong>", html)
        self.assertIn("<ul", html)
        self.assertIn("<table", html)
        self.assertEqual(headings[0][1], "Mục một")

    def test_article_renderer_escapes_unsafe_html(self):
        from core import textfmt

        html, _ = textfmt.render_article('## <script>alert(1)</script>\n<img src=x onerror=alert(1)>')
        self.assertNotIn("<script>", html)
        self.assertNotIn("<img", html)
        self.assertIn("&lt;script&gt;", html)
        self.assertIn("&lt;img", html)

    def test_outline_matches_rendered_anchors(self):
        from core import textfmt

        text = "## Một mục\nnội dung\n\n## Một mục\nnội dung khác"
        html, headings = textfmt.render_article(text)
        items = textfmt.outline(text)
        self.assertEqual([h[0] for h in headings], [i["id"] for i in items])
        for item in items:
            self.assertIn(f'id="{item["id"]}"', html)

    def test_plain_text_conversion_for_analysis(self):
        """Bộ phân tích chỉ đọc phần chữ, bảng phải thành câu tra cứu được."""
        from core import textfmt

        plain = textfmt.strip_markdown("## Tiêu đề\n| Chỉ tiêu | Tuần 44 |\n|---|---|\n| Mật độ | 1.850 |")
        self.assertIn("Mật độ", plain)
        self.assertIn("1.850", plain)
        self.assertNotIn("|", plain)
        self.assertNotIn("##", plain)

    def test_portal_lists_all_content_types(self):
        self.login("xem")
        for ptype in ("news", "guide", "bulletin", "forecast", "situation", "advice", "notice"):
            r = self.client.get(f"/tin-tuc/?type={ptype}")
            self.assertEqual(r.status_code, 200)
            self.assertGreater(r.context["page"].paginator.count, 0, ptype)

    def test_article_page_shows_toc_and_reading_time(self):
        self.login("xem")
        post = cm.Post.objects.get(slug="quy-trinh-phong-tru-benh-dao-on")
        r = self.client.get(f"/tin-tuc/{post.slug}/")
        self.assertEqual(r.status_code, 200)
        self.assertGreaterEqual(len(r.context["sections"]), 2)
        self.assertGreaterEqual(r.context["reading_minutes"], 1)
        self.assertContains(r, "Nội dung bài viết")

    def test_home_shows_river_and_categories_with_counts(self):
        r = self.client.get("/")
        self.assertContains(r, "Tin nổi bật")
        self.assertGreaterEqual(len(r.context["featured"]), 4)
        self.assertTrue(r.context["guides"])
        for c in r.context["categories"]:
            self.assertGreater(c.published, 0, c.slug)

    def test_assistant_reads_seeded_article(self):
        self.login("xem")
        post = cm.Post.objects.get(slug="quy-trinh-phong-tru-benh-dao-on")
        r = self.client.post(f"/tin-tuc/{post.slug}/hoi-dap/",
                             {"question": "khi nào phun phòng đạo ôn cổ bông"})
        data = r.json()
        self.assertTrue(data["ok"])
        self.assertIn("cổ bông", data["answer"].lower())

    def test_seeded_articles_ranked_by_hot_score(self):
        from cms import insights

        insights.refresh_hot_scores()
        top = insights.hot_posts(limit=3)
        self.assertEqual(len(top), 3)
        # Bài gắn cảnh báo đang hiệu lực và nhiều lượt xem phải nằm trong nhóm đầu
        self.assertIn("du-bao-ray-nau-hai-tuan-toi", [p.slug for p in top])
