param(
    [string]$Base = "http://127.0.0.1:8000",
    [string]$User = "admin",
    [string]$Password = ""
)

# Kiểm tra toàn bộ trang sau khi triển khai hoặc cập nhật.
# Dùng:  .\check.ps1
#        .\check.ps1 -Base http://10.1.2.30:8000 -User admin

$ErrorActionPreference = "Stop"
$s = New-Object Microsoft.PowerShell.Commands.WebRequestSession

$login = Invoke-WebRequest "$Base/accounts/login/" -WebSession $s -UseBasicParsing
$m = [regex]'name="csrfmiddlewaretoken" value="([^"]+)"'
$tok = $m.Match($login.Content).Groups[1].Value
if (-not $tok) { Write-Host "Khong tim thay CSRF token - kiem tra lai dia chi $Base" -ForegroundColor Red; exit 1 }

if (-not $Password) {
    $sec = Read-Host "Mat khau cho '$User'" -AsSecureString
    $Password = [Runtime.InteropServices.Marshal]::PtrToStringAuto(
        [Runtime.InteropServices.Marshal]::SecureStringToBSTR($sec))
}

try {
    Invoke-WebRequest "$Base/accounts/login/" -Method POST -WebSession $s -UseBasicParsing `
        -Body @{ username = $User; password = $Password; csrfmiddlewaretoken = $tok } | Out-Null
} catch {
    Write-Host "Dang nhap that bai: $($_.Exception.Message)" -ForegroundColor Red; exit 1
}

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

# Tài nguyên tĩnh
""
foreach ($a in @("/static/vendor/leaflet/leaflet.js", "/static/vendor/chartjs/chart.umd.min.js",
                 "/static/vendor/fonts/material-symbols-outlined.woff2")) {
    try {
        $x = Invoke-WebRequest "$Base$a" -UseBasicParsing -TimeoutSec 20
        "{0,-52} {1} {2}" -f $a, $x.StatusCode, $x.RawContentLength
    } catch {
        $bad++
        "{0,-52} LOI {1}" -f $a, [int]$_.Exception.Response.StatusCode
    }
}

"`n" + ("-" * 50)
if ($bad -eq 0) {
    Write-Host "  Ket qua: TAT CA DAT ($($pages.Count) trang)" -ForegroundColor Green
} else {
    Write-Host "  Ket qua: $bad muc LOI / $($pages.Count) trang" -ForegroundColor Red
    exit 1
}
