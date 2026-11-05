# KỊCH BẢN TRIỂN KHAI

**Hệ thống**: AgriGov TT&BVTV — Quản lý điều tra sinh vật gây hại
**Máy chủ**: Windows Server (hướng dẫn này dùng Windows; phần Linux ghi ở cuối)
**Ngày soạn**: 05/11/2026

Tài liệu này để một cán bộ kỹ thuật **chưa từng làm** cũng dựng được hệ thống.
Làm tuần tự từ trên xuống, không bỏ bước.

---

## 0. Chuẩn bị trước khi bắt đầu

### Cần có

| Thứ | Ghi chú |
|---|---|
| Máy chủ Windows | Tối thiểu 2 CPU, 4 GB RAM, 20 GB trống |
| PostgreSQL 16 trở lên | Đã cài sẵn, có mật khẩu tài khoản `postgres` |
| Python 3.12 | Đã cài, nhớ tick "Add to PATH" |
| Bộ mã nguồn dự án | Thư mục chứa `manage.py` |
| Địa chỉ IP hoặc tên miền nội bộ | Ví dụ `10.1.2.30` hoặc `bvtv.local` |

### Ba câu hỏi phải trả lời trước

**Câu 1: Máy chủ có HTTPS không?**

- **Có** → dùng `DJANGO_SECURE_COOKIES=1` (cấu hình chuẩn, an toàn)
- **Không, chỉ HTTP trong mạng LAN** → dùng `DJANGO_SECURE_COOKIES=0`

Chọn sai ở đây sẽ khiến **không ai đăng nhập được**. Không có thông báo lỗi rõ ràng,
chỉ thấy bấm đăng nhập xong quay lại trang login. Nếu gặp hiện tượng đó, quay lại mục này.

**Câu 2: Có internet không?**

- **Có** → bản đồ nền hoạt động bình thường
- **Không** → bản đồ trống; xem mục 9 để dựng tile server nội bộ

**Câu 3: Có máy chủ SMTP của cơ quan không?**

- **Có** → điền ở mục 3, cảnh báo gửi được qua email
- **Không** → email chỉ in ra log; cảnh báo vẫn hiện trên trang thông tin

---

## 1. Đưa mã nguồn lên máy chủ

Chép thư mục dự án vào, ví dụ `D:\agrigov`. Mở **PowerShell với quyền Administrator**:

```powershell
cd D:\agrigov
```

Tạo môi trường ảo và cài thư viện:

```powershell
python -m venv .venv
.venv\Scripts\python.exe -m pip install --upgrade pip
.venv\Scripts\python.exe -m pip install -r requirements.txt
```

Nếu công ty chặn internet, chép thư mục `.venv` từ máy đã cài sẵn thay vì chạy lệnh trên.

---

## 2. Tạo cơ sở dữ liệu

```powershell
& "C:\Program Files\PostgreSQL\18\bin\psql.exe" -U postgres -c "CREATE DATABASE pest_survey;"
```

Nhập mật khẩu PostgreSQL khi được hỏi.

> Đường dẫn `psql.exe` có thể khác nếu bạn cài PostgreSQL bản khác. Tìm bằng:
> `Get-ChildItem "C:\Program Files\PostgreSQL" -Recurse -Filter psql.exe`

---

## 3. Tạo file cấu hình `.env`

```powershell
Copy-Item .env.example .env
notepad .env
```

Sửa các dòng sau. **Phần còn lại giữ nguyên** nếu không có lý do đổi.

```ini
# ── Bắt buộc sửa ────────────────────────────────────────────────────────────
# Sinh khoá mới bằng lệnh ở dưới, KHÔNG dùng giá trị mẫu
DJANGO_SECRET_KEY=<dán khoá vừa sinh>
DJANGO_DEBUG=0
DJANGO_ALLOWED_HOSTS=10.1.2.30,bvtv.local,localhost

DB_PASSWORD=<mật khẩu PostgreSQL của bạn>

# ── Chọn theo Câu 1 ở mục 0 ─────────────────────────────────────────────────
DJANGO_SECURE_COOKIES=0     # 0 nếu KHÔNG có HTTPS, 1 nếu có HTTPS

# ── Nếu chạy sau nginx/IIS có TLS thì thêm ───────────────────────────────────
# DJANGO_BEHIND_PROXY=1
```

Sinh `SECRET_KEY`:

```powershell
.venv\Scripts\python.exe -c "from django.core.management.utils import get_random_secret_key as g; print(g())"
```

Chép nguyên dòng vừa in vào `DJANGO_SECRET_KEY`.

### Nếu có SMTP (Câu 3)

Thêm vào cuối `.env`:

```ini
EMAIL_HOST=smtp.coquan.gov.vn
EMAIL_PORT=587
EMAIL_USER=canhbao@coquan.gov.vn
EMAIL_PASSWORD=<mật khẩu>
DEFAULT_FROM_EMAIL=canhbao@coquan.gov.vn
```

> Nếu SMTP của bạn dùng cổng 465 (SSL thay vì TLS), phải sửa `EMAIL_USE_TLS = False`
> và bật `EMAIL_USE_SSL = True` trong `config/settings.py`.

---

## 4. Khởi tạo dữ liệu

```powershell
# Bắt buộc, tránh lỗi tiếng Việt trong console Windows
[Console]::OutputEncoding = [System.Text.Encoding]::UTF8
$env:PYTHONIOENCODING = "utf-8"

.venv\Scripts\python.exe manage.py migrate
.venv\Scripts\python.exe manage.py collectstatic --noinput
```

Kiểm tra không còn migration sót:

```powershell
.venv\Scripts\python.exe manage.py migrate --check
```

Phải không in ra gì cả. Nếu có, chạy `migrate` lại.

> **`collectstatic` là bắt buộc.** Thiếu bước này, mở trang sẽ thấy chữ trơn không
> màu, không biểu tượng, không bố cục.

---

## 5. Tạo tài khoản quản trị

```powershell
.venv\Scripts\python.exe manage.py createsuperuser
```

Nhập tên đăng nhập, email, mật khẩu. Mật khẩu phải **tối thiểu 8 ký tự, không toàn số,
không trùng tên đăng nhập** — hệ thống sẽ từ chối nếu không đạt.

> **Không chạy `seed_demo`.** Lệnh đó nạp 96 phiếu điều tra giả và 8 tài khoản demo,
> chỉ dùng để trình diễn. Nếu đã lỡ chạy, phải tạo lại database sạch.

Sau khi đăng nhập, vào `/accounts/roles/` để xem ma trận phân quyền và tạo tài khoản
cho từng cán bộ.

---

## 6. Chạy thử lần đầu

```powershell
.venv\Scripts\python.exe serve.py --host 0.0.0.0 --port 8000
```

Màn hình phải hiện:

```
  AgriGov TT&BVTV — http://0.0.0.0:8000/
  DEBUG=False  threads=8  db=postgresql
  cookie Secure=False  SSL redirect=False
```

Nếu hiện khung **CẢNH BÁO**, đọc kỹ và sửa trước khi tiếp tục. Đó là các lỗi
đã biết khiến hệ thống không dùng được.

### Kiểm tra bằng trình duyệt

Mở `http://10.1.2.30:8000/` từ một máy khác trong mạng. Kiểm tra lần lượt:

- [ ] Trang chủ hiện đúng màu xanh, có biểu tượng — nếu chỉ có chữ trơn thì thiếu `collectstatic`
- [ ] Đăng nhập được bằng tài khoản vừa tạo
- [ ] Vào được `/reports/dashboard/`
- [ ] Mở `/map/` thấy bản đồ (nếu có internet)
- [ ] Tạo thử một bản ghi bất kỳ rồi xoá

Nếu **đăng nhập xong bị quay lại trang login**: sai `DJANGO_SECURE_COOKIES`. Quay lại mục 0 Câu 1.

Kiểm tra nhanh bằng dòng lệnh:

```powershell
curl.exe -s http://127.0.0.1:8000/core/health/
```

Phải trả `{"status": "ok"}`.

---

## 7. Đặt chạy tự động (dịch vụ Windows)

Chạy `serve.py` trong cửa sổ PowerShell chỉ dùng để thử. Muốn chạy thật, phải cài
thành dịch vụ để tự khởi động lại khi khởi động máy chủ.

### Cách đơn giản: dùng NSSM

Tải NSSM từ `https://nssm.cc/download`, giải nén, chép `nssm.exe` (bản `win64`) vào `D:\agrigov\`.

```powershell
# Cài dịch vụ
.\nssm.exe install AgriGov "D:\agrigov\.venv\Scripts\python.exe" "D:\agrigov\serve.py --host 0.0.0.0 --port 8000"

# Đặt thư mục làm việc
.\nssm.exe set AgriGov AppDirectory "D:\agrigov"

# Ghi log
.\nssm.exe set AgriGov AppStdout "D:\agrigov\logs\service-out.log"
.\nssm.exe set AgriGov AppStderr "D:\agrigov\logs\service-err.log"

# Tự khởi động lại nếu chết
.\nssm.exe set AgriGov AppExit Default Restart
.\nssm.exe set AgriGov AppRestartDelay 5000

# Khởi động
.\nssm.exe start AgriGov
```

Kiểm tra:

```powershell
Get-Service AgriGov
curl.exe -s http://127.0.0.1:8000/core/health/
```

### Mở tường lửa

```powershell
New-NetFirewallRule -DisplayName "AgriGov 8000" -Direction Inbound -Protocol TCP -LocalPort 8000 -Action Allow
```

Nếu chỉ muốn mở cho mạng nội bộ, thêm `-RemoteAddress 10.1.2.0/24` (đổi theo dải mạng của bạn).

---

## 8. Đặt lịch chạy tác vụ định kỳ

`run_schedules` làm hai việc: chuyển bản tin cảnh báo quá hạn sang "hết hiệu lực",
và tổng hợp/gửi báo cáo định kỳ. **Không đặt lịch thì hai việc này không bao giờ chạy.**

### Tạo bằng Task Scheduler

Mở PowerShell Administrator:

```powershell
$action = New-ScheduledTaskAction -Execute "D:\agrigov\.venv\Scripts\python.exe" `
    -Argument "manage.py run_schedules" -WorkingDirectory "D:\agrigov"

$trigger = New-ScheduledTaskTrigger -Once -At (Get-Date).Date.AddHours(7) `
    -RepetitionInterval (New-TimeSpan -Hours 1)

Register-ScheduledTask -TaskName "AgriGov - run_schedules" -Action $action `
    -Trigger $trigger -RunLevel Highest -User "SYSTEM"
```

Chạy thử ngay để chắc lịch hoạt động:

```powershell
Start-ScheduledTask -TaskName "AgriGov - run_schedules"
Start-Sleep 10
Get-ScheduledTaskInfo -TaskName "AgriGov - run_schedules" | Select-Object LastTaskResult
```

`LastTaskResult = 0` là thành công.

> **Lỗi tiếng Việt trong log:** Task Scheduler không có `PYTHONIOENCODING`. Nếu log
> hiện ký tự lạ, thêm biến môi trường vào `.env` hoặc sửa Action thành:
> `cmd /c "set PYTHONIOENCODING=utf-8 && D:\agrigov\.venv\Scripts\python.exe manage.py run_schedules"`

---

## 9. Bản đồ khi không có internet

Mặc định bản đồ lấy ảnh nền từ OpenStreetMap qua internet. Nếu máy chủ và máy trạm
đều không ra internet, bản đồ sẽ trống — phần đánh dấu điểm vẫn hiện nhưng không có nền.

Ba hướng xử lý, chọn một:

**Hướng A — Cho phép ra internet có kiểm soát.** Mở tường lửa cho máy chủ đến
`tile.openstreetmap.org` (cổng 443). Đơn giản nhất.

**Hướng B — Dựng tile server nội bộ.** Cài `tileserver-gl` hoặc dùng GeoServer, tải
gói dữ liệu bản đồ Việt Nam, chạy nội bộ.

**Hướng C — Dùng ảnh nền tự tạo.** Tạo một ảnh tĩnh lớn của tỉnh, phục vụ từ `/static/`.

Với B và C, sửa URL tile trong `templates/mapview/map.html` — tìm chỗ khai báo
`L.tileLayer(` và đổi địa chỉ.

---

## 10. Sao lưu

Hệ thống có chức năng sao lưu trong `/system/backups/`, dùng `pg_dump`. Cần đặt
`PG_BIN_DIR` trong `.env`:

```ini
PG_BIN_DIR=C:\Program Files\PostgreSQL\18\bin
```

Nhưng **không nên chỉ dựa vào nút bấm tay**. Đặt lịch sao lưu tự động:

```powershell
$action = New-ScheduledTaskAction -Execute "D:\agrigov\.venv\Scripts\python.exe" `
    -Argument "-c `"import os,django;os.environ.setdefault('DJANGO_SETTINGS_MODULE','config.settings');django.setup();from sysadmin import backup;from accounts.models import User;backup.create_backup(User.objects.filter(is_superuser=True).first())`"" `
    -WorkingDirectory "D:\agrigov"

$trigger = New-ScheduledTaskTrigger -Daily -At 23:00

Register-ScheduledTask -TaskName "AgriGov - backup" -Action $action `
    -Trigger $trigger -RunLevel Highest -User "SYSTEM"
```

**Phải sao lưu cả thư mục `D:\agrigov\media`**, không chỉ database. Ảnh hiện trường
nằm ở đó; mất database thì phục hồi được, mất ảnh gốc thì không.

Ba thứ cần sao lưu, chép ra ổ khác hoặc máy khác:

| Thứ | Đường dẫn | Vì sao |
|---|---|---|
| Database | file `.dump` trong `backups/` | Toàn bộ dữ liệu nghiệp vụ |
| Ảnh và tệp đính kèm | `D:\agrigov\media\` | Ảnh hiện trường gốc, không tái tạo được |
| Cấu hình | `D:\agrigov\.env` | Chứa khoá và mật khẩu; để nơi riêng, không chép lẫn |

Kiểm tra bản sao lưu có dùng được không — **làm thử ít nhất một lần**:

```powershell
.venv\Scripts\python.exe manage.py shell
```
```python
from sysadmin import backup
from accounts.models import User
print(backup.create_backup(User.objects.filter(is_superuser=True).first()))
```
Phải in ra tên file và file phải có kích thước lớn hơn 0. Bản sao lưu chưa từng thử
khôi phục thì chưa được coi là có sao lưu.

---

## 11. Cập nhật phiên bản mới

```powershell
# Dừng dịch vụ
.\nssm.exe stop AgriGov

# Sao lưu trước khi cập nhật — dùng chức năng trong /system/backups/ hoặc chạy:
.venv\Scripts\python.exe -c "import os,django;os.environ.setdefault('DJANGO_SETTINGS_MODULE','config.settings');django.setup();from sysadmin import backup;from accounts.models import User;print(backup.create_backup(User.objects.filter(is_superuser=True).first()))"

# Chép mã mới vào, ghi đè (giữ nguyên .env và media)

# Chạy migration
.venv\Scripts\python.exe manage.py migrate
.venv\Scripts\python.exe manage.py collectstatic --noinput

# Chạy test trước khi mở lại
.venv\Scripts\python.exe manage.py test --noinput

# Khởi động lại
.\nssm.exe start AgriGov
```

Nếu có sửa giao diện, phải build lại CSS **trước khi** `collectstatic`:

```powershell
npm install
npm run build
```

Máy chủ không có Node.js thì build ở máy khác rồi chép `static/css/app.css` sang.

---

## 12. Xử lý sự cố thường gặp

| Hiện tượng | Nguyên nhân | Cách sửa |
|---|---|---|
| Trang chỉ có chữ trơn, không màu | Thiếu `collectstatic` | Chạy `manage.py collectstatic --noinput` |
| Đăng nhập quay lại trang login | Cookie `Secure` nhưng chạy HTTP | Đặt `DJANGO_SECURE_COOKIES=0` |
| Mọi trang trả 500 | Database "in recovery mode" | Chờ 1–2 phút, PostgreSQL tự phục hồi |
| Ảnh hiện trường không hiện | Route `/media/` chưa chạy | Kiểm tra `config/urls.py` có `serve_media` |
| "DisallowedHost" | IP chưa có trong `ALLOWED_HOSTS` | Thêm IP vào `DJANGO_ALLOWED_HOSTS` |
| Bản đồ trống | Không có internet | Xem mục 9 |
| Log hiện ký tự lạ | Console Windows sai bảng mã | `[Console]::OutputEncoding = [System.Text.Encoding]::UTF8` |

### Xem log

```
D:\agrigov\logs\app.log
```

File tự xoay vòng ở 10 MB, giữ 10 bản. Lỗi 500 luôn được ghi kèm traceback đầy đủ.

---

## 13. Nghiệm thu trước khi bàn giao

Đừng chỉ kiểm tra "mở được trang". Cho **người dùng thật** tự làm các việc sau,
vì đây là chỗ tôi không thể tự kiểm tra được:

- [ ] Lãnh đạo: mở dashboard, đọc số liệu, đối chiếu với báo cáo miệng
- [ ] Chuyên môn: lập một kế hoạch điều tra thật, kiểm tra danh mục cây trồng/SVGH đúng ngành
- [ ] Điều tra viên: nhập một phiếu thật ngoài đồng bằng điện thoại, chụp ảnh, gửi
- [ ] Người phê duyệt: duyệt kế hoạch và phát hành một bản tin cảnh báo
- [ ] Văn thư: soạn một tin, đăng lên cổng thông tin công khai
- [ ] Kiểm tra phân quyền: dùng tài khoản `viewer` xác nhận bị chặn đúng chỗ
- [ ] Xuất một báo cáo Excel và một PDF, mở xem tiếng Việt có dấu đúng
- [ ] Sao lưu thử, rồi khôi phục thử ra database khác

---

## Phụ lục A — Chạy trên Linux

Các bước tương đương, dùng `gunicorn` thay `waitress`:

```bash
python3 -m venv .venv
.venv/bin/pip install -r requirements.txt gunicorn
.venv/bin/python manage.py migrate
.venv/bin/python manage.py collectstatic --noinput
.venv/bin/gunicorn config.wsgi:application --bind 0.0.0.0:8000 --workers 4
```

Dịch vụ systemd tại `/etc/systemd/system/agrigov.service`:

```ini
[Unit]
Description=AgriGov TT&BVTV
After=network.target postgresql.service

[Service]
User=agrigov
WorkingDirectory=/opt/agrigov
Environment="PYTHONIOENCODING=utf-8"
ExecStart=/opt/agrigov/.venv/bin/gunicorn config.wsgi:application --bind 0.0.0.0:8000 --workers 4
Restart=always

[Install]
WantedBy=multi-user.target
```

Cron cho `run_schedules`:

```bash
0 * * * * cd /opt/agrigov && .venv/bin/python manage.py run_schedules >> logs/cron.log 2>&1
```

---

## Phụ lục B — Danh sách kiểm tra một trang

Dùng khi cần rà lại toàn bộ sau khi cập nhật. Lưu thành `check.ps1` trong thư mục dự án:

```powershell
param(
    [string]$Base = "http://127.0.0.1:8000",
    [string]$User = "admin"
)

$ErrorActionPreference = "Stop"
$s = New-Object Microsoft.PowerShell.Commands.WebRequestSession

# Đăng nhập
$login = Invoke-WebRequest "$Base/accounts/login/" -WebSession $s -UseBasicParsing
$tok = ([regex]'name="csrfmiddlewaretoken" value="([^"]+)"').Match($login.Content).Groups[1].Value
$pwd = Read-Host "Mật khẩu cho '$User'" -AsSecureString
$plain = [Runtime.InteropServices.Marshal]::PtrToStringAuto(
    [Runtime.InteropServices.Marshal]::SecureStringToBSTR($pwd))
Invoke-WebRequest "$Base/accounts/login/" -Method POST -WebSession $s -UseBasicParsing `
    -Body @{ username = $User; password = $plain; csrfmiddlewaretoken = $tok } | Out-Null

# Các trang cần kiểm tra
$pages = @("/", "/reports/", "/reports/dashboard/", "/reports/summary/", "/map/",
    "/surveys/records/", "/surveys/plans/", "/surveys/my-tasks/", "/surveys/templates/",
    "/surveys/sandbox/", "/surveys/offline/", "/forecasts/forecasts/", "/forecasts/analysis/",
    "/alerts/alerts/", "/alerts/followups/", "/cms/posts/", "/catalog/", "/system/",
    "/system/audit/", "/system/logins/", "/system/backups/", "/system/documents/",
    "/accounts/roles/", "/accounts/profile/", "/accounts/notifications/")

$bad = 0
foreach ($p in $pages) {
    try {
        $x = Invoke-WebRequest "$Base$p" -WebSession $s -UseBasicParsing -TimeoutSec 20
        $css = if ($x.Content -match 'static/css/app\.') { "OK" } else { "THIEU-CSS" }
        if ($x.StatusCode -ne 200 -or $css -ne "OK") { $bad++ }
        "{0,-26} {1} {2}" -f $p, $x.StatusCode, $css
    } catch {
        $bad++
        "{0,-26} LOI {1}" -f $p, [int]$_.Exception.Response.StatusCode
    }
}

"{0}`n  Ket qua: {1}/{2} trang dat" -f ("-" * 50), ($pages.Count - $bad), $pages.Count
if ($bad -gt 0) { exit 1 }
```

Chạy:

```powershell
.\check.ps1
```

Mọi dòng phải là `200 OK`. Dòng `THIEU-CSS` là lỗi `collectstatic`.
Dòng `LOI 403` là đúng nếu tài khoản thử không có quyền module đó —
dùng tài khoản quản trị để kiểm tra toàn bộ.
