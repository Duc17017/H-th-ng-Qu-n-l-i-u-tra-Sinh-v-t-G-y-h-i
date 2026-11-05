"""Phục vụ file tải lên (media) khi chạy thật, có kiểm soát truy cập.

Django chỉ tự phục vụ `MEDIA_URL` khi DEBUG=1. Khi chạy thật, các chỗ dùng
`.file.url` (ảnh hiện trường, ảnh bìa bài viết, tệp báo cáo) sẽ trả 404.

Hai hướng xử lý:
  1. Đặt máy chủ web (nginx/IIS) phục vụ thẳng thư mục media — nhanh nhất.
  2. Để Django phục vụ qua view này — tiện cho mạng nội bộ nhỏ, và cho phép
     kiểm tra quyền trước khi trả tệp.

View này chỉ phục vụ tệp nằm trong MEDIA_ROOT (chặn `..`), và với tệp nhạy cảm
(phiếu điều tra, tài liệu, báo cáo) thì yêu cầu đã đăng nhập.
"""
import mimetypes
import posixpath
from pathlib import Path

from django.conf import settings
from django.http import FileResponse, Http404
from django.utils._os import safe_join

# Thư mục con yêu cầu đăng nhập mới được tải.
PROTECTED_PREFIXES = ("records/", "documents/", "reports/", "backups/")
# Thư mục công khai (ảnh bìa bài viết trên cổng thông tin).
PUBLIC_PREFIXES = ("cms/",)


def serve_media(request, path):
    if not request.user.is_authenticated:
        if not any(path.startswith(p) for p in PUBLIC_PREFIXES):
            raise Http404
    try:
        full = Path(safe_join(settings.MEDIA_ROOT, path))
    except Exception:
        raise Http404
    if not full.is_file():
        raise Http404

    ctype, _ = mimetypes.guess_type(posixpath.basename(path))
    resp = FileResponse(open(full, "rb"), content_type=ctype or "application/octet-stream")
    # Ảnh hiện trường và ảnh bìa nên xem trực tiếp; tệp khác nên tải về.
    if not (ctype or "").startswith("image/"):
        resp["Content-Disposition"] = f'attachment; filename="{posixpath.basename(path)}"'
    # Tệp tải lên không nên bị trình duyệt đoán kiểu dữ liệu khác.
    resp["X-Content-Type-Options"] = "nosniff"
    return resp
