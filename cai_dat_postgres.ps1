# Chay: powershell -ExecutionPolicy Bypass -File .\cai_dat_postgres.ps1
# Doc mat khau trong .env, tao database (neu chua co), tao bang, nap du lieu mau.
$ErrorActionPreference = "Stop"
Set-Location $PSScriptRoot
$env:PYTHONUTF8 = "1"
Remove-Item Env:DB_ENGINE -ErrorAction SilentlyContinue

$cfg = @{}
Get-Content .env | Where-Object { $_ -match '^\s*[A-Z_]+=' } | ForEach-Object {
    $k, $v = $_ -split '=', 2
    $cfg[$k.Trim()] = $v.Trim()
}
if (-not $cfg["DB_PASSWORD"]) { Write-Host "Chua co mat khau: mo file .env, dien DB_PASSWORD roi chay lai." -ForegroundColor Yellow; exit 1 }

$bin = if ($cfg["PG_BIN_DIR"]) { $cfg["PG_BIN_DIR"] } else { "C:\Program Files\PostgreSQL\18\bin" }
$psql = Join-Path $bin "psql.exe"
$env:PGPASSWORD = $cfg["DB_PASSWORD"]
$hostName = if ($cfg["DB_HOST"]) { $cfg["DB_HOST"] } else { "localhost" }
$port = if ($cfg["DB_PORT"]) { $cfg["DB_PORT"] } else { "5432" }
$user = if ($cfg["DB_USER"]) { $cfg["DB_USER"] } else { "postgres" }
$db = if ($cfg["DB_NAME"]) { $cfg["DB_NAME"] } else { "pest_survey" }

$exists = & $psql -h $hostName -p $port -U $user -d postgres -tAc "SELECT 1 FROM pg_database WHERE datname='$db'" 2>&1
if ($LASTEXITCODE -ne 0) { Write-Host "Khong ket noi duoc PostgreSQL (sai mat khau?): $exists" -ForegroundColor Red; exit 1 }
if (-not $exists) {
    & $psql -h $hostName -p $port -U $user -d postgres -c "CREATE DATABASE $db ENCODING 'UTF8' TEMPLATE template0"
    if ($LASTEXITCODE -ne 0) { exit 1 }
    Write-Host "Da tao database $db" -ForegroundColor Green
}

$py = ".\.venv\Scripts\python.exe"
& $py manage.py migrate
if ($LASTEXITCODE -ne 0) { exit 1 }
& $py manage.py seed_demo
Write-Host "Xong. Chay: .\.venv\Scripts\python manage.py runserver" -ForegroundColor Green
