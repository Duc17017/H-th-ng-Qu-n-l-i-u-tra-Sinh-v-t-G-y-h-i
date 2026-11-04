"""Chạy các lịch tổng hợp/gửi báo cáo đến hạn. Đặt trong Task Scheduler / cron, ví dụ chạy mỗi giờ:
    python manage.py run_schedules
"""
import datetime as dt

from django.core.files.base import ContentFile
from django.core.mail import EmailMessage
from django.core.management.base import BaseCommand
from django.utils import timezone

from alerts.services import expire_due
from core.notify import notify
from reports import builders as b
from reports.models import GeneratedReport, ReportSchedule

INTERVAL = {"daily": dt.timedelta(days=1), "weekly": dt.timedelta(days=7), "monthly": dt.timedelta(days=30)}


class Command(BaseCommand):
    help = "Chạy lịch báo cáo đến hạn và cập nhật bản tin cảnh báo hết hiệu lực."

    def add_arguments(self, parser):
        parser.add_argument("--force", action="store_true", help="Chạy tất cả lịch đang bật, bỏ qua thời hạn")

    def handle(self, *args, **opts):
        expired = expire_due()
        self.stdout.write(f"Bản tin hết hiệu lực: {expired}")
        now = timezone.now()
        for sch in ReportSchedule.objects.filter(is_active=True, template__is_active=True).select_related("template"):
            if not opts["force"] and sch.last_run and now - sch.last_run < INTERVAL[sch.frequency]:
                continue
            d_to = timezone.localdate()
            d_from = d_to - dt.timedelta(days=sch.lookback_days)
            rep = b.build(sch.template.kind, d_from, d_to)
            content = b.to_xlsx(rep) if sch.fmt == "xlsx" else b.to_pdf(rep)
            fname = f"{sch.template.code}_{d_to:%Y%m%d}.{sch.fmt}"
            gr = GeneratedReport(schedule=sch, template=sch.template, title=rep["title"], period_from=d_from, period_to=d_to)
            gr.file.save(fname, ContentFile(content), save=True)
            users = list(sch.recipients.filter(is_active=True))
            notify(users, f"Báo cáo định kỳ: {rep['title']}", "Báo cáo đã được tổng hợp tự động.", "/reports/")
            if sch.send_email:
                emails = [u.email for u in users if u.email]
                if emails:
                    msg = EmailMessage(rep["title"], "Báo cáo định kỳ đính kèm.", to=emails)
                    msg.attach(fname, content)
                    msg.send(fail_silently=True)
            sch.last_run = now
            sch.save(update_fields=["last_run"])
            self.stdout.write(f"Đã chạy: {sch.name}")
