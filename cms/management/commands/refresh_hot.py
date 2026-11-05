"""Tính lại điểm tin nóng cho cổng thông tin.

Chạy tay:      python manage.py refresh_hot
Chạy định kỳ:  đặt lịch 15 phút một lần (Task Scheduler) để khối "Đang được quan tâm"
               phản ánh lượt xem mới mà không cần chờ người vào trang.
"""

from django.core.management.base import BaseCommand

from cms import insights
from cms.models import Post


class Command(BaseCommand):
    help = "Tính lại điểm tin nóng cho các bài đã đăng trên cổng thông tin."

    def add_arguments(self, parser):
        parser.add_argument("--top", type=int, default=10, help="Số bài in ra để kiểm tra.")

    def handle(self, *args, **options):
        changed = insights.refresh_hot_scores()
        self.stdout.write(self.style.SUCCESS(f"Đã chấm điểm {changed} bài viết."))

        top = Post.objects.filter(status="published").order_by("-hot_score")[: options["top"]]
        if not top:
            self.stdout.write("Chưa có bài viết nào được đăng.")
            return
        self.stdout.write("")
        for p in top:
            flag = "★" if p.is_featured else " "
            self.stdout.write(f"  {p.hot_score:6.2f} {flag} {p.get_post_type_display():<24} {p.title[:60]}")
