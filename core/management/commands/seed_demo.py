"""Tạo dữ liệu mẫu để chạy thử hệ thống: python manage.py seed_demo"""
import random
from datetime import date, timedelta

from django.core.management import call_command
from django.core.management.base import BaseCommand
from django.db import transaction
from django.utils import timezone

from accounts.models import AdminDivision, RolePermission, Unit, User
from catalog import models as cat
from core.permissions import ACTIONS, MODULES

DEMO_PASSWORD = "Demo@12345"

ROLE_PERMS = {
    "admin": {m: list(ACTIONS) for m in MODULES},
    "leader": {m: ["view", "export"] for m in MODULES if m != "system"},
    "approver": {"cms": ["view", "confirm", "approve"], "catalog": ["view"], "plans": ["view", "approve"],
                 "records": ["view", "confirm"], "data": ["view", "export"], "map": ["view", "export"],
                 "forecast": ["view", "confirm", "approve"], "alert": ["view", "approve"],
                 "report": ["view", "export"]},
    "expert": {"cms": ["view", "create", "edit", "confirm"], "catalog": ["view", "create", "edit"],
               "plans": ["view", "create", "edit"], "records": ["view", "create", "edit", "confirm"],
               "data": ["view", "create", "export"], "map": ["view", "create", "export"],
               "forecast": ["view", "create", "edit", "confirm"], "alert": ["view", "create", "edit"],
               "report": ["view", "export"]},
    "editor": {"cms": ["view", "create", "edit", "export"], "catalog": ["view"], "report": ["view"]},
    "surveyor": {"cms": ["view"], "catalog": ["view"], "plans": ["view"],
                 "records": ["view", "create", "edit"], "map": ["view"]},
    "viewer": {"cms": ["view"], "catalog": ["view"], "map": ["view"], "report": ["view"]},
}


class Command(BaseCommand):
    help = "Tạo dữ liệu mẫu (danh mục, người dùng, kế hoạch, phiếu điều tra, tiêu chí, bản tin...)."

    @transaction.atomic
    def handle(self, *args, **opts):
        random.seed(42)
        self.perms()
        self.geo()
        self.catalogs()
        self.users()
        self.surveys()
        self.forecasting()
        self.content()
        self.reports_and_system()
        # Ghép nội dung thực tế: bài viết chuyên ngành, cảnh báo, ảnh đại diện.
        # Chạy sau cùng để có sẵn danh mục, người dùng và bản tin cảnh báo.
        call_command("seed_content", verbosity=0)
        self.stdout.write(self.style.SUCCESS("Xong. Tài khoản mẫu: admin, lanhdao, pheduyet, chuyenmon, bientap, dieutra1, dieutra2, xem. Mật khẩu chung: %s" % DEMO_PASSWORD))

    # ---------- phân quyền
    def perms(self):
        for role, mods in ROLE_PERMS.items():
            for module, actions in mods.items():
                RolePermission.objects.update_or_create(role=role, module=module, defaults={"actions": actions})

    # ---------- địa bàn, đơn vị
    def geo(self):
        self.prov, _ = AdminDivision.objects.get_or_create(code="T01", defaults={"name": "Tỉnh Mẫu", "level": 1})
        self.districts, self.communes = [], []
        for i, dn in enumerate(["Huyện A", "Huyện B"], 1):
            d, _ = AdminDivision.objects.get_or_create(code=f"H0{i}", defaults={"name": dn, "level": 2, "parent": self.prov})
            self.districts.append(d)
            for j in (1, 2):
                c, _ = AdminDivision.objects.get_or_create(
                    code=f"X0{i}{j}", defaults={"name": f"Xã {dn[-1]}{j}", "level": 3, "parent": d})
                self.communes.append(c)
        self.unit_prov, _ = Unit.objects.get_or_create(code="CCBVTV", defaults={"name": "Chi cục Trồng trọt và BVTV", "division": self.prov})
        self.units = []
        for i, d in enumerate(self.districts, 1):
            u, _ = Unit.objects.get_or_create(code=f"TT0{i}", defaults={"name": f"Trạm Trồng trọt và BVTV {d.name}", "division": d, "parent": self.unit_prov})
            self.units.append(u)

    # ---------- danh mục chuyên môn
    def catalogs(self):
        g = lambda model, code, **kw: model.objects.get_or_create(code=code, defaults=kw)[0]
        self.lua = g(cat.Crop, "LUA", name="Lúa", scientific_name="Oryza sativa")
        self.ngo = g(cat.Crop, "NGO", name="Ngô", scientific_name="Zea mays")
        self.rau = g(cat.Crop, "RAU", name="Rau màu")
        self.rayna = g(cat.PestSpecies, "RNN", name="Rầy nâu", scientific_name="Nilaparvata lugens", pest_type="insect",
                       control_guidance="Điều tra thường xuyên, hạn chế bón thừa đạm, phun thuốc khi mật độ vượt ngưỡng.")
        self.daoon = g(cat.PestSpecies, "DAO", name="Bệnh đạo ôn", scientific_name="Pyricularia oryzae", pest_type="disease",
                       control_guidance="Không bón thừa đạm, phun phòng khi thời tiết âm u, độ ẩm cao.")
        self.sau = g(cat.PestSpecies, "SAU", name="Sâu keo mùa thu", scientific_name="Spodoptera frugiperda", pest_type="insect")
        self.rayna.crops.add(self.lua)
        self.daoon.crops.add(self.lua)
        self.sau.crops.add(self.ngo)
        self.st_de = g(cat.GrowthStage, "LUA-DN", name="Đẻ nhánh", crop=self.lua)
        self.st_dong = g(cat.GrowthStage, "LUA-DL", name="Làm đòng", crop=self.lua)
        self.st_nm = g(cat.GrowthStage, "NGO-9L", name="9-12 lá", crop=self.ngo)
        self.m_con_m2 = g(cat.MeasureUnit, "CON_M2", name="Con trên mét vuông", symbol="con/m²")
        self.m_pct = g(cat.MeasureUnit, "PCT", name="Phần trăm", symbol="%")
        self.m_ha = g(cat.MeasureUnit, "HA", name="Héc-ta", symbol="ha")
        self.method = g(cat.SurveyMethod, "KHAYDAP", name="Khay đập (5 điểm chéo góc)")
        self.method2 = g(cat.SurveyMethod, "QUANSAT", name="Quan sát trực quan")
        self.ind_dens = g(cat.SurveyIndicator, "MATDO", name="Mật độ", data_type="number", unit=self.m_con_m2, min_value=0)
        self.ind_rate = g(cat.SurveyIndicator, "TLHAI", name="Tỷ lệ hại", data_type="number", unit=self.m_pct, min_value=0, max_value=100)
        today = timezone.localdate()
        self.season = g(cat.Season, f"VU-{today.year}", name=f"Vụ {today.year}",
                        start_date=date(today.year, 1, 1), end_date=date(today.year, 12, 31))
        self.levels = [
            g(cat.DamageLevel, "L0", name="Không hại", rank=0, min_rate=0, max_rate=0),
            g(cat.DamageLevel, "L1", name="Nhẹ", rank=1, min_rate=0.01, max_rate=10),
            g(cat.DamageLevel, "L2", name="Trung bình", rank=2, min_rate=10.01, max_rate=30),
            g(cat.DamageLevel, "L3", name="Nặng", rank=3, min_rate=30.01, max_rate=50),
            g(cat.DamageLevel, "L4", name="Rất nặng", rank=4, min_rate=50.01, max_rate=100),
        ]

    def level_for(self, rate):
        if rate <= 0:
            return self.levels[0]
        for lv in self.levels[1:]:
            if rate <= lv.max_rate:
                return lv
        return self.levels[-1]

    # ---------- người dùng
    def users(self):
        spec = [("admin", "admin", "Quản trị hệ thống", None, None), ("lanhdao", "leader", "Nguyễn Lãnh Đạo", self.unit_prov, None),
                ("pheduyet", "approver", "Trần Phê Duyệt", self.unit_prov, None), ("chuyenmon", "expert", "Lê Chuyên Môn", self.unit_prov, None),
                ("bientap", "editor", "Phạm Biên Tập", self.unit_prov, None),
                ("dieutra1", "surveyor", "Hoàng Điều Tra 1", self.units[0], self.districts[0]),
                ("dieutra2", "surveyor", "Vũ Điều Tra 2", self.units[1], self.districts[1]),
                ("xem", "viewer", "Người Xem", None, None)]
        self.u = {}
        for username, role, name, unit, div in spec:
            user, created = User.objects.get_or_create(username=username, defaults={
                "role": role, "unit": unit, "division": div, "first_name": name, "email": f"{username}@example.local"})
            if created:
                user.set_password(DEMO_PASSWORD)
            if username == "admin":
                user.is_staff = user.is_superuser = True
            user.save()
            self.u[username] = user

    # ---------- kế hoạch, điểm, phiếu
    def surveys(self):
        from surveys import models as s

        tpl, created = s.FormTemplate.objects.get_or_create(code="BM-RAYNAU", defaults={
            "name": "Biểu mẫu điều tra rầy nâu trên lúa", "crop": self.lua, "pest": self.rayna, "method": self.method})
        if created:
            for i, (k, lbl, ft, req, lo, hi, ch) in enumerate([
                ("so_diem", "Số điểm khay đập", "number", True, 1, 20, ""),
                ("rayna_truong_thanh", "Số rầy trưởng thành", "number", False, 0, None, ""),
                ("tinh_trang_nuoc", "Tình trạng nước ruộng", "choice", False, None, None, "Khô\nÂm\nCó nước"),
            ]):
                s.FormField.objects.create(template=tpl, key=k, label=lbl, field_type=ft, required=req,
                                           min_value=lo, max_value=hi, choices=ch, order=i)
        today = timezone.localdate()
        plan, _ = s.SurveyPlan.objects.get_or_create(code="KH-001", defaults={
            "name": "Điều tra định kỳ rầy nâu trên lúa", "plan_type": "periodic", "season": self.season, "crop": self.lua,
            "method": self.method, "form_template": tpl, "division": self.prov, "start_date": today - timedelta(days=90),
            "end_date": today + timedelta(days=30), "frequency_days": 7, "status": "running",
            "created_by": self.u["chuyenmon"], "description": "Điều tra 7 ngày/lần tại các điểm cố định."})
        plan.pests.add(self.rayna)
        if s.SurveyPoint.objects.exists():
            return
        base = [(20.45, 106.30), (20.50, 106.35), (20.40, 106.25), (20.55, 106.40)]
        self.points = []
        for i, commune in enumerate(self.communes):
            route, _ = s.SurveyRoute.objects.get_or_create(plan=plan, code=f"T{commune.code}", defaults={
                "name": f"Tuyến {commune.name}", "division": commune, "unit": self.units[i // 2]})
            for k in (1, 2):
                lat, lng = base[i % 4][0] + k * 0.01, base[i % 4][1] + k * 0.012 + (i // 4) * 0.05
                self.points.append(s.SurveyPoint.objects.create(
                    code=f"D{i + 1}{k}", name=f"Điểm {commune.name} - {k}", route=route, division=commune, crop=self.lua,
                    latitude=lat, longitude=lng, area_ha=round(random.uniform(1.5, 6), 1)))
        # nhiệm vụ và phiếu lịch sử 12 tuần
        for p_idx, pt in enumerate(self.points):
            surveyor = self.u["dieutra1"] if p_idx < 4 else self.u["dieutra2"]
            unit = self.units[0] if p_idx < 4 else self.units[1]
            for w in range(12, -1, -1):
                d = today - timedelta(days=w * 7)
                rate = max(0, round(random.uniform(2, 12) + (12 - w) * (1.8 if p_idx % 3 == 0 else 0.5), 1))
                rate = min(rate, 95)
                done = w > 0
                task = s.SurveyTask.objects.create(
                    plan=plan, point=pt, unit=unit, assignee=surveyor, survey_date=d, due_date=d + timedelta(days=2),
                    status="done" if done else "assigned")
                if not done:
                    continue
                surveyed = pt.area_ha or 2
                rec = s.SurveyRecord.objects.create(
                    task=task, plan=plan, point=pt, survey_date=timezone.now() - timedelta(days=w * 7), unit=unit,
                    surveyor=surveyor, crop=self.lua, season=self.season, stage=self.st_de if w > 6 else self.st_dong,
                    pest=self.rayna, method=self.method, density=round(rate * 40, 0), damage_rate=rate,
                    prevalence="Phổ biến" if rate > 20 else "Rải rác", damage_level=self.level_for(rate),
                    surveyed_area=surveyed, affected_area=round(surveyed * rate / 100, 2), comment=f"Điều tra tuần {13 - w}.",
                    data={"so_diem": 5, "rayna_truong_thanh": int(rate * 3), "tinh_trang_nuoc": "Có nước"},
                    status="confirmed", confirmed_by=self.u["chuyenmon"], confirmed_at=timezone.now(), source="web")
                s.RecordHistory.objects.create(record=rec, action="seed", from_status="", to_status="confirmed",
                                               note="Dữ liệu mẫu", user=self.u["chuyenmon"])

    # ---------- tiêu chí, thời tiết, dự báo
    def forecasting(self):
        from forecasts import models as f

        th, _ = f.Threshold.objects.get_or_create(name="Ngưỡng rầy nâu trên lúa", pest=self.rayna, defaults={
            "crop": self.lua, "metric": "damage_rate", "medium_from": 10, "high_from": 30, "very_high_from": 50,
            "temp_min": 25, "temp_max": 30, "humidity_min": 80, "basis": "Dữ liệu minh họa, cần thay bằng quy trình kỹ thuật được phê duyệt",
            "approved_by": "Chi cục Trồng trọt và BVTV (mẫu)", "weather_condition": "Ẩm độ cao, nhiệt độ 25-30°C"})
        if not f.WeatherData.objects.exists():
            today = timezone.localdate()
            for div in self.districts:
                for d in range(30):
                    f.WeatherData.objects.create(division=div, date=today - timedelta(days=d),
                                                 temp_avg=round(random.uniform(24, 31), 1), humidity=round(random.uniform(70, 92), 0),
                                                 rainfall=round(random.uniform(0, 20), 1), source="manual", source_note="Dữ liệu mẫu")
        if not f.Forecast.objects.exists():
            today = timezone.localdate()
            f.Forecast.objects.create(
                title="Dự báo rầy nâu 2 tuần tới", pest=self.rayna, crop=self.lua, division=self.prov, stage=self.st_dong,
                valid_from=today, valid_to=today + timedelta(days=14), risk_level="high", expected_rate=28,
                basis="Xu hướng tăng 4 tuần liên tiếp theo dữ liệu điều tra; thời tiết ẩm.", recommendation="Tăng cường điều tra, chuẩn bị phòng trừ.",
                threshold=th, origin="manual", status="confirmed", created_by=self.u["chuyenmon"],
                confirmed_by=self.u["pheduyet"], confirmed_at=timezone.now())

    # ---------- chuyên mục nội dung
    def content(self):
        """Chỉ chuẩn bị chuyên mục; bài viết và bản tin do lệnh seed_content tạo."""
        from cms import models as c

        for slug, name, order in [("tin-tuc", "Tin tức", 0), ("ban-tin", "Bản tin chuyên ngành", 1),
                                   ("huong-dan", "Hướng dẫn kỹ thuật", 4), ("thong-bao", "Thông báo", 6)]:
            c.Category.objects.get_or_create(slug=slug, defaults={"name": name, "order": order})

    # ---------- báo cáo, cấu hình
    def reports_and_system(self):
        from mapview.models import ExternalLayer
        from reports.models import ReportSchedule, ReportTemplate
        from sysadmin.models import SystemConfig

        tpls = {}
        for code, name, kind in [("BC-TIENDO", "Báo cáo tiến độ điều tra", "progress"),
                                 ("BC-PHATSINH", "Báo cáo tình hình phát sinh, mức độ gây hại", "occurrence"),
                                 ("BC-DIENTICH", "Báo cáo diện tích bị ảnh hưởng", "area")]:
            tpls[code] = ReportTemplate.objects.get_or_create(code=code, defaults={
                "name": name, "kind": kind, "approved_by": "Chi cục Trồng trọt và BVTV (mẫu)"})[0]
        if not ReportSchedule.objects.exists():
            sc = ReportSchedule.objects.create(name="Báo cáo tuần gửi lãnh đạo", template=tpls["BC-PHATSINH"],
                                               frequency="weekly", fmt="xlsx", lookback_days=7)
            sc.recipients.add(self.u["lanhdao"])
        ExternalLayer.objects.get_or_create(name="OpenTopoMap (mẫu)", defaults={
            "kind": "xyz", "url": "https://tile.opentopomap.org/{z}/{x}/{y}.png", "attribution": "OpenTopoMap",
            "is_base": True, "is_active": False})
        for k, v, d in [("site_name", "Hệ thống quản lý điều tra sinh vật gây hại", "Tên hiển thị"),
                        ("alert_default_valid_days", "14", "Số ngày hiệu lực mặc định của bản tin"),
                        ("record_duplicate_check", "1", "Bật cảnh báo trùng lặp phiếu")]:
            SystemConfig.objects.get_or_create(key=k, defaults={"value": v, "description": d})
