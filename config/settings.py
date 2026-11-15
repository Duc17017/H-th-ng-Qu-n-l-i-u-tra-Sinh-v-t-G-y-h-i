import os
from pathlib import Path

from dotenv import load_dotenv

BASE_DIR = Path(__file__).resolve().parent.parent
load_dotenv(BASE_DIR / ".env")

SECRET_KEY = os.getenv("DJANGO_SECRET_KEY", "dev-insecure-change-me")
DEBUG = os.getenv("DJANGO_DEBUG", "1") == "1"
ALLOWED_HOSTS = [h.strip() for h in os.getenv("DJANGO_ALLOWED_HOSTS", "localhost,127.0.0.1").split(",")]
CSRF_TRUSTED_ORIGINS = [o for o in os.getenv("DJANGO_CSRF_ORIGINS", "").split(",") if o]

INSTALLED_APPS = [
    "django.contrib.auth",
    "django.contrib.contenttypes",
    "django.contrib.sessions",
    "django.contrib.messages",
    "django.contrib.staticfiles",
    "core",
    "accounts",
    "catalog",
    "cms",
    "surveys",
    "mapview",
    "forecasts",
    "alerts",
    "reports",
    "sysadmin",
]

MIDDLEWARE = [
    "django.middleware.security.SecurityMiddleware",
    # Phục vụ CSS/JS/font trực tiếp từ Django khi chạy thật (DEBUG=0).
    # Không có lớp này, toàn bộ giao diện mất style vì Django không tự phục vụ static.
    "whitenoise.middleware.WhiteNoiseMiddleware",
    "django.contrib.sessions.middleware.SessionMiddleware",
    "django.middleware.common.CommonMiddleware",
    "django.middleware.csrf.CsrfViewMiddleware",
    "django.contrib.auth.middleware.AuthenticationMiddleware",
    "django.contrib.messages.middleware.MessageMiddleware",
    "django.middleware.clickjacking.XFrameOptionsMiddleware",
    "core.middleware.CurrentUserMiddleware",
]

ROOT_URLCONF = "config.urls"
WSGI_APPLICATION = "config.wsgi.application"

TEMPLATES = [{
    "BACKEND": "django.template.backends.django.DjangoTemplates",
    "DIRS": [BASE_DIR / "templates"],
    "APP_DIRS": True,
    "OPTIONS": {"context_processors": [
        "django.template.context_processors.request",
        "django.contrib.auth.context_processors.auth",
        "django.contrib.messages.context_processors.messages",
        "core.context_processors.app_context",
    ]},
}]

# Cơ sở dữ liệu: PostgreSQL (mặc định). DB_ENGINE=sqlite chỉ dùng để thử nhanh.
# Trên Render: sẽ cấp DATABASE_URL (tự động resolve từ internal postgres service)
if os.getenv("DATABASE_URL"):
    # Render cung cấp DATABASE_URL, parse nó
    import dj_database_url
    DATABASES = {"default": dj_database_url.config(conn_max_age=600, conn_health_checks=True)}
elif os.getenv("DB_ENGINE", "postgres") == "sqlite":
    DATABASES = {"default": {"ENGINE": "django.db.backends.sqlite3", "NAME": BASE_DIR / "db.sqlite3"}}
else:
    DATABASES = {"default": {
        "ENGINE": "django.db.backends.postgresql",
        "NAME": os.getenv("DB_NAME", "pest_survey"),
        "USER": os.getenv("DB_USER", "postgres"),
        "PASSWORD": os.getenv("DB_PASSWORD", ""),
        "HOST": os.getenv("DB_HOST", "localhost"),
        "PORT": os.getenv("DB_PORT", "5432"),
    }}

AUTH_USER_MODEL = "accounts.User"
AUTH_PASSWORD_VALIDATORS = [
    {"NAME": "django.contrib.auth.password_validation.UserAttributeSimilarityValidator"},
    {"NAME": "django.contrib.auth.password_validation.MinimumLengthValidator", "OPTIONS": {"min_length": 8}},
    {"NAME": "django.contrib.auth.password_validation.CommonPasswordValidator"},
    {"NAME": "django.contrib.auth.password_validation.NumericPasswordValidator"},
]
LOGIN_URL = "accounts:login"
LOGIN_REDIRECT_URL = "reports:dashboard"
LOGOUT_REDIRECT_URL = "cms:home"

LANGUAGE_CODE = "vi"
TIME_ZONE = "Asia/Ho_Chi_Minh"
USE_I18N = True
USE_TZ = True

STATIC_URL = "static/"
STATICFILES_DIRS = [BASE_DIR / "static"]
STATIC_ROOT = BASE_DIR / "staticfiles"
MEDIA_URL = "media/"
MEDIA_ROOT = BASE_DIR / "media"

# WhiteNoise phục vụ file tĩnh cho môi trường thật. Nén sẵn khi collectstatic.
STORAGES = {
    "default": {"BACKEND": "django.core.files.storage.FileSystemStorage"},
    "staticfiles": {
        "BACKEND": "whitenoise.storage.CompressedManifestStaticFilesStorage"
        if not DEBUG else "django.contrib.staticfiles.storage.StaticFilesStorage",
    },
}
BACKUP_DIR = BASE_DIR / "backups"
DATA_UPLOAD_MAX_MEMORY_SIZE = 20 * 1024 * 1024
DEFAULT_AUTO_FIELD = "django.db.models.BigAutoField"
# Mặc định của Django là "same-origin" nên các máy chủ ảnh nền bản đồ (OpenStreetMap...) từ chối tải.
SECURE_REFERRER_POLICY = "strict-origin-when-cross-origin"

if os.getenv("EMAIL_HOST"):
    EMAIL_BACKEND = "django.core.mail.backends.smtp.EmailBackend"
    EMAIL_HOST = os.getenv("EMAIL_HOST")
    EMAIL_PORT = int(os.getenv("EMAIL_PORT", "587"))
    EMAIL_HOST_USER = os.getenv("EMAIL_USER", "")
    EMAIL_HOST_PASSWORD = os.getenv("EMAIL_PASSWORD", "")
    # Cổng 465 dùng SSL ngầm định; các cổng khác (587) dùng STARTTLS.
    EMAIL_USE_SSL = os.getenv("EMAIL_USE_SSL", "1" if EMAIL_PORT == 465 else "0") == "1"
    EMAIL_USE_TLS = not EMAIL_USE_SSL
else:
    EMAIL_BACKEND = "django.core.mail.backends.console.EmailBackend"
DEFAULT_FROM_EMAIL = os.getenv("DEFAULT_FROM_EMAIL", "bvtv@example.local")

# Đường dẫn font Unicode để xuất PDF tiếng Việt (tự dò nếu để trống)
PDF_FONT_PATH = os.getenv("PDF_FONT_PATH", "")
PG_BIN_DIR = os.getenv("PG_BIN_DIR", "")

# ── Ghi log ────────────────────────────────────────────────────────────────────
# Không có LOGGING thì lỗi production sẽ im lặng, không truy vết được.
LOG_LEVEL = os.getenv("DJANGO_LOG_LEVEL", "INFO")
LOG_DIR = BASE_DIR / "logs"
LOG_DIR.mkdir(exist_ok=True)

LOGGING = {
    "version": 1,
    "disable_existing_loggers": False,
    "formatters": {
        "verbose": {"format": "{levelname} {asctime} {name} {message}", "style": "{"},
    },
    "handlers": {
        "console": {"class": "logging.StreamHandler", "formatter": "verbose"},
        "file": {
            "class": "logging.handlers.RotatingFileHandler",
            "filename": LOG_DIR / "app.log",
            "maxBytes": 10 * 1024 * 1024,
            "backupCount": 10,
            "encoding": "utf-8",
            "formatter": "verbose",
        },
    },
    "root": {"handlers": ["console", "file"], "level": LOG_LEVEL},
    "loggers": {
        "django.request": {"handlers": ["console", "file"], "level": "WARNING", "propagate": False},
        "django.security": {"handlers": ["console", "file"], "level": "WARNING", "propagate": False},
        "core": {"handlers": ["console", "file"], "level": LOG_LEVEL, "propagate": False},
        "alerts": {"handlers": ["console", "file"], "level": LOG_LEVEL, "propagate": False},
        "accounts": {"handlers": ["console", "file"], "level": LOG_LEVEL, "propagate": False},
    },
}

# ── Chống dò mật khẩu (brute-force) ───────────────────────────────────────────
# Số lần đăng nhập sai liên tiếp trước khi tạm khoá, và thời gian khoá (giây).
LOGIN_MAX_ATTEMPTS = int(os.getenv("LOGIN_MAX_ATTEMPTS", "5"))
LOGIN_LOCKOUT_SECONDS = int(os.getenv("LOGIN_LOCKOUT_SECONDS", "900"))

# ── Đăng ký tài khoản từ cổng thông tin ───────────────────────────────────────
# Người tự đăng ký LUÔN chỉ là vai trò "viewer" (Người xem); không có cách nào
# tự nâng quyền qua form. Tài khoản tạo ra dùng ngay được đọc tin, không đụng
# tới dữ liệu điều tra.
REGISTRATION_OPEN = os.getenv("REGISTRATION_OPEN", "1") == "1"
# False = tài khoản phải chờ quản trị viên kích hoạt mới đăng nhập được.
REGISTRATION_AUTO_ACTIVE = os.getenv("REGISTRATION_AUTO_ACTIVE", "1") == "1"
# Số lần đăng ký tối đa từ một IP trong một giờ (chống spam).
REGISTRATION_MAX_PER_IP = int(os.getenv("REGISTRATION_MAX_PER_IP", "3"))
# Để trống = nhận mọi tên miền; ví dụ "gov.vn,chicucttbvt.vn" = chỉ nhận nội bộ.
REGISTRATION_EMAIL_DOMAINS = [
    d.strip().lower() for d in os.getenv("REGISTRATION_EMAIL_DOMAINS", "").split(",") if d.strip()]

# ── Tác vụ nền (email, SMS) ───────────────────────────────────────────────────
# thread: chạy ngay trong luồng nền | worker: chờ `manage.py process_tasks --loop` | eager: chạy tại chỗ
TASKS_MODE = os.getenv("TASKS_MODE", "thread")

# ── SMS qua eSMS.vn (để trống khoá = chế độ thử, chỉ ghi log) ───────────────────
ESMS_API_KEY = os.getenv("ESMS_API_KEY", "")
ESMS_SECRET_KEY = os.getenv("ESMS_SECRET_KEY", "")
ESMS_SMS_TYPE = os.getenv("ESMS_SMS_TYPE", "8")
ESMS_BRANDNAME = os.getenv("ESMS_BRANDNAME", "")

# ── Đăng nhập LDAP / Active Directory (bật bằng cách đặt LDAP_SERVER_URI) ──────
LDAP_SERVER_URI = os.getenv("LDAP_SERVER_URI", "")          # ví dụ ldaps://dc.so.gov.vn:636
LDAP_USER_DN_TEMPLATE = os.getenv("LDAP_USER_DN_TEMPLATE", "")  # ví dụ {username}@so.gov.vn hoặc uid={username},ou=users,dc=so,dc=gov,dc=vn
LDAP_SEARCH_BASE = os.getenv("LDAP_SEARCH_BASE", "")        # ví dụ dc=so,dc=gov,dc=vn (dùng để lấy họ tên, email, SĐT)
LDAP_DEFAULT_ROLE = os.getenv("LDAP_DEFAULT_ROLE", "viewer")
LDAP_AUTO_CREATE = os.getenv("LDAP_AUTO_CREATE", "1") == "1"
AUTHENTICATION_BACKENDS = ["accounts.ldap_backend.LdapBackend", "django.contrib.auth.backends.ModelBackend"]

# ── Trợ lý AI hội thoại (tùy chọn, tương thích OpenAI Chat Completions) ────────
# Để trống = chỉ dùng trợ lý trích rút offline.
AI_API_URL = os.getenv("AI_API_URL", "")      # ví dụ https://api.openai.com/v1/chat/completions
AI_API_KEY = os.getenv("AI_API_KEY", "")
AI_MODEL = os.getenv("AI_MODEL", "")

if not DEBUG:
    SECURE_CONTENT_TYPE_NOSNIFF = True
    SESSION_COOKIE_HTTPONLY = True
    CSRF_COOKIE_HTTPONLY = False  # form đăng nhập cần đọc token bằng JS trong vài trang
    X_FRAME_OPTIONS = "DENY"

# ── HTTPS ────────────────────────────────────────────────────────────────────
# Mặc định BẬT vì đó là cấu hình đúng cho hệ thống chạy thật qua HTTPS.
# Nếu triển khai trong mạng nội bộ KHÔNG có TLS, phải đặt DJANGO_SECURE_COOKIES=0,
# nếu không trình duyệt sẽ từ chối cookie phiên và KHÔNG AI ĐĂNG NHẬP ĐƯỢC.
# Đặt ngoài khối `if not DEBUG` để luôn có công tắc rõ ràng.
SECURE_COOKIES = os.getenv("DJANGO_SECURE_COOKIES", "1") == "1"
if not DEBUG:
    SESSION_COOKIE_SECURE = SECURE_COOKIES
    CSRF_COOKIE_SECURE = SECURE_COOKIES
    if not SECURE_COOKIES:
        import warnings

        warnings.warn(
            "DJANGO_SECURE_COOKIES=0: cookie phiên không có cờ Secure. "
            "Chỉ dùng khi thật sự không có HTTPS. Thông tin đăng nhập có thể bị đánh cắp.",
            RuntimeWarning,
        )

    SECURE_HSTS_SECONDS = int(os.getenv("DJANGO_HSTS_SECONDS", "0"))
    SECURE_HSTS_INCLUDE_SUBDOMAINS = SECURE_HSTS_SECONDS > 0
    SECURE_HSTS_PRELOAD = False
    # Chỉ bật khi đã có HTTPS chạy ổn định. Bật khi chưa có TLS sẽ khoá người dùng ra ngoài.
    SECURE_SSL_REDIRECT = os.getenv("DJANGO_SSL_REDIRECT", "0") == "1"
    if os.getenv("DJANGO_BEHIND_PROXY", "0") == "1":
        SECURE_PROXY_SSL_HEADER = ("HTTP_X_FORWARDED_PROTO", "https")
