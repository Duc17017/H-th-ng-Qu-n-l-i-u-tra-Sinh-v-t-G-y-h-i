# 🌾 Hệ thống Quản lý Điều tra Sinh vật Gây hại - AgriGov TT&BVTV

**Phiên bản**: v4.2.0-SEC  
**Framework**: Django 5.2 + PostgreSQL 16  
**UI Design System**: Tailwind CSS 3 + Material Design 3  
**Ngày cập nhật**: 01/11/2026

---

## 📋 **TỔNG QUAN DỰ ÁN**

Hệ thống quản lý tổng hợp điều tra, giám sát sinh vật gây hại trên cây trồng theo quy chuẩn kỹ thuật quốc gia (QCVN), hỗ trợ:
- 🗺️ Bản đồ GIS thời gian thực với Leaflet
- 📱 Điều tra điện tử QCVN, nhập liệu ngoài tuyến
- 📊 Dự báo bằng hồi quy tuyến tính & phân tích xu hướng dịch hại
- ⚠️ Cảnh báo qua trang thông tin, thông báo nội bộ và email
- 🔐 RBAC phân quyền chi tiết + Audit trail
- 🏛️ Quản trị hệ thống & Danh mục chuyên môn

> **Lưu ý về phạm vi:** hệ thống **chưa có** gửi SMS, chưa có nhận diện qua video (KYC)
> và chưa dùng học máy/trí tuệ nhân tạo. Dự báo dựa trên hồi quy tuyến tính trên số liệu
> điều tra thực tế, kết quả luôn cần chuyên môn xác nhận trước khi phát hành cảnh báo.

---

## 🏗️ **CẤU TRÚC DỰ ÁN**

```
gonstack 2/
├── accounts/          # Người dùng, vai trò, đơn vị, địa bàn
├── alerts/            # Cảnh báo dịch hại
├── catalog/           # Danh mục cây trồng, sinh vật, MSVT
├── cms/               # Cổng thông tin công cộng
├── core/              # Permissions, context processors, templatetags
├── forecasts/         # Dự báo & phân tích
├── mapview/           # GIS với Leaflet
├── reports/           # Báo cáo tổng hợp
├── surveys/           # Điều tra điện tử QCVN
├── sysadmin/          # Quản trị hệ thống, backup/restore
├── templates/         
│   ├── base_ui.html   # ✅ Shell nội bộ (Tailwind MD3)
│   ├── base_public.html # ✅ Shell cổng thông tin công khai
│   ├── partials/      # ✅ Form fields, pagination, ui_field
│   ├── crud/          # ✅ List / form / detail / delete dùng chung
│   ├── sysadmin/
│   │   └── index.html # ✅ Dashboard hoàn chỉnh
│   └── surveys/
│       └── record_list.html # ✅ Danh sách điều tra
├── static/
│   └── css/
│       └── leaflet_tailwind_fix.css  # ✅ Leaflet compatibility
├── docs/
│   ├── UI-MOCKUPS-SUMMARY.md  # ✅ Spec 19 mockup
│   └── DEPLOYMENT-STATUS.md   # ✅ Tiến độ triển khai
├── manage.py
└── requirements.txt
```

---

## 🚀 **CÀI ĐẶT & CHẠY**

### **Bước 1 — Vào thư mục dự án và kích hoạt virtualenv**

```powershell
cd "e:\gonstack 2"
.venv\Scripts\Activate.ps1
```

> Nếu PowerShell chặn script, chạy `Set-ExecutionPolicy -Scope Process -ExecutionPolicy Bypass` trước.
> Không muốn activate cũng được — chỉ cần gọi trực tiếp `.venv\Scripts\python.exe`.

### **Bước 2 — Cài dependencies (chỉ lần đầu)**

```powershell
.venv\Scripts\python.exe -m pip install -r requirements.txt
```

### **Bước 3 — Cấu hình `.env`**

Sao chép `.env.example` thành `.env` rồi sửa cho khớp máy bạn:

```ini
DJANGO_SECRET_KEY=doi-chuoi-nay-khi-trien-khai
DJANGO_DEBUG=1
DJANGO_ALLOWED_HOSTS=localhost,127.0.0.1

DB_ENGINE=postgres          # đổi thành "sqlite" nếu muốn chạy nhanh, không cần cài PostgreSQL
DB_NAME=pest_survey
DB_USER=postgres
DB_PASSWORD=mat_khau_cua_ban
DB_HOST=localhost
DB_PORT=5432

# Tùy chọn — cần cho chức năng sao lưu/khôi phục và xuất PDF tiếng Việt
# PG_BIN_DIR=C:\Program Files\PostgreSQL\18\bin
# PDF_FONT_PATH=C:\Windows\Fonts\arial.ttf
```

**Chạy bằng SQLite (nhanh nhất, không cần cài PostgreSQL):**

```powershell
$env:DB_ENGINE="sqlite"
.venv\Scripts\python.exe manage.py migrate
```

**Tạo database PostgreSQL (nếu chưa có):**

```powershell
psql -U postgres -c "CREATE DATABASE pest_survey;"
```

### **Bước 4 — Migrate**

```powershell
.venv\Scripts\python.exe manage.py migrate
```

Kiểm tra không còn migration sót:

```powershell
.venv\Scripts\python.exe manage.py migrate --check
```

### **Bước 5 — Nạp dữ liệu mẫu (khuyến nghị)**

```powershell
.venv\Scripts\python.exe manage.py seed_demo
```

Tạo sẵn 8 tài khoản demo, danh mục cây trồng/SVGH, 1 kế hoạch điều tra, 8 điểm, 96 phiếu điều tra,
bài viết CMS, cảnh báo và dự báo — đủ để xem mọi màn hình có dữ liệu.

**Mật khẩu chung của tất cả tài khoản demo: `Demo@12345`**

| Tài khoản | Vai trò | Dùng để xem |
|-----------|---------|-------------|
| `admin` | Quản trị (superuser) | Toàn bộ hệ thống, `/system/` |
| `lanhdao` | Lãnh đạo | Dashboard điều hành, báo cáo |
| `pheduyet` | Phê duyệt | Duyệt kế hoạch / dự báo / cảnh báo |
| `chuyenmon` | Chuyên môn | Nhận định dự báo, phân tích |
| `bientap` | Biên tập | CMS, phát hành bản tin |
| `dieutra1` | Điều tra viên | Chỉ thấy địa bàn được phân công |
| `dieutra2` | Điều tra viên | Địa bàn khác — kiểm tra phân quyền |
| `xem` | Người xem | Kiểm tra chặn quyền (403) |

### **Bước 6 — Chạy server**

```powershell
.venv\Scripts\python.exe manage.py runserver
```

Mở trình duyệt:

| URL | Trang |
|-----|-------|
| http://localhost:8000/ | Cổng thông tin công khai (không cần đăng nhập) |
| http://localhost:8000/accounts/login/ | Đăng nhập nội bộ |
| http://localhost:8000/reports/ | Dashboard điều hành (sau khi đăng nhập) |
| http://localhost:8000/map/ | Bản đồ GIS dịch tễ |
| http://localhost:8000/surveys/records/ | Danh sách phiếu điều tra |
| http://localhost:8000/system/ | Quản trị hệ thống (chỉ admin) |

Đổi cổng nếu 8000 bị chiếm: `manage.py runserver 8010`.

---

## 🧪 **TESTING**

Luôn thêm `--noinput`, nếu không Django sẽ hỏi tương tác khi muốn xóa test database cũ
(và treo khi chạy trong terminal không tương tác):

```powershell
# Toàn bộ
.venv\Scripts\python.exe manage.py test --noinput

# Một app
.venv\Scripts\python.exe manage.py test core.tests --noinput

# Một nhóm test
.venv\Scripts\python.exe manage.py test core.tests.PageSmokeTests --noinput
```

Kiểm tra cấu hình:

```powershell
.venv\Scripts\python.exe manage.py check
```

Test chạy trên database tạm riêng, **không** đụng dữ liệu thật trong `pest_survey`.

---

## ⏰ **TÁC VỤ ĐỊNH KỲ**

Chạy báo cáo đến hạn và cập nhật bản tin cảnh báo hết hiệu lực — đặt trong Task Scheduler / cron mỗi giờ:

```powershell
.venv\Scripts\python.exe manage.py run_schedules

# Bỏ qua kiểm tra thời hạn, chạy ngay mọi lịch đang bật
.venv\Scripts\python.exe manage.py run_schedules --force
```

---

## 🎨 **DESIGN SYSTEM**

### **Tailwind Config (đã tích hợp trong base_ui.html)**
```javascript
colors: {
  primary: '#00652c',           // Green Agriculture
  primary-container: '#15803d',
  secondary: '#904d00',          // Amber Warning
  tertiary: '#b20010',           // Red Emergency
  surface: '#f8f9ff',            // Near-white base
  // ... (60+ Material Design 3 tokens)
}
```

### **Typography Scale**
- **Display**: 32px/24px (Page titles)
- **Headline**: 20px/18px/16px (Section headers)
- **Body**: 15px/14px/13px (Content)
- **Label**: 13px/12px/11px (Badges, metadata)
- **Data Tabular**: 13px mono (Codes, coordinates)

### **Components**
```html
<!-- Badge Pill -->
<span class="px-2.5 py-1 rounded-full bg-primary-container text-on-primary font-label-md font-semibold">
  Active
</span>

<!-- Card -->
<div class="bg-surface-container-lowest p-space-xl rounded-xl shadow-sm">
  <!-- Content -->
</div>
```

---

## 📊 **MODULES & FEATURES**

Toàn bộ giao diện đã dùng Tailwind MD3 — không còn Bootstrap.

| Phân hệ | Đường dẫn | Chức năng chính |
|---------|-----------|-----------------|
| Cổng công khai (`cms`) | `/` | Tin tức, bản tin cảnh báo, hướng dẫn kỹ thuật, tra cứu |
| Toà soạn (`cms`) | `/cms/posts/` | Soạn thảo → duyệt → phát hành, lịch sử phiên bản |
| Điều hành (`reports`) | `/reports/dashboard/` | Dashboard KPI, biểu đồ xu hướng, báo cáo tổng hợp, xuất PDF/Excel |
| Bản đồ (`mapview`) | `/map/` | Leaflet GIS, chuyển lớp bản đồ, lọc theo thời gian, xuất/nhập GeoJSON |
| Kế hoạch (`surveys`) | `/surveys/plans/` | Lập kế hoạch, sinh nhiệm vụ tự động, theo dõi tiến độ |
| Nhiệm vụ (`surveys`) | `/surveys/my-tasks/` | Danh sách việc được giao, cảnh báo quá hạn |
| Phiếu điều tra (`surveys`) | `/surveys/records/` | Quy trình 4 bước: nháp → gửi → xác nhận, đính kèm ảnh GPS |
| Nhập ngoại tuyến (`surveys`) | `/surveys/offline/` | Lưu `localStorage`, tự đồng bộ khi có mạng |
| Biểu mẫu QCVN (`surveys`) | `/surveys/template-catalog/` | Danh mục biểu mẫu, cấu trúc trường, thiết kế và thêm trường |
| Rule Engine (`surveys`) | `/surveys/sandbox/` | Kiểm thử quy tắc xác thực, mô phỏng PASS/FAIL |
| Dự báo (`forecasts`) | `/forecasts/forecasts/` | Hồi quy tuyến tính, ngưỡng tự động, so sánh kỳ, đánh giá độ chính xác |
| Cảnh báo (`alerts`) | `/alerts/alerts/` | Phát hành bản tin, phân mức nguy cơ, theo dõi sau cảnh báo |
| Danh mục (`catalog`) | `/catalog/` | Cây trồng, SVGH, giai đoạn, mùa vụ, mức thiệt hại |
| Quản trị (`sysadmin`) | `/system/` | Nhật ký kiểm toán, lịch sử đăng nhập, sao lưu/khôi phục, tài liệu |
| Tài khoản (`accounts`) | `/accounts/` | Hồ sơ, đổi mật khẩu, thông báo, ma trận phân quyền RBAC |

### **Tính năng chưa có**
Để tránh hiểu nhầm khi vận hành, các mục sau **chưa được xây dựng**:
- Gửi SMS (model `Alert.CHANNELS` chỉ có `web`, `notify`, `email`)
- Nhận diện qua video / KYC
- Học máy; dự báo dùng hồi quy tuyến tính trên số liệu điều tra
- Đăng nhập một lần (SSO/LDAP) với hệ thống của Sở

### **Ghi chú kỹ thuật**
- Mọi template kế thừa `base_ui.html` (nội bộ) hoặc `base_public.html` (công khai).
- Test `test_no_legacy_bootstrap_shell` sẽ fail nếu ai đó tạo lại `base.html` kiểu cũ.
- Bộ lọc hiển thị: `state_badge`, `risk_badge`, `role_badge`, `audit_icon` trong `core/templatetags/ui.py`.

---

## 🔐 **RBAC PERMISSIONS**

### **Vai trò hiện có**
```python
ROLES = [
    ('admin', 'Quản trị viên'),
    ('leader', 'Lãnh đạo'),
    ('approver', 'Người phê duyệt'),
    ('expert', 'Chuyên gia'),
    ('editor', 'Biên tập viên'),
    ('surveyor', 'Điều tra viên'),
    ('viewer', 'Người xem'),
]
```

### **Modules & Actions**

Danh sách chuẩn trong `core/permissions.py` — dùng đúng khóa này ở cả view và template:

```python
MODULES = {
    'cms': 'Trang thông tin',
    'catalog': 'Danh mục chuyên môn',
    'plans': 'Kế hoạch điều tra',
    'records': 'Dữ liệu hiện trường',
    'data': 'Tổng hợp dữ liệu',
    'map': 'Bản đồ GIS',
    'forecast': 'Dự tính, dự báo',
    'alert': 'Cảnh báo',
    'report': 'Báo cáo, bảng điều hành',
    'system': 'Quản trị hệ thống',
}

ACTIONS = {
    'view': 'Xem',
    'create': 'Tạo mới',
    'edit': 'Chỉnh sửa',
    'confirm': 'Xác nhận',
    'approve': 'Phê duyệt',
    'export': 'Kết xuất',
}
```

> Lưu ý: module là **`records`** (không phải `surveys`) và **`report`**, **`forecast`**, **`alert`**
> ở dạng số ít. Viết sai khóa sẽ khiến menu và nút bấm không hiện dù user có quyền.

---

## 📁 **QUAN TRỌNG: FILE CẦN ĐỌC**

1. **`/docs/TRIEN-KHAI.md`**
   - Kịch bản triển khai từng bước trên Windows Server
   - Cài dịch vụ (NSSM), Task Scheduler, sao lưu tự động
   - Xử lý sự cố và danh sách nghiệm thu

2. **`/docs/UI-MOCKUPS-SUMMARY.md`**
   - Spec đầy đủ 19 mockup
   - Design tokens
   - Mapping mockup → module
   - Priority implementation

3. **`/docs/DEPLOYMENT-STATUS.md`**
   - Tiến độ hiện tại
   - Checklist còn lại
   - Hướng dẫn tiếp tục

4. **`templates/base_ui.html`**
   - Master template reference
   - Sidebar navigation
   - Header bar với alerts
   - Tailwind config

4. **`templates/sysadmin/index.html`**
   - Dashboard template hoàn chỉnh
   - Làm mẫu cho các template khác

---

## 🛠️ **KỸ THUẬT**

### **Stack**
- **Backend**: Django 5.2, Python 3.12
- **Database**: PostgreSQL 16 / SQLite
- **Frontend**: Tailwind CSS 3 (CDN), Leaflet 1.9.4, Chart.js 4
- **Icons**: Google Material Symbols Outlined
- **Fonts**: Inter (Variable weight 400-700)

### **Key Libraries**
```txt
Django==5.2.18
psycopg[binary]==3.3.6
openpyxl==3.1.5        # nhập/xuất Excel
reportlab==5.1.0       # xuất PDF tiếng Việt
Pillow==13.0.0         # xử lý ảnh đính kèm
python-dotenv==1.2.4
```

---

## 📝 **GHI CHÚ CHO DEVELOPER**

### **1. Extend Base Template**
```django
{% extends 'base_ui.html' %}
{% load ui %}

{% block title %}Trang của bạn{% endblock %}

{% block content %}
<div class="flex flex-col w-full pb-space-3xl gap-space-xl">
    <!-- Content here -->
</div>
{% endblock %}
```

### **2. Sử dụng Template Tags**
```django
{{ record|state_badge }}              {# huy hiệu theo trạng thái nghiệp vụ #}
{{ record|state_badge:"source" }}     {# huy hiệu theo thuộc tính khác #}
{{ forecast|risk_badge }}             {# mức nguy cơ low/medium/high/very_high #}
{{ user|role_badge }}                 {# vai trò RBAC #}
{{ user|initials }}                   {# chữ cái avatar #}
{{ log.action|audit_icon }}           {# tên Material icon #}
{{ log.action|audit_icon:"class" }}   {# lớp màu nền #}
{{ rec.survey_date|vn_date }}         {# dd/mm/yyyy #}
{{ 12.5|num:1 }}                      {# 12,5 #}
```

### **3. Permission Guard**

Dùng đúng khóa module trong `core/permissions.py` (`records`, `plans`, `forecast`, `alert`, `report`, `map`, `data`, `cms`, `catalog`, `system`):

```python
from core.permissions import perm_required

@perm_required("records", "create")
def record_create(request):
    ...
```

```django
{% if 'create' in perms_map.records %}
<a href="{% url 'surveys:record_create' %}">Tạo phiếu điều tra</a>
{% endif %}
```

### **4. Giữ dữ liệu theo địa bàn**

Điều tra viên chỉ thấy dữ liệu thuộc địa bàn được phân công (gồm cả địa bàn con):

```python
from core.permissions import scope_qs

qs = scope_qs(request.user, SurveyRecord.objects.all(), "point__division")
```

---

## 🚢 **TRIỂN KHAI THỰC TẾ**

### **Checklist trước khi mở cho người dùng**
- [ ] `DJANGO_DEBUG=0` trong `.env`
- [ ] Đổi `DJANGO_SECRET_KEY` sang chuỗi ngẫu nhiên ≥ 50 ký tự
- [ ] Cấu hình PostgreSQL, đặt `DB_PASSWORD`
- [ ] `DJANGO_ALLOWED_HOSTS` = domain thật
- [ ] `.venv\Scripts\python.exe manage.py collectstatic --noinput` — **bắt buộc**, thiếu là mất giao diện
- [ ] Quyết định `DJANGO_SECURE_COOKIES` theo việc có HTTPS hay không (xem mục dưới)
- [ ] Chạy bằng `serve.py` (waitress), **không** dùng `runserver`
- [ ] Đặt `PG_BIN_DIR` để bật sao lưu/khôi phục bằng `pg_dump`
- [ ] Đặt `PDF_FONT_PATH` tới font Unicode (vd `C:\Windows\Fonts\arial.ttf`)
- [ ] Điền `EMAIL_HOST`/`EMAIL_USER`/`EMAIL_PASSWORD` nếu dùng cảnh báo qua email
- [ ] Lên lịch `manage.py run_schedules` mỗi giờ
- [ ] Sao lưu định kỳ `media/` và database
- [ ] Chạy `manage.py test --noinput` trên máy đích — phải xanh toàn bộ

### **Chạy bằng WSGI server**

`runserver` chỉ dành cho phát triển. Trên máy thật dùng `serve.py`:

```powershell
.venv\Scripts\python.exe manage.py collectstatic --noinput   # bắt buộc, nếu không giao diện mất style
```

```powershell
.venv\Scripts\python.exe serve.py
.venv\Scripts\python.exe serve.py --host 0.0.0.0 --port 8080 --threads 8
```

`serve.py` sẽ **cảnh báo ngay khi khởi động** nếu cấu hình sắp khiến hệ thống không dùng được
(chưa collectstatic, cookie Secure mà không có HTTPS, SECRET_KEY mặc định).

File tĩnh do WhiteNoise phục vụ; tệp tải lên (ảnh hiện trường, tệp báo cáo) do view
`core/media.py` phục vụ và **yêu cầu đăng nhập**.

### **HTTPS — đọc kỹ trước khi triển khai**

Khi `DJANGO_DEBUG=0`, mặc định cookie phiên có cờ `Secure`, tức là **chỉ gửi qua HTTPS**.
Nếu bạn chạy bằng `http://`, trình duyệt sẽ từ chối cookie và **không ai đăng nhập được**
(không có thông báo lỗi rõ ràng, chỉ thấy quay lại trang đăng nhập).

Chọn một trong hai:

| Tình huống | Cấu hình |
|---|---|
| Có HTTPS (khuyến nghị) | `DJANGO_SECURE_COOKIES=1`, và `DJANGO_BEHIND_PROXY=1` nếu chạy sau nginx/IIS |
| Mạng nội bộ không có HTTPS | `DJANGO_SECURE_COOKIES=0` — chấp nhận rủi ro bị đánh cắp phiên |

Sau khi HTTPS chạy ổn định vài tuần, bật thêm `DJANGO_SSL_REDIRECT=1` và
`DJANGO_HSTS_SECONDS=31536000`.

### **Sự cố đã gặp: database ở "recovery mode"**

Nếu thấy `FATAL: the database system is in recovery mode`, PostgreSQL đang tự khôi phục
sau khi tắt máy đột ngột. Chờ 1–2 phút rồi thử lại; không cần khởi động lại dịch vụ.
Trong lúc đó mọi trang sẽ trả lỗi 500.

### **Biến môi trường**

Tên biến phải khớp `config/settings.py` — xem `.env.example` để có danh sách đầy đủ.

```ini
DJANGO_SECRET_KEY=chuoi_ngau_nhien_manh_it_nhat_50_ky_tu
DJANGO_DEBUG=0
DJANGO_ALLOWED_HOSTS=bvtv.example.gov.vn
DJANGO_CSRF_ORIGINS=https://bvtv.example.gov.vn

DB_ENGINE=postgres
DB_NAME=pest_survey
DB_USER=postgres
DB_PASSWORD=mat_khau_manh
DB_HOST=localhost
DB_PORT=5432

LOGIN_MAX_ATTEMPTS=5
LOGIN_LOCKOUT_SECONDS=900

PG_BIN_DIR=C:\Program Files\PostgreSQL\18\bin
PDF_FONT_PATH=C:\Windows\Fonts\arial.ttf
```

> ⚠️ Khi `DJANGO_DEBUG=0`, settings tự bật `SESSION_COOKIE_SECURE` và `CSRF_COOKIE_SECURE`,
> nên **bắt buộc phải chạy qua HTTPS**, nếu không sẽ không đăng nhập được.
> Đây là nguyên nhân phổ biến nhất của lỗi "CSRF verification failed" khi thử nghiệm.

### **Tài nguyên giao diện đã tự host**

Toàn bộ CSS, JS và font nằm trong `static/` — **không cần internet**:

| Tài nguyên | Đường dẫn |
|---|---|
| Tailwind CSS đã build | `static/css/app.css` |
| Leaflet 1.9.4 | `static/vendor/leaflet/` |
| Chart.js 4.4.4 | `static/vendor/chartjs/` |
| Font Inter + Material Symbols | `static/vendor/fonts/` |

Chỉ **ảnh nền bản đồ** (OpenStreetMap) là cần internet. Nếu mạng nội bộ chặn hoàn toàn,
cần dựng tile server nội bộ và sửa URL tile trong `templates/mapview/map.html`.

Khi sửa giao diện, phải build lại CSS:

```powershell
npm install          # lần đầu
npm run build        # build một lần
npm run watch        # theo dõi khi đang sửa
```

Thiếu bước này, các class Tailwind mới thêm sẽ **không có tác dụng**.

---

## 🩺 **LỖI THƯỜNG GẶP**

### **`UnicodeEncodeError: 'charmap' codec can't encode character`**

Console Windows mặc định dùng code page cp1252, không in được tiếng Việt khi lệnh quản lý
xuất thông báo (thường gặp với `seed_demo`, `run_schedules`). Sửa bằng cách đặt encoding UTF-8:

```powershell
$env:PYTHONIOENCODING="utf-8"
.venv\Scripts\python.exe manage.py seed_demo
```

Hoặc đặt một lần cho cả phiên PowerShell:

```powershell
[Console]::OutputEncoding = [System.Text.Encoding]::UTF8
chcp 65001
```

### **`CommandError: database "pest_survey" does not exist`**

Chưa tạo database — xem Bước 3. Hoặc chuyển tạm sang SQLite:

```powershell
$env:DB_ENGINE="sqlite"
.venv\Scripts\python.exe manage.py migrate
.venv\Scripts\python.exe manage.py seed_demo
```

### **Test treo, hỏi "Type 'yes' to delete..."**

Thiếu `--noinput`. Luôn chạy:

```powershell
.venv\Scripts\python.exe manage.py test --noinput
```

### **Không đăng nhập được sau khi đặt `DJANGO_DEBUG=0`**

Settings bật cookie `Secure` khi tắt DEBUG, nên phải truy cập qua HTTPS (hoặc qua reverse proxy
có TLS). Khi thử trên máy local, giữ `DJANGO_DEBUG=1`.

### **Bản đồ trắng, không tải được ảnh nền**

Cần mạng Internet để lấy tile từ OpenStreetMap. Kiểm tra cả `SECURE_REFERRER_POLICY` trong
`config/settings.py` vẫn là `strict-origin-when-cross-origin`.

### **Trang 403 dù đã đăng nhập**

Tài khoản không có quyền trên module đó. Đăng nhập `admin` để đối chiếu, rồi vào
`/accounts/roles/` xem vai trò đang thiếu quyền gì.

---

## 📞 **HỖ TRỢ & LIÊN HỆ**

- **Technical Issues**: Xem `/docs/DEPLOYMENT-STATUS.md`
- **Design Reference**: Xem `/docs/UI-MOCKUPS-SUMMARY.md`
- **Code Examples**: Tham khảo `templates/sysadmin/index.html`

---

## 📄 **LICENSE**

Internal Government Project - Restricted Access  
© 2026 Chi cục Trồng trọt & BVTV Tỉnh Bắc Giang

---

**Chúc bạn code hiệu quả!** 🌾🚀
