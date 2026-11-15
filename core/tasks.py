"""Hàng đợi tác vụ nền lưu trong database, không cần Celery hay Redis.

Cách dùng:
    @tasks.register("ten_tac_vu")
    def handler(**payload): ...

    tasks.enqueue("ten_tac_vu", alert_id=5)

Chế độ chạy (biến môi trường TASKS_MODE):
    thread  (mặc định) lưu tác vụ rồi chạy ngay trong một luồng nền sau khi giao dịch hoàn tất.
                       Yêu cầu của người dùng không phải chờ. Tác vụ lỗi hoặc bị gián đoạn
                       được chạy lại bởi `manage.py process_tasks` hoặc `run_schedules`.
    worker             chỉ lưu; một tiến trình `manage.py process_tasks --loop` xử lý.
    eager              chạy ngay trong chính yêu cầu (dùng cho test).
"""
import datetime as dt
import importlib
import logging
import threading

from django.conf import settings
from django.db import close_old_connections, transaction
from django.utils import timezone

from .models import BackgroundTask

logger = logging.getLogger(__name__)

HANDLERS = {}
# Các module khai báo tác vụ; nạp khi worker khởi động để HANDLERS đầy đủ.
HANDLER_MODULES = ["alerts.services"]
STALE_AFTER = dt.timedelta(minutes=10)
BACKOFF = [dt.timedelta(minutes=1), dt.timedelta(minutes=5), dt.timedelta(minutes=30)]


def register(name):
    def deco(fn):
        HANDLERS[name] = fn
        return fn

    return deco


def load_handlers():
    for mod in HANDLER_MODULES:
        importlib.import_module(mod)


def enqueue(name, **payload):
    task = BackgroundTask.objects.create(name=name, payload=payload)
    mode = getattr(settings, "TASKS_MODE", "thread")
    if mode == "eager":
        run_task(task.pk)
    elif mode == "thread":
        transaction.on_commit(lambda: threading.Thread(target=_run_in_thread, args=(task.pk,), daemon=True).start())
    return task


def _run_in_thread(task_id):
    try:
        run_task(task_id)
    finally:
        close_old_connections()


def run_task(task_id):
    """Chạy một tác vụ. Trả về True nếu hoàn tất. Tự khoá để hai tiến trình không chạy trùng."""
    claimed = BackgroundTask.objects.filter(pk=task_id, status="pending").update(
        status="running", run_after=timezone.now())
    if not claimed:
        return False
    task = BackgroundTask.objects.get(pk=task_id)
    task.attempts += 1
    handler = HANDLERS.get(task.name)
    try:
        if handler is None:
            load_handlers()
            handler = HANDLERS[task.name]
        handler(**task.payload)
    except Exception as exc:  # noqa: BLE001 - lưu lỗi để truy vết, thử lại theo lịch
        logger.exception("Tác vụ nền %s #%s lỗi", task.name, task.pk)
        task.last_error = f"{type(exc).__name__}: {exc}"[:1000]
        if task.attempts >= task.max_attempts:
            task.status, task.finished_at = "failed", timezone.now()
        else:
            task.status = "pending"
            task.run_after = timezone.now() + BACKOFF[min(task.attempts - 1, len(BACKOFF) - 1)]
        task.save()
        return False
    task.status, task.finished_at, task.last_error = "done", timezone.now(), ""
    task.save()
    return True


def run_pending(limit=100):
    """Chạy các tác vụ đến hạn; đưa tác vụ treo quá lâu ở trạng thái 'running' về hàng đợi."""
    now = timezone.now()
    BackgroundTask.objects.filter(status="running", run_after__lt=now - STALE_AFTER).update(status="pending")
    ids = list(BackgroundTask.objects.filter(status="pending", run_after__lte=now)
               .order_by("created_at").values_list("pk", flat=True)[:limit])
    return sum(1 for pk in ids if run_task(pk))
