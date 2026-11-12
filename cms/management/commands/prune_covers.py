"""Dọn ảnh đại diện do kiểm thử ghi nhầm vào media/ thật.

Chỉ giữ lại ảnh khớp với slug của các bài viết đang có trong CSDL; phần còn lại
là rác từ những lần chạy test trước khi media được chuyển sang thư mục tạm.

    python manage.py prune_covers --dry-run
    python manage.py prune_covers
"""

from pathlib import Path

from django.conf import settings
from django.core.management.base import BaseCommand

from cms.models import Post


class Command(BaseCommand):
    help = "Xóa ảnh đại diện mồ côi trong media/ (không còn bài viết nào dùng)."

    def add_arguments(self, parser):
        parser.add_argument("--dry-run", action="store_true", help="Chỉ liệt kê, không xóa.")

    def handle(self, *args, **options):
        root = Path(settings.MEDIA_ROOT)
        used = {p.cover.name for p in Post.objects.exclude(cover="")}
        removed = freed = 0

        for path in sorted(root.rglob("*")):
            if not path.is_file():
                continue
            relative = path.relative_to(root).as_posix()
            if not relative.startswith("cms/"):
                continue          # không đụng vào tệp báo cáo hay tệp khác
            if relative in used:
                continue
            size = path.stat().st_size
            if options["dry_run"]:
                self.stdout.write(f"  sẽ xóa: {relative} ({size // 1024} KB)")
            else:
                path.unlink()
            removed += 1
            freed += size

        action = "Sẽ xóa" if options["dry_run"] else "Đã xóa"
        self.stdout.write(self.style.SUCCESS(
            f"{action} {removed} tệp, giải phóng {freed / 1024 / 1024:.1f} MB. "
            f"Đang dùng: {len(used)} ảnh."))
