"""Quy trình bản tin cảnh báo: dự thảo -> chờ phê duyệt -> phát hành -> cập nhật -> hết hiệu lực."""
from django.db import transaction
from django.db.models import Q
from django.utils import timezone

from accounts.models import User
from core.audit import write_log
from core.notify import notify, users_with_perm
from . import models as m


class AlertError(Exception):
    pass


def snapshot(alert):
    return {
        "code": alert.code, "title": alert.title, "pest": alert.pest.name, "crop": alert.crop.name,
        "divisions": [d.name for d in alert.divisions.all()], "risk": alert.get_risk_level_display(),
        "valid_from": alert.valid_from.isoformat(), "valid_to": alert.valid_to.isoformat(),
        "basis": alert.basis, "guidance": alert.guidance, "channels": alert.channels, "version": alert.version,
    }


def add_revision(alert, action, user, note=""):
    return m.AlertRevision.objects.create(alert=alert, action=action, version=alert.version,
                                          snapshot=snapshot(alert), note=note, user=user)


def recipients(alert):
    """Cán bộ thuộc địa bàn/đơn vị nhận bản tin."""
    div_ids = set()
    for d in alert.divisions.all():
        div_ids.update(d.descendant_ids())
    cond = Q(division_id__in=div_ids) | Q(division__isnull=True)
    unit_ids = list(alert.recipient_units.values_list("pk", flat=True))
    if unit_ids:
        cond |= Q(unit_id__in=unit_ids)
    return list(User.objects.filter(is_active=True).filter(cond))


@transaction.atomic
def transition(alert, action, user, note=""):
    flows = {
        "submit": ({"draft", "updated"}, "pending"),
        "approve": ({"pending"}, "published"),
        "return": ({"pending"}, "draft"),
        "expire": ({"published", "updated"}, "expired"),
        "reopen": ({"expired"}, "draft"),
    }
    allowed, to = flows[action]
    if alert.status not in allowed:
        raise AlertError("Trạng thái hiện tại của bản tin không cho phép thao tác này.")
    if action == "submit":
        if not alert.basis.strip() or not alert.guidance.strip():
            raise AlertError("Cần có căn cứ nhận định và hướng dẫn phòng trừ.")
        if not alert.divisions.exists():
            raise AlertError("Cần chọn phạm vi địa bàn.")
        if alert.forecast_id and alert.forecast.status != "confirmed":
            raise AlertError("Nhận định dự báo gắn với bản tin chưa được chuyên môn xác nhận.")
    if action == "return" and not note.strip():
        raise AlertError("Cần nhập lý do trả lại.")
    old = alert.status
    was_update = old == "pending" and alert.version > 1
    alert.status = to
    if note:
        alert.review_note = note
    if action == "approve":
        alert.approved_by, alert.published_at = user, timezone.now()
    alert.save()
    add_revision(alert, f"{action}", user, note)
    write_log(f"alert_{action}", alert, note=note, changes={"status": [old, to]}, user=user)
    url = f"/alerts/alerts/{alert.pk}/"
    if action == "submit":
        notify([u for u in users_with_perm("alert", "approve") if u != user],
               "Bản tin cảnh báo chờ phê duyệt", str(alert), url)
    elif action == "return" and alert.created_by:
        notify([alert.created_by], "Bản tin cảnh báo bị trả lại", note, url)
    elif action == "approve":
        _publish(alert, was_update)
    return alert


def _publish(alert, was_update=False):
    chans = alert.channels or []
    prefix = "[CẬP NHẬT] " if was_update else ""
    if "notify" in chans or not chans:
        notify(recipients(alert), f"{prefix}Cảnh báo: {alert.title}",
               f"Mức nguy cơ: {alert.get_risk_level_display()}. {alert.valid_from:%d/%m/%Y} - {alert.valid_to:%d/%m/%Y}",
               f"/alerts/alerts/{alert.pk}/")
    if "email" in chans:
        _send_email(alert, prefix)
    if "web" in chans:
        from cms.models import Post, PostRevision

        post, created = Post.objects.get_or_create(
            alert=alert, defaults=dict(title=alert.title, post_type="forecast", status="published",
                                       published_at=timezone.now(), author=alert.created_by,
                                       summary=f"Mức nguy cơ: {alert.get_risk_level_display()}",
                                       content=f"{alert.basis}\n\nHướng dẫn phòng trừ:\n{alert.guidance}"))
        if not created:
            post.title, post.content, post.status = alert.title, f"{alert.basis}\n\nHướng dẫn phòng trừ:\n{alert.guidance}", "published"
            post.version += 1
            post.published_at = timezone.now()
            post.save()
        PostRevision.objects.create(post=post, version=post.version, action="alert_publish", title=post.title,
                                    content=post.content, user=alert.approved_by)


def _send_email(alert, prefix=""):
    """Gửi bản tin cảnh báo qua email cho cán bộ thuộc địa bàn/đơn vị nhận.

    Không nuốt lỗi: ghi lại số email gửi được vào nhật ký kiểm toán để còn truy vết.
    Chỉ những người có địa chỉ email hợp lệ mới được gửi.
    """
    from django.conf import settings
    from django.core.mail import EmailMultiAlternatives

    from core.audit import write_log

    to = [u.email for u in recipients(alert) if u.email]
    if not to:
        return 0

    subject = f"{prefix}Cảnh báo sinh vật gây hại: {alert.title}"
    body = (
        f"BẢN TIN CẢNH BÁO SỐ {alert.code}\n"
        f"Đối tượng: {alert.pest.name}\n"
        f"Cây trồng: {alert.crop.name}\n"
        f"Mức nguy cơ: {alert.get_risk_level_display()}\n"
        f"Hiệu lực: {alert.valid_from:%d/%m/%Y} - {alert.valid_to:%d/%m/%Y}\n\n"
        f"CĂN CỨ NHẬN ĐỊNH\n{alert.basis}\n\n"
        f"HƯỚNG DẪN PHÒNG TRỪ\n{alert.guidance}\n"
    )

    sent = 0
    for addr in to:
        try:
            msg = EmailMultiAlternatives(subject, body, settings.DEFAULT_FROM_EMAIL, [addr])
            msg.send(fail_silently=False)
            sent += 1
        except Exception as exc:  # noqa: BLE001 - ghi log rồi tiếp tục với người kế tiếp
            write_log("alert_email_failed", alert, note=f"{addr}: {exc}"[:500], user=alert.approved_by)

    write_log("alert_email_sent", alert, note=f"Đã gửi {sent}/{len(to)} email", user=alert.approved_by)
    return sent


@transaction.atomic
def start_update(alert, user):
    """Điều chỉnh bản tin đã phát hành: tăng lần ban hành, đưa về chế độ chỉnh sửa, ghi lịch sử."""
    if alert.status != "published":
        raise AlertError("Chỉ điều chỉnh được bản tin đang phát hành.")
    add_revision(alert, "before_update", user, "Lưu bản ban hành trước khi điều chỉnh")
    alert.status, alert.version = "updated", alert.version + 1
    alert.save()
    write_log("alert_update_start", alert, user=user)


def expire_due():
    """Đưa các bản tin hết hạn về trạng thái hết hiệu lực. Trả về số bản tin đã chuyển."""
    qs = m.Alert.objects.filter(status__in=["published"], valid_to__lt=timezone.localdate())
    n = 0
    for a in qs:
        a.status = "expired"
        a.save()
        add_revision(a, "auto_expire", None, "Tự động hết hiệu lực")
        n += 1
    return n


def followup_summary(alert):
    qs = alert.followups.all()
    total = qs.count()
    done = qs.filter(status="done").count()
    from django.db.models import Avg, Sum

    agg = qs.filter(status="done").aggregate(area=Sum("area_treated"), rate=Avg("rate_after"))
    eff = {k: qs.filter(effectiveness=k).count() for k in ("good", "fair", "poor")}
    return {"total": total, "done": done, "pct": round(done * 100 / total) if total else 0,
            "area": agg["area"], "rate_after": agg["rate"], "eff": eff,
            "overdue": sum(1 for t in qs if t.overdue)}
