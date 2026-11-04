"""Sao lưu / khôi phục PostgreSQL bằng pg_dump / pg_restore (không đưa mật khẩu vào dòng lệnh)."""
import os
import re
import shutil
import subprocess
from pathlib import Path

from django.conf import settings
from django.utils import timezone

from .models import BackupRecord

SAFE_NAME = re.compile(r"^[A-Za-z0-9_.\-]+\.dump$")


class BackupError(Exception):
    pass


def _tool(name):
    d = settings.PG_BIN_DIR
    exe = name + (".exe" if os.name == "nt" else "")
    if d and (Path(d) / exe).exists():
        return str(Path(d) / exe)
    found = shutil.which(name)
    if found:
        return found
    if os.name == "nt":
        for p in sorted(Path(r"C:\Program Files\PostgreSQL").glob(f"*/bin/{exe}"), reverse=True):
            return str(p)
    raise BackupError(f"Không tìm thấy {name}. Đặt PG_BIN_DIR trong .env.")


def _env():
    db = settings.DATABASES["default"]
    if "postgresql" not in db["ENGINE"]:
        raise BackupError("Chức năng sao lưu chỉ hỗ trợ PostgreSQL.")
    env = os.environ.copy()
    env["PGPASSWORD"] = db.get("PASSWORD") or ""
    return db, env


def backup_dir():
    p = Path(settings.BACKUP_DIR)
    p.mkdir(parents=True, exist_ok=True)
    return p


def list_backups():
    out = []
    for f in sorted(backup_dir().glob("*.dump"), reverse=True):
        st = f.stat()
        out.append({"name": f.name, "size": st.st_size, "mtime": timezone.datetime.fromtimestamp(st.st_mtime)})
    return out


def create_backup(user):
    db, env = _env()
    name = f"pest_{timezone.localtime():%Y%m%d_%H%M%S}.dump"
    path = backup_dir() / name
    cmd = [_tool("pg_dump"), "-h", db["HOST"] or "localhost", "-p", str(db["PORT"] or 5432), "-U", db["USER"],
           "-Fc", "-f", str(path), db["NAME"]]
    res = subprocess.run(cmd, env=env, capture_output=True, text=True, timeout=1800)
    ok = res.returncode == 0 and path.exists()
    BackupRecord.objects.create(action="backup", filename=name, size_bytes=path.stat().st_size if ok else 0,
                                success=ok, message=(res.stderr or "")[-2000:], created_by=user)
    if not ok:
        path.unlink(missing_ok=True)
        raise BackupError("Sao lưu thất bại: " + (res.stderr or "lỗi không xác định")[-300:])
    return name


def restore_backup(name, user):
    if not SAFE_NAME.match(name):
        raise BackupError("Tên tệp sao lưu không hợp lệ.")
    path = backup_dir() / name
    if not path.is_file():
        raise BackupError("Không tìm thấy tệp sao lưu.")
    db, env = _env()
    cmd = [_tool("pg_restore"), "-h", db["HOST"] or "localhost", "-p", str(db["PORT"] or 5432), "-U", db["USER"],
           "-d", db["NAME"], "--clean", "--if-exists", "--no-owner", str(path)]
    res = subprocess.run(cmd, env=env, capture_output=True, text=True, timeout=3600)
    ok = res.returncode == 0
    BackupRecord.objects.create(action="restore", filename=name, size_bytes=path.stat().st_size, success=ok,
                                message=(res.stderr or "")[-2000:], created_by=user)
    if not ok:
        raise BackupError("Khôi phục có lỗi: " + (res.stderr or "")[-300:])
