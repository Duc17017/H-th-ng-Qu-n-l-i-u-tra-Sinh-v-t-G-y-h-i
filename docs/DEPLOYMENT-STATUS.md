# ✅ TÌNH TRẠNG TRIỂN KHAI ỨNG DỤNG

**Ngày cập nhật**: 04/11/2026
**Mục tiêu**: Hoàn thiện ứng dụng Django 5.2 theo 19 mockup Tailwind CSS Material Design 3

---

## ✅ **TỔNG QUAN**

Toàn bộ giao diện đã được chuyển sang hệ thiết kế **Tailwind CSS + Material Design 3**.
Không còn template nào dùng Bootstrap 5 hay shell cũ `base.html` (đã được xóa).

| Hạng mục | Trạng thái |
|----------|------------|
| Shell nội bộ (`base_ui.html`) | ✅ Hoàn thành |
| Shell công khai (`base_public.html`) | ✅ Hoàn thành |
| Template kế thừa `base.html` (legacy) | ✅ 0 file |
| Style Bootstrap (`static/css/app.css`) | ✅ Đã xóa |
| Test suite | ✅ 27/27 PASS |
| `manage.py check` | ✅ 0 issue |

---

## 🧱 **1. Hạ tầng giao diện**

- ✅ `templates/base_ui.html` — shell nội bộ: sidebar cố định `w-64`, header `h-16` `left-64`,
  MD3 color tokens, Material Symbols Outlined, alert ticker, season selector, profile dropdown, messages.
- ✅ `templates/base_public.html` — cổng thông tin công khai, không có sidebar quản trị.
- ✅ `core/templatetags/ui.py` — bộ filter dùng chung: `state_badge`, `risk_badge`, `role_badge`,
  `audit_icon`, `initials`, `pct`, `num`, `vn_date`, `qs_set`, `qs_without`, `ui_field`, `field_widget`.
- ✅ `core/permissions.py` — bản đồ quyền `perms_map` cho 10 module.
- ✅ `static/css/leaflet_tailwind_fix.css` — tương thích Leaflet ↔ Tailwind preflight.

---

## 📦 **2. Template theo phân hệ**

### CMS (cổng công khai + toà soạn)
- ✅ `cms/home.html`, `cms/post_list.html`, `cms/post_public.html`
- ✅ `cms/manage_list.html`, `cms/manage_detail.html`, `cms/post_form.html`

### Surveys (điều tra)
- ✅ `surveys/plan_list.html`, `surveys/plan_detail.html`
- ✅ `surveys/task_list.html`, `surveys/import.html`, `surveys/offline.html`
- ✅ `surveys/record_list.html`, `surveys/record_detail.html`, `surveys/record_form.html`
- ✅ `surveys/template_catalog.html`, `surveys/template_edit.html` (thiết kế biểu mẫu + thêm trường)
- ✅ `surveys/sandbox.html` (Rule Engine simulator)

### GIS / Mapview
- ✅ `mapview/map.html` — cockpit Leaflet, layer switcher, filter panel, timeline Chart.js,
  point inspector drawer, GeoJSON export/import

### Forecasts (dự báo)
- ✅ `forecasts/analysis.html`, `forecasts/forecast_list.html`, `forecasts/forecast_detail.html`
- ✅ `forecasts/compare.html`, `forecasts/suggest.html`

### Alerts (cảnh báo)
- ✅ `alerts/alert_list.html`, `alerts/alert_detail.html`
- ✅ `alerts/followup_list.html`, `alerts/followup_detail.html`, `alerts/from_forecast.html`

### Reports (báo cáo)
- ✅ `reports/dashboard.html`, `reports/summary.html`
- ✅ `reports/report_list.html`, `reports/report_view.html`

### SysAdmin
- ✅ `sysadmin/index.html`, `sysadmin/audit_log.html`, `sysadmin/login_history.html`
- ✅ `sysadmin/backups.html`, `sysadmin/documents.html`

### Accounts
- ✅ `accounts/role_matrix.html`, `accounts/profile.html`, `accounts/notifications.html`
- ✅ `accounts/password_change.html`, `registration/login.html`

### CRUD dùng chung (`core/crud.py`)
- ✅ `crud/list.html`, `crud/form.html`, `crud/detail.html`, `crud/index.html`, `crud/confirm_delete.html`
- ✅ `partials/form_fields.html`, `partials/pagination.html`, `partials/ui_field.html`

---

## 🧪 **3. Kiểm thử**

```bash
python manage.py test --noinput      # 27 tests OK
python manage.py check               # 0 issue
```

`core/tests.py` bao gồm:

- `PageSmokeTests.test_admin_pages` — mọi trang chính trả 200/302 **và** render bằng shell MD3.
- `PageSmokeTests.test_detail_pages` — trang chi tiết của từng phân hệ.
- `PageSmokeTests.test_template_edit_page_renders_fields` — trang thiết kế biểu mẫu.
- `PageSmokeTests.test_template_edit_save_redirects_with_selection` — lưu biểu mẫu và redirect kèm `template_id`.
- `PageSmokeTests.test_no_legacy_bootstrap_shell` — chặn hồi quy về `base.html`.
- `PageSmokeTests.test_public_site_no_login` / `test_login_required_for_internal`.
- `RbacTests` — ma trận phân quyền, phạm vi dữ liệu theo địa bàn cho điều tra viên.

---

## 📌 **4. Ghi chú vận hành**

- Tailwind được nạp qua CDN `cdn.tailwindcss.com` cùng `tailwind.config` khai báo token MD3 trong `base_ui.html`
  và `base_public.html`. Khi triển khai production nên build CSS tĩnh thay vì CDN.
- Biểu mẫu điều tra dùng HTML5 geolocation (`#btn-gps`), nhập liệu ngoại tuyến dùng `localStorage`
  và đồng bộ qua `surveys:sync_api` (idempotent theo `client_uuid`).
