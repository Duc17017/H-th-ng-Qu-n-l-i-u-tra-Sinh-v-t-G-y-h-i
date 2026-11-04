"""Chạy ứng dụng bằng WSGI server thật (waitress) — dùng cho triển khai nội bộ.

Khác với `manage.py runserver` (chỉ dành cho phát triển), waitress chịu được
nhiều kết nối đồng thời và không tự nạp lại mã khi có thay đổi.

Cách dùng:
    .venv\\Scripts\\python.exe serve.py
    .venv\\Scripts\\python.exe serve.py --host 0.0.0.0 --port 8080 --threads 8
"""
import argparse
import os
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
os.environ.setdefault("DJANGO_SETTINGS_MODULE", "config.settings")

from dotenv import load_dotenv  # noqa: E402

load_dotenv(Path(__file__).resolve().parent / ".env")

import django  # noqa: E402
from django.conf import settings  # noqa: E402
from django.core.management import call_command  # noqa: E402
from django.core.wsgi import get_wsgi_application  # noqa: E402
from waitress import serve  # noqa: E402

django.setup()


def main():
    parser = argparse.ArgumentParser(description="Chạy AgriGov TT&BVTV bằng waitress")
    parser.add_argument("--host", default=os.getenv("SERVE_HOST", "127.0.0.1"))
    parser.add_argument("--port", type=int, default=int(os.getenv("SERVE_PORT", "8000")))
    parser.add_argument("--threads", type=int, default=int(os.getenv("SERVE_THREADS", "8")))
    parser.add_argument("--no-check", action="store_true", help="Bỏ qua bước kiểm tra cấu hình")
    args = parser.parse_args()

    if not args.no_check:
        call_command("check")

    if not settings.DEBUG and settings.SECRET_KEY.startswith("dev-"):
        print("CẢNH BÁO: DJANGO_SECRET_KEY vẫn là giá trị mặc định của bản phát triển.")
        print("         Hãy đổi trong .env trước khi mở cho người dùng thật.")

    print(f"\n  AgriGov TT&BVTV — http://{args.host}:{args.port}/")
    print(f"  DEBUG={settings.DEBUG}  threads={args.threads}  "
          f"db={settings.DATABASES['default']['ENGINE'].rsplit('.', 1)[-1]}\n")
    serve(get_wsgi_application(), host=args.host, port=args.port, threads=args.threads,
          ident="AgriGov")


if __name__ == "__main__":
    main()
