# TIẾN ĐỘ TRIỂN KHAI

**Ngày cập nhật**: 04/11/2026
**Mục tiêu**: Ứng dụng Django 5.2 theo bộ mockup Tailwind CSS Material Design 3

---

## TỔNG QUAN

Toàn bộ giao diện đã chuyển sang **Tailwind CSS + Material Design 3**.
Không còn template nào dùng Bootstrap 5 hay shell cũ `base.html`.

| Hạng mục | Trạng thái |
|----------|------------|
| Shell nội bộ (`base_ui.html`) | Hoàn thành |
| Shell công khai (`base_public.html`) | Hoàn thành |
| Template kế thừa `base.html` (legacy) | 0 file |
| Style Bootstrap (`static/css/app.css` cũ) | Đã xoá |
| Test suite | 44/44 PASS |
| `manage.py check` | 0 issue |

---

## 1. Hệ thống giao diện

- `templates/base_ui.html` — shell nội bộ: sidebar cố định `w-64`, header `h-16` `left-64`,
  MD3 color tokens, Material Symbols Outlined, alert ticker, season selector, profile dropdown, messages.
- `templates/base_public.html` — cổng thông tin công khai, không có sidebar quản trị.
- `core/templatetags/ui.py` — bộ filter dùng chung: `state_badge`, `risk_badge`, `role_badge`,
  `audit_icon`, `initials`, `pct`, `num`, `vn_date`, `qs_set`, `qs_without`, `ui_field`, `field_widget`.
- `core/permissions.py` — bản đồ quyền `perms_map` cho 10 module; `landing_url()` chọn trang đích theo quyền.
- `static/css/leaflet_tailwind_fix.css` — tương thích Leaflet với Tailwind preflight.

### Tài nguyên tự host
Toàn bộ CSS/JS/font nằm trong `static/`, **không phụ thuộc internet**:

| Tài nguyên | Đường dẫn | Nguồn |
|---|---|---|
| Tailwind (đã build) | `static/css/app.css` | build từ `static/css/input.css` |
| Leaflet 1.9.4 | `static/vendor/leaflet/` | kèm ảnh marker |
| Chart.js 4.4.4 | `static/vendor/chartjs/` | |
| Inter + Material Symbols | `static/vendor/fonts/` | |

Cấu hình build: `tailwind.config.js`, `package.json`. Sửa giao diện phải chạy `npm run build`.

---

## 2. Template theo phân hệ

### CMS (cổng công khai + toà soạn)
- `cms/home.html`, `cms/post_list.html`, `cms/post_public.html`
- `cms/manage_list.html`, `cms/manage_detail.html`, `cms/post_form.html` — quy trình soạn → duyệt → phát hành

### Surveys (điều tra)
- `surveys/record_list.html`, `surveys/record_detail.html`, `surveys/record_form.html`
- `surveys/plan_list.html`, `surveys/plan_detail.html`
- `surveys/task_list.html`, `surveys/import.html`, `surveys/offline.html`
- `surveys/template_catalog.html`, `surveys/template_edit.html`, `surveys/sandbox.html`

### Dự báo & phân tích
- `forecasts/forecast_list.html`, `forecasts/forecast_detail.html`
- `forecasts/analysis.html`, `forecasts/compare.html`, `forecasts/suggest.html`

### Cảnh báo
- `alerts/alert_list.html`, `alerts/alert_detail.html`
- `alerts/followup_list.html`, `alerts/followup_detail.html`, `alerts/from_forecast.html`

### Báo cáo & bản đồ
- `reports/dashboard.html`, `reports/summary.html`, `reports/report_list.html`, `reports/report_view.html`
- `mapview/map.html`

### Quản trị & tài khoản
- `sysadmin/index.html`, `audit_log.html`, `login_history.html`, `backups.html`, `documents.html`
- `accounts/role_matrix.html`, `profile.html`, `notifications.html`, `password_change.html`
- `registration/login.html`

### Trang lỗi
- `403.html`, `404.html`, `500.html` — dùng chung khung MD3

---

## 3. Việc đã làm để chạy thực tế (04/11/2026)

| Việc | Chi tiết |
|---|---|
| Tự host toàn bộ tài nguyên | Bỏ 5 nguồn CDN; build Tailwind tĩnh; font và JS tải về `static/vendor/` |
| Sửa signal nhật ký đăng nhập | Closure trong `AppConfig.ready()` bị GC thu hồi → tách ra `accounts/signals.py` dùng `@receiver` |
| Sửa lỗi 403 sau đăng nhập | `landing_url()` chọn trang đích theo quyền; `home_url` trong context thay cho link cứng |
| Chống dò mật khẩu | `accounts/lockout.py`, ngưỡng qua `LOGIN_MAX_ATTEMPTS` / `LOGIN_LOCKOUT_SECONDS` |
| Ghi log | `LOGGING` ghi ra `logs/app.log` (xoay vòng 10 MB × 10) |
| Gửi email cảnh báo | `_send_email()` gửi thật, không nuốt lỗi, ghi nhật ký kiểm toán từng lần |
| WSGI server | `serve.py` dùng waitress thay `runserver` |
| Trang lỗi | 403 / 404 / 500 |
| Version control | Khởi tạo git, `.gitignore` chặn `.env`, `logs/`, `media/`, `backups/` |
| Sửa lỗi bảng mã | `templates/surveys/template_edit.html` (149 chỗ) |

---

## 4. Điểm cần lưu ý khi vận hành

- **Bắt buộc HTTPS khi `DJANGO_DEBUG=0`**, nếu không sẽ không đăng nhập được
  (cookie `Secure` bị trình duyệt từ chối qua HTTP).
- **Ảnh nền bản đồ vẫn cần internet.** Nếu mạng nội bộ chặn hoàn toàn, cần dựng tile server
  nội bộ và sửa URL trong `templates/mapview/map.html`.
- Sau khi sửa giao diện phải chạy `npm run build`, nếu không class mới không có tác dụng.
- `run_schedules` nằm ở app `reports` (`reports/management/commands/run_schedules.py`),
  đặt lịch chạy mỗi giờ.

---

## 5. Tính năng chưa có

Các mục dưới đây **chưa được xây dựng**, cần biết để không hiểu nhầm khi vận hành:

- Gửi SMS (`Alert.CHANNELS` chỉ có `web`, `notify`, `email`)
- Nhận diện qua video / KYC
- Học máy; dự báo dùng hồi quy tuyến tính trên số liệu điều tra thực tế
- Đăng nhập một lần (SSO/LDAP) với hệ thống của Sở
- Hàng đợi tác vụ nền (Celery); email gửi đồng bộ trong lúc phát hành cảnh báo
