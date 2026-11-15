"""Xử lý hàng đợi tác vụ nền.

Chạy một lần:      python manage.py process_tasks
Chạy thường trực:  python manage.py process_tasks --loop   (dùng khi TASKS_MODE=worker)
"""
import time

from django.core.management.base import BaseCommand

from core import tasks


class Command(BaseCommand):
    help = "Chạy các tác vụ nền đến hạn (email, SMS...)."

    def add_arguments(self, parser):
        parser.add_argument("--loop", action="store_true", help="Chạy liên tục, nghỉ giữa các lượt")
        parser.add_argument("--interval", type=int, default=10, help="Số giây nghỉ giữa các lượt (với --loop)")

    def handle(self, *args, **opts):
        tasks.load_handlers()
        while True:
            done = tasks.run_pending()
            if done:
                self.stdout.write(f"Đã chạy {done} tác vụ")
            if not opts["loop"]:
                break
            time.sleep(opts["interval"])
