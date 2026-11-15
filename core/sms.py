"""Gửi SMS qua eSMS.vn. Không có khoá API thì chỉ ghi ra log (chế độ thử).

Biến môi trường:
    ESMS_API_KEY, ESMS_SECRET_KEY   khoá lấy từ trang quản trị eSMS
    ESMS_SMS_TYPE                   loại tin theo tài khoản eSMS (mặc định 8)
    ESMS_BRANDNAME                  tên thương hiệu đã đăng ký (bắt buộc với loại tin brandname)
"""
import json
import logging
import re
import unicodedata
import urllib.request

from django.conf import settings

logger = logging.getLogger(__name__)

ESMS_URL = "https://rest.esms.vn/MainService.svc/json/SendMultipleMessage_V4_post_json/"
PHONE_RE = re.compile(r"^0\d{9}$")


def normalize_phone(raw):
    """Đưa số điện thoại Việt Nam về dạng 0xxxxxxxxx. Trả về None nếu không hợp lệ."""
    p = re.sub(r"[\s.\-()]", "", raw or "")
    if p.startswith("+84"):
        p = "0" + p[3:]
    elif p.startswith("84") and len(p) == 11:
        p = "0" + p[2:]
    return p if PHONE_RE.match(p) else None


def fold(text):
    """Bỏ dấu tiếng Việt: tin nhắn không Unicode rẻ hơn và máy nào cũng đọc được."""
    text = (text or "").replace("đ", "d").replace("Đ", "D")
    return "".join(c for c in unicodedata.normalize("NFD", text) if unicodedata.category(c) != "Mn")


def send_sms(phone, text):
    """Gửi một tin. Trả về True nếu nhà cung cấp nhận (hoặc đang ở chế độ thử)."""
    number = normalize_phone(phone)
    if not number:
        return False
    content = fold(text)[:160]
    key, secret = getattr(settings, "ESMS_API_KEY", ""), getattr(settings, "ESMS_SECRET_KEY", "")
    if not key or not secret:
        logger.info("SMS (chế độ thử, chưa có khoá eSMS) tới %s: %s", number, content)
        return True
    body = {"ApiKey": key, "SecretKey": secret, "Phone": number, "Content": content,
            "SmsType": getattr(settings, "ESMS_SMS_TYPE", "8"), "IsUnicode": "0"}
    brand = getattr(settings, "ESMS_BRANDNAME", "")
    if brand:
        body["Brandname"] = brand
    req = urllib.request.Request(ESMS_URL, data=json.dumps(body).encode(), method="POST",
                                 headers={"Content-Type": "application/json"})
    with urllib.request.urlopen(req, timeout=15) as resp:  # noqa: S310 - URL cố định, https
        result = json.loads(resp.read().decode() or "{}")
    if str(result.get("CodeResult")) != "100":
        logger.warning("eSMS từ chối tin gửi %s: %s", number, result)
        return False
    return True
