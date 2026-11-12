"""Ghép nội dung thực tế vào cổng thông tin.

Tạo bộ bài viết chuyên ngành đầy đủ (tin tức, bản tin, dự tính dự báo, tình hình
sinh vật gây hại, khuyến cáo, hướng dẫn kỹ thuật), bản tin cảnh báo kèm nhiệm vụ
theo dõi và ảnh đại diện sinh tự động — để cổng thông tin có nội dung đọc được
ngay, không phải màn hình trống.

    python manage.py seed_content
    python manage.py seed_content --force        # ghi đè nội dung bài đã có
    python manage.py seed_content --no-cover     # không sinh ảnh đại diện

Chạy lại nhiều lần vẫn an toàn: mọi bản ghi đều định danh bằng slug/mã.
"""

from __future__ import annotations

import io
import random
from datetime import timedelta

from django.core.files.base import ContentFile
from django.core.management.base import BaseCommand
from django.db import transaction
from django.utils import timezone

# ─────────────────────────── ảnh đại diện sinh tự động ────────────────────────
# Mỗi loại bài có một bảng màu riêng để người đọc nhận ra loại tin từ xa.

COVER_PALETTE = {
    "news": ((22, 129, 62), (10, 48, 28)),
    "guide": ((0, 101, 44), (0, 40, 20)),
    "bulletin": ((150, 84, 0), (52, 28, 0)),
    "forecast": ((8, 92, 122), (4, 32, 48)),
    "situation": ((172, 24, 24), (74, 6, 10)),
    "advice": ((146, 78, 8), (58, 26, 0)),
    "notice": ((62, 74, 66), (24, 30, 26)),
}

_FONT_CANDIDATES = {
    True: [r"C:\Windows\Fonts\arialbd.ttf", r"C:\Windows\Fonts\segoeuib.ttf"],
    False: [r"C:\Windows\Fonts\arial.ttf", r"C:\Windows\Fonts\segoeui.ttf"],
}


def _font(size: int, bold: bool = False):
    from PIL import ImageFont

    for path in _FONT_CANDIDATES[bold]:
        try:
            return ImageFont.truetype(path, size)
        except OSError:
            continue
    return ImageFont.load_default()


def _wrap(draw, text: str, font, max_width: int, max_lines: int) -> list[str]:
    words, lines, current = text.split(), [], ""
    for word in words:
        trial = f"{current} {word}".strip()
        if draw.textlength(trial, font=font) <= max_width or not current:
            current = trial
        else:
            lines.append(current)
            current = word
            if len(lines) == max_lines:
                break
    if current and len(lines) < max_lines:
        lines.append(current)
    if not lines:
        return []
    # Còn chữ chưa đưa vào thì cắt bớt và thêm dấu lược
    consumed = sum(len(ln.split()) for ln in lines)
    if consumed < len(words) and lines:
        while lines[-1] and draw.textlength(lines[-1] + "…", font=font) > max_width:
            lines[-1] = " ".join(lines[-1].split()[:-1])
        lines[-1] = lines[-1] + "…"
    return lines


def render_cover(label: str, title: str, post_type: str, seed: int = 0) -> ContentFile:
    """Vẽ ảnh đại diện 1200×600: nền chuyển sắc, luống cày, nhãn loại bài, tiêu đề."""
    from PIL import Image, ImageDraw

    width, height = 1200, 600
    top, bottom = COVER_PALETTE.get(post_type, COVER_PALETTE["news"])

    # Nền: tạo gradient nhỏ rồi phóng to — nhanh và mượt hơn tô từng điểm ảnh.
    small = Image.new("RGB", (64, 40))
    sp = small.load()
    for y in range(40):
        for x in range(64):
            t = (x / 63) * 0.62 + (y / 39) * 0.38
            sp[x, y] = tuple(round(top[i] + (bottom[i] - top[i]) * t) for i in range(3))
    img = small.resize((width, height), Image.BICUBIC).convert("RGBA")

    overlay = Image.new("RGBA", (width, height), (255, 255, 255, 0))
    od = ImageDraw.Draw(overlay)

    # Luống cày chạy chéo, tạo cảm giác cánh đồng mà không cần ảnh thật.
    rnd = random.Random(seed)
    for i in range(9):
        base = -200 + i * 110 + rnd.randint(-12, 12)
        od.line([(base, height + 40), (base + 620, -40)], fill=(255, 255, 255, 16), width=rnd.choice([18, 26, 34]))

    # Khối tròn mờ góc phải, giữ chỗ cho phần chữ bên trái.
    od.ellipse([width - 300, -180, width + 220, 340], fill=(255, 255, 255, 18))
    od.ellipse([width - 210, height - 250, width + 120, height + 80], fill=(255, 255, 255, 12))
    img = Image.alpha_composite(img, overlay)

    draw = ImageDraw.Draw(img)
    pad = 72

    # Nhãn loại bài
    label_font = _font(24, bold=True)
    label_text = label.upper()
    lw = draw.textlength(label_text, font=label_font)
    draw.rounded_rectangle([pad, 78, pad + lw + 44, 78 + 46], radius=23, fill=(255, 255, 255, 38))
    draw.text((pad + 22, 78 + 11), label_text, font=label_font, fill=(255, 255, 255, 235))

    # Tiêu đề
    title_font = _font(54, bold=True)
    lines = _wrap(draw, title, title_font, width - pad * 2 - 60, 3)
    y = 168
    for line in lines:
        draw.text((pad, y), line, font=title_font, fill=(255, 255, 255, 248))
        y += 72

    # Chân ảnh
    foot_font = _font(22)
    draw.line([(pad, height - 116), (pad + 96, height - 116)], fill=(255, 255, 255, 130), width=4)
    draw.text((pad, height - 96), "AgriGov TT&BVTV · Cổng thông tin nông nghiệp",
              font=foot_font, fill=(255, 255, 255, 170))

    buf = io.BytesIO()
    img.convert("RGB").save(buf, format="JPEG", quality=84, optimize=True)
    return ContentFile(buf.getvalue())


# ─────────────────────────────── danh mục bổ sung ─────────────────────────────
# Dấu nhận biết bài do lệnh này tạo: dùng để biết bài còn nguyên bản hay đã được
# biên tập viên sửa tay (khi đó seeder không được ghi đè nội dung).
SEED_NOTE = "Nội dung do bộ dữ liệu mẫu khởi tạo."

CATEGORIES = [
    ("tin-tuc", "Tin tức - sự kiện", 0),
    ("ban-tin", "Bản tin chuyên ngành", 1),
    ("du-bao", "Dự tính, dự báo", 2),
    ("canh-bao", "Cảnh báo dịch hại", 3),
    ("huong-dan", "Hướng dẫn kỹ thuật", 4),
    ("chinh-sach", "Chính sách, văn bản", 5),
    ("thong-bao", "Thông báo", 6),
]

CROPS = [
    ("LUA", "Lúa", "Oryza sativa"),
    ("NGO", "Ngô", "Zea mays"),
    ("RAU", "Rau màu", ""),
    ("CAYCO-MUI", "Cây có múi", "Citrus spp."),
]

PESTS = [
    ("RNN", "Rầy nâu", "Nilaparvata lugens", "insect", ["LUA"],
     "Điều tra 7 ngày/lần, giữ mực nước nông, bón phân cân đối, chỉ phun khi mật độ vượt ngưỡng kinh tế."),
    ("DAO", "Bệnh đạo ôn", "Pyricularia oryzae", "disease", ["LUA"],
     "Không bón thừa đạm, giữ ẩm hợp lý, phun phòng khi thời tiết âm u ẩm cao hoặc khi thấy vết bệnh đầu tiên."),
    ("SAU", "Sâu keo mùa thu", "Spodoptera frugiperda", "insect", ["NGO"],
     "Thăm đồng 3–5 ngày/lần ở giai đoạn 3–6 lá, bắt sâu non bằng tay, phun khi mật độ vượt ngưỡng."),
    ("SCL", "Sâu cuốn lá nhỏ", "Cnaphalocrocis medinalis", "insect", ["LUA"],
     "Bảo vệ thiên địch, chỉ phun ở giai đoạn làm đòng–trổ khi tỷ lệ lá hại vượt ngưỡng."),
    ("VL", "Bệnh vàng lùn", "Rice grassy stunt virus", "disease", ["LUA"],
     "Không có thuốc chữa; phòng trừ bằng diệt rầy nâu môi giới và nhổ bỏ cây bệnh."),
    ("LXL", "Bệnh lùn xoắn lá", "Rice ragged stunt virus", "disease", ["LUA"],
     "Quản lý rầy nâu môi giới, tránh sạ dày, vệ sinh đồng ruộng sau thu hoạch."),
    ("GRE", "Bệnh vàng lá gân xanh (Greening)", "Candidatus Liberibacter asiaticus", "disease", ["CAYCO-MUI"],
     "Dùng giống sạch bệnh, quản lý rầy chổng cánh, chặt bỏ cây bệnh, không vận chuyển cành ghép không rõ nguồn."),
    ("BACLA", "Bệnh bạc lá lúa", "Xanthomonas oryzae pv. oryzae", "disease", ["LUA"],
     "Hạn chế bón đạm muộn, không để ruộng ngập sâu, phun khi vết bệnh xuất hiện sau mưa giông."),
]

STAGES = [
    ("LUA-MA", "Mạ - mới sạ", "LUA"),
    ("LUA-DN", "Đẻ nhánh", "LUA"),
    ("LUA-DL", "Làm đòng", "LUA"),
    ("LUA-NT", "Trổ bông - vào chắc", "LUA"),
    ("LUA-CHIN", "Chín - thu hoạch", "LUA"),
    ("NGO-3L", "3–6 lá", "NGO"),
    ("NGO-9L", "9–12 lá", "NGO"),
]

# ─────────────────────────────── bản tin cảnh báo ─────────────────────────────
ALERTS = [
    {
        "code": "CB-001",
        "title": "Cảnh báo rầy nâu hại lúa giai đoạn làm đòng",
        "pest": "RNN", "crop": "LUA", "risk_level": "high",
        "valid_from": -5, "valid_to": 9,
        "basis": (
            "Mật độ rầy nâu trung bình 4 tuần gần đây tăng liên tục, từ 750 con/m² lên 1.850 con/m², "
            "cá biệt 4.500 con/m² tại các điểm ven đê. Rầy ở pha trưởng thành và rầy cánh ngắn chiếm 62%. "
            "Thời tiết nhiệt độ 26–30°C, ẩm độ trên 85% rất thuận lợi cho rầy sinh sản. Lúa đang ở giai đoạn "
            "làm đòng đến trổ, mức thiệt hại tiềm năng cao nhất."
        ),
        "guidance": (
            "Tăng cường điều tra 3–5 ngày/lần, đặc biệt ruộng sạ dày, bón thừa đạm.\n"
            "Giữ mực nước ruộng 3–5 cm, không để ruộng khô hạn trong giai đoạn rầy cao điểm.\n"
            "Chỉ phun khi mật độ vượt 1.500 con/m² ở giai đoạn đẻ nhánh hoặc 2.000 con/m² ở giai đoạn làm đòng.\n"
            "Ưu tiên thuốc đặc hiệu rầy, phun vào sáng sớm hoặc chiều mát, tập trung vào gốc lúa.\n"
            "Không trộn nhiều loại thuốc, tuân thủ thời gian cách ly ít nhất 14 ngày trước thu hoạch."
        ),
    },
    {
        "code": "CB-002",
        "title": "Cảnh báo bệnh đạo ôn lá lúa trong điều kiện âm u, ẩm độ cao",
        "pest": "DAO", "crop": "LUA", "risk_level": "very_high",
        "valid_from": -2, "valid_to": 12,
        "basis": (
            "Bốn tuần qua có 9 ngày trời âm u, ẩm độ không khí trung bình 89%, sương mù kéo dài đến 9 giờ sáng. "
            "Các điểm điều tra đã ghi nhận vết bệnh hình thoi ở 5/12 điểm, tỷ lệ lá hại 3–8%, cao nhất 15%. "
            "Gió mùa đông bắc tràn về làm nhiệt độ giảm còn 20–24°C, đúng điều kiện bệnh đạo ôn phát triển mạnh. "
            "Các giống lúa nhiễm bệnh gieo cấy trên 60% diện tích cần theo dõi đặc biệt."
        ),
        "guidance": (
            "Tuyệt đối không bón thêm đạm, tăng kali và lân giúp cây cứng, tăng sức chống chịu.\n"
            "Không phun thuốc thành giọt lớn làm bệnh lan sang lá khác; dùng bình phun sương mịn.\n"
            "Phun phòng ngay khi thấy vết bệnh đầu tiên, nhắc lại sau 5–7 ngày nếu thời tiết vẫn âm u.\n"
            "Ưu tiên thuốc trừ nấm có một trong các hoạt chất: tricyclazole, isoprothiolane, "
            "propiconazole, azoxystrobin.\n"
            "Ngừng phun trước thu hoạch theo đúng thời gian cách ly ghi trên nhãn."
        ),
    },
    {
        "code": "CB-003",
        "title": "Cảnh báo sâu keo mùa thu gây hại ngô đông xuân",
        "pest": "SAU", "crop": "NGO", "risk_level": "medium",
        "valid_from": -8, "valid_to": 14,
        "basis": (
            "Sâu keo mùa thu đã xuất hiện trên ngô giai đoạn 3–6 lá tại 4 xã, mật độ 0,3–0,8 con/m², "
            "tỷ lệ cây hại 8–22%, cá biệt 35% ở ruộng gieo muộn. Bướm đã bắt đầu vũ hóa sau đợt rộ đầu, "
            "dự kiến lứa tiếp theo gây hại từ 7–10 ngày tới. Đây là giai đoạn cây ngô quyết định năng suất, "
            "sâu non tuổi 1–3 ăn lá non chưa vào loa kèn nên hiệu quả phòng trừ cao nhất."
        ),
        "guidance": (
            "Thăm đồng 3 ngày/lần, kiểm tra mặt dưới lá và loa kèn non vào sáng sớm.\n"
            "Bắt sâu non bằng tay ở ruộng nhỏ, ngắt bỏ ổ trứng trước khi sâu nở.\n"
            "Phun khi mật độ vượt 0,5 con/m² ở giai đoạn 3–6 lá, hướng vòi vào loa kèn.\n"
            "Luân canh hoạt chất để tránh kháng thuốc, ưu tiên chế phẩm sinh học Bacillus thuringiensis "
            "hoặc nấm xanh, nấm trắng ở ruộng mật độ thấp.\n"
            "Sau thu hoạch, cày vùi tàn dư cây ngô để cắt vòng đời sâu."
        ),
    },
    {
        "code": "CB-004",
        "title": "Cảnh báo bệnh vàng lá gân xanh trên cây có múi",
        "pest": "GRE", "crop": "CAYCO-MUI", "risk_level": "high",
        "valid_from": -12, "valid_to": 30,
        "basis": (
            "Bệnh vàng lá gân xanh (Greening, HLB) do vi khuẩn Candidatus Liberibacter asiaticus gây ra, "
            "lan truyền chủ yếu qua rầy chổng cánh và qua cành ghép, mắt ghép nhiễm bệnh. "
            "Khảo sát 6 vườn tại hai huyện cho thấy 3 vườn có cây biểu hiện vàng lá không đối xứng, "
            "gân còn xanh, quả nhỏ và méo, tỷ lệ cây bệnh 4–11%. Rầy chổng cánh xuất hiện với mật độ "
            "cao trên các vườn có chồi non. Bệnh không có thuốc chữa, chỉ phòng được."
        ),
        "guidance": (
            "Kiểm tra vườn 7–10 ngày/lần, chú ý chồi non là nơi rầy chổng cánh ưa cư trú.\n"
            "Chặt bỏ và tiêu hủy cây bệnh nặng, không giữ cây làm giống.\n"
            "Chỉ trồng cây giống từ cơ sở được chứng nhận sạch bệnh.\n"
            "Phun thuốc trừ rầy chổng cánh vào các đợt ra lộc non, không trừ sạch côn trùng có ích trong vườn.\n"
            "Bón phân cân đối, giữ đất tơi xốp và thoát nước tốt để hỗ trợ cây khỏe."
        ),
    },
]

# ────────────────────────────────── bài viết ──────────────────────────────────

ARTICLES: list[dict] = [
    # ── Chính sách, văn bản ───────────────────────────────────────────────────
    {
        "slug": "huong-dan-thi-hanh-luat-bao-ve-va-kiem-dich-thuc-vat",
        "title": "Hướng dẫn thi hành Luật Bảo vệ và kiểm dịch thực vật tại địa phương",
        "type": "notice",
        "category": "chinh-sach",
        "days_ago": 14,
        "views": 1130,
        "featured": False,
        "summary": (
            "Tóm tắt các nội dung trọng tâm của Luật Bảo vệ và kiểm dịch thực vật và văn bản hướng dẫn "
            "thi hành, tập trung vào trách nhiệm của tổ chức, cá nhân và quy trình xử lý sinh vật gây hại."
        ),
        "content": """## Phạm vi điều chỉnh

Luật Bảo vệ và kiểm dịch thực vật điều chỉnh hoạt động phòng, chống sinh vật gây hại thực vật; kiểm
dịch thực vật; quản lý thuốc bảo vệ thực vật; và trách nhiệm của cơ quan, tổ chức, cá nhân có liên quan.

## Nguyên tắc cơ bản

1. Phòng là chính, phát hiện sớm và xử lý kịp thời khi sinh vật gây hại mới xuất hiện.
2. Ưu tiên biện pháp sinh học, canh tác, vật lý và cơ giới; hạn chế tối đa thuốc hóa học.
3. Bảo đảm an toàn thực phẩm, an toàn sức khỏe con người và môi trường sinh thái.
4. Xử lý kịp thời, đúng thẩm quyền và công khai thông tin cho cộng đồng.

## Trách nhiệm của nông dân, hộ sản xuất

| Nội dung | Trách nhiệm |
|---|---|
| Điều tra, phát hiện | Báo ngay cho chính quyền cấp xã khi nghi ngờ có dịch mới |
| Phòng trừ | Thực hiện theo hướng dẫn của cán bộ chuyên môn, không tự ý mở rộng |
| Thuốc BVTV | Chỉ dùng thuốc trong danh mục được phép, đúng liều và đúng thời gian cách ly |
| Bao bì | Thu gom và xử lý theo quy định, không vứt ra môi trường |
| Khai báo sản phẩm | Bảo đảm an toàn khi đưa nông sản ra thị trường |

## Trách nhiệm của đơn vị chuyên môn

- Tổ chức điều tra, phát hiện và dự báo sinh vật gây hại.
- Hướng dẫn, tập huấn kỹ thuật và phổ biến pháp luật cho nông dân.
- Phối hợp xử lý ổ dịch, khoanh vùng và tiêu hủy theo quy định.
- báo cáo định kỳ và đột xuất với cơ quan cấp trên.

## Xử lý khi phát hiện sinh vật gây hại mới

> Sinh vật gây hại mới là sinh vật lần đầu xuất hiện trên lãnh thổ Việt Nam, có nguy cơ lây lan nhanh
> và gây thiệt hại lớn. Người phát hiện phải báo ngay, tuyệt đối không tự ý tiêu hủy hoặc vận chuyển
> ra khỏi khu vực.

Quy trình gồm bốn bước: phát hiện và báo cáo → lấy mẫu giám định → khoanh vùng phòng trừ → đánh giá và
công bố hết dịch. Mỗi bước đều có yêu cầu cụ thể về thời hạn báo cáo và thẩm quyền quyết định.

## Lưu ý khi áp dụng

Nội dung trên chỉ là tóm tắt phục vụ phổ biến, không thay thế văn bản quy phạm pháp luật. Khi áp dụng
cần đối chiếu văn bản gốc và các văn bản sửa đổi, bổ sung còn hiệu lực.""",
        "cover_label": "Chính sách, văn bản",
    },
    {
        "slug": "quy-dinh-quan-ly-thuoc-bao-ve-thuc-vat",
        "title": "Quy định quản lý và sử dụng thuốc bảo vệ thực vật: những điểm người sản xuất cần nắm",
        "type": "notice",
        "category": "chinh-sach",
        "days_ago": 19,
        "views": 890,
        "featured": False,
        "summary": (
            "Thuốc bảo vệ thực vật chỉ được sử dụng khi có đủ điều kiện: thuốc trong danh mục được phép, "
            "người dùng tập huấn, tuân thủ thời gian cách ly và bảo hộ lao động. Vi phạm có thể bị xử phạt."
        ),
        "content": """## Danh mục thuốc được phép sử dụng

Bộ Nông nghiệp và Phát triển nông thôn ban hành và cập nhật định kỳ danh mục thuốc bảo vệ thực vật được
phép sử dụng và danh mục thuốc cấm sử dụng tại Việt Nam. Chỉ được dùng thuốc có trong danh mục được
phép, còn hạn sử dụng và có nhãn hợp pháp.

## Điều kiện của người sử dụng

Người trực tiếp sử dụng thuốc bảo vệ thực vật phải được tập huấn và cấp chứng chỉ hành nghề theo quy
định. Hộ gia đình sử dụng thuốc cho sản xuất của mình cần được hướng dẫn về bảo hộ lao động và an toàn
thực phẩm.

| Trách nhiệm | Nội dung |
|---|---|
| Bảo hộ lao động | Mũ, khẩu trang, găng tay, kính, quần áo dài tay, ủng |
| Pha chế | Đúng nồng độ trên nhãn, dùng dụng cụ chia vạch |
| Lưu trữ | Nơi kho khóa, xa trẻ em, xa nguồn nước và thức ăn |
| Bao bì | Thu gom về điểm tập kết, không đốt hoặc vứt xuống mương |
| Thời gian cách ly | Tuyệt đối tuân thủ trước khi thu hoạch |

## Sản xuất, buôn bán thuốc bảo vệ thực vật

Cơ sở sản xuất và cửa hàng buôn bán thuốc bảo vệ thực vật phải có giấy chứng nhận đủ điều kiện hoạt động,
có người có chứng chỉ hành nghề và lưu giữ hồ sơ theo dõi xuất nhập hàng. Cơ sở vi phạm có thể bị đình
chỉ hoạt động và thu hồi giấy chứng nhận.

## Xử lý vi phạm

Các hành vi thường bị xử phạt gồm: bán thuốc ngoài danh mục hoặc thuốc cấm; bán thuốc không rõ nguồn
gốc, hết hạn; quảng cáo sai công dụng; không hướng dẫn bảo hộ cho người mua; bán thuốc cho người chưa
đủ điều kiện sử dụng.

> Mức xử phạt có thể lên tới hàng chục triệu đồng, kèm tịch thu tang vật. Ngoài xử phạt hành chính,
> cơ sở vi phạm còn có thể bị thu hồi giấy phép và bồi thường thiệt hại do thuốc gây ra.

## Khuyến nghị cho nông dân

1. Mua thuốc tại cửa hàng có giấy phép, giữ hóa đơn để đối chiếu khi cần.
2. Đọc kỹ nhãn trước khi dùng, đặc biệt phần cảnh báo và thời gian cách ly.
3. Không pha trộn nhiều loại thuốc khi chưa được hướng dẫn.
4. Không dùng thuốc cấm, không dùng thuốc của cây trồng khác cho rau ăn lá.
5. Ghi lại nhật ký phun thuốc làm căn cứ truy xuất nguồn gốc.

## Lưu ý khi áp dụng

Nội dung trên chỉ là tài liệu tuyên truyền, không thay thế văn bản quy phạm pháp luật hiện hành. Đề nghị
đối chiếu văn bản gốc và tham vấn cơ quan chuyên môn khi cần.""",
        "cover_label": "Chính sách, văn bản",
    },
    # ── Tình hình sinh vật gây hại ────────────────────────────────────────────
    {
        "slug": "tinh-hinh-ray-nau-tuan-thu-44",
        "title": "Tình hình rầy nâu hại lúa tuần thứ 44: mật độ tăng nhanh ở các huyện ven đê",
        "type": "situation",
        "category": "canh-bao",
        "days_ago": 1,
        "views": 1864,
        "featured": True,
        "alert": "CB-001",
        "summary": (
            "Qua điều tra 12 điểm cố định, mật độ rầy nâu trung bình đạt 1.850 con/m², tăng 46% so với tuần "
            "trước và gấp 2,4 lần cùng kỳ năm ngoái. Diện tích nhiễm đã lên 1.240 ha, trong đó 86 ha ở mức "
            "nặng — tập trung tại các xã ven đê có ruộng sạ dày, bón thừa đạm."
        ),
        "content": """## Kết quả điều tra 12 điểm cố định

Tuần thứ 44, các Trạm Trồng trọt và BVTV thực hiện điều tra 12 điểm cố định trên 4 xã theo phương pháp
khay đập 5 điểm chéo góc. Kết quả như sau:

| Chỉ tiêu | Tuần 42 | Tuần 43 | Tuần 44 | So tuần trước |
|---|---|---|---|---|
| Mật độ trung bình (con/m²) | 1.120 | 1.270 | 1.850 | +46% |
| Mật độ cao nhất (con/m²) | 2.800 | 3.200 | 4.500 | +41% |
| Tỷ lệ hại trung bình (%) | 8,4 | 9,6 | 14,2 | +48% |
| Rầy cánh ngắn (%) | 38 | 51 | 62 | +11 |
| Diện tích nhiễm (ha) | 780 | 940 | 1.240 | +32% |

## Diễn biến cần lưu ý

Rầy nâu tập trung chủ yếu ở giai đoạn rầy non tuổi 2–5, chiếm 58% tổng số cá thể thu được. Tỷ lệ rầy
cánh ngắn tăng từ 38% lên 62% là dấu hiệu rầy đã ổn định quần thể và sắp bùng phát thành dịch, vì rầy
cánh ngắn có sức sinh sản cao gấp 3–4 lần rầy cánh dài.

Các xã có mật độ vượt ngưỡng đáng lo nhất:

- **Xã A1**: 4.500 con/m², ruộng sạ dày 180 kg/ha, bón đạm muộn lần hai.
- **Xã B2**: 3.100 con/m², ruộng ven đê thoát nước kém, mực nước 10–15 cm.
- **Xã A2**: 2.400 con/m², giống nhiễm rầy chiếm 80% diện tích.

## Mức độ gây hại

Diện tích nhiễm 1.240 ha được phân loại theo Quy chuẩn kỹ thuật quốc gia về phương pháp điều tra:

| Mức độ | Tỷ lệ hại | Diện tích (ha) | Ghi chú |
|---|---|---|---|
| Nhẹ | Dưới 10% | 890 | Rải rác, chưa cần phun |
| Trung bình | 10–30% | 264 | Cần theo dõi 3 ngày/lần |
| Nặng | 30–50% | 86 | Phải phòng trừ ngay |

## Nguyên nhân mật độ tăng

> Thời tiết 4 tuần gần đây nhiệt độ 26–30°C, ẩm độ luôn trên 85%, có mưa giông chiều tối đúng điều kiện
> rầy nâu sinh sản mạnh nhất.

Thêm vào đó, ba yếu tố kỹ thuật làm rầy phát triển nhanh hơn bình thường:

1. Gieo sạ dày trên 150 kg/ha ở 70% diện tích, tạo tán lá rậm, ẩm độ trong ruộng cao.
2. Bón thừa đạm và bón muộn, cây lúa mềm, giàu đạm — thức ăn ưa thích của rầy.
3. Phun thuốc trừ sâu phổ rộng không đúng lúc đã tiêu diệt thiên địch, làm mất cân bằng sinh thái.

## Khuyến nghị cho các Trạm

- Điều tra lại toàn bộ điểm cố định trong 48 giờ tới, bổ sung điểm tại ruộng sạ dày.
- Đối chiếu mật độ với ngưỡng kinh tế trước khi đề xuất phun, tránh phun tràn lan.
- Báo cáo số liệu về Chi cục qua phân hệ Điều tra để chạy lại mô hình dự báo.
- Kiểm tra chéo ít nhất 10% số phiếu để bảo đảm chất lượng dữ liệu trước khi xác nhận.""",
        "cover_label": "Tình hình sinh vật gây hại",
    },
    {
        "slug": "dien-bien-sau-keo-mua-thu-tren-ngo-dong-xuan",
        "title": "Diễn biến sâu keo mùa thu trên ngô: đã có 4 xã ghi nhận, mật độ có chiều hướng tăng",
        "type": "situation",
        "category": "canh-bao",
        "days_ago": 4,
        "views": 967,
        "featured": False,
        "alert": "CB-003",
        "summary": (
            "Sâu keo mùa thu xuất hiện tại 4 xã trên ngô giai đoạn 3–6 lá với mật độ 0,3–0,8 con/m², "
            "tỷ lệ cây hại 8–22%. Bướm đã vũ hóa sau đợt rộ đầu, lứa tiếp theo dự kiến gây hại từ 7–10 ngày tới."
        ),
        "content": """## Phạm vi và mật độ

Điều tra 8 điểm trên diện tích ngô đông xuân giai đoạn 3–6 lá cho thấy sâu keo mùa thu đã có mặt tại
4/6 xã. Mật độ trung bình 0,3–0,8 con/m², cá biệt ruộng gieo muộn tại xã B1 lên tới 1,4 con/m².

| Xã | Diện tích ngô (ha) | Mật độ (con/m²) | Tỷ lệ cây hại (%) | Giai đoạn ngô |
|---|---|---|---|---|
| A1 | 62 | 0,8 | 22 | 3–6 lá |
| A2 | 48 | 0,5 | 14 | 3–6 lá |
| B1 | 35 | 1,4 | 35 | 3 lá |
| B2 | 40 | 0,3 | 8 | 6 lá |

## Đặc điểm gây hại cần nhận biết

Sâu non tuổi 1–3 ăn biểu bì lá non, để lại lớp màng trắng. Từ tuổi 4 trở đi sâu ăn thủng lá, đục vào
loa kèn non và có thể cắn đứt điểm sinh trưởng khiến cây ngô chết hẳn — đây là kiểu gây hại nguy hiểm
nhất vì cây không phục hồi được.

Phân sâu keo mùa thu có dạng hạt đặc trưng, màu vàng nâu, tập trung thành đám trong loa kèn. Người điều
tra có thể phát hiện nhanh qua phân sâu mà không cần thấy sâu.

## Dự kiến lứa tới

Bướm đã vũ hóa sau đợt rộ đầu; với nhiệt độ 24–28°C, vòng đời sâu keo khoảng 30–36 ngày. Trứng nở sau
2–4 ngày, sâu non gây hại mạnh nhất ở tuổi 4–6 tức khoảng 7–10 ngày sau khi bướm đẻ. Đây là cửa sổ
phòng trừ hiệu quả nhất.

## Việc cần làm ngay

1. Thăm đồng 3 ngày/lần, quan sát mặt dưới lá và loa kèn non vào sáng sớm.
2. Ngắt bỏ ổ trứng và bắt sâu non bằng tay ở diện tích dưới 0,5 ha.
3. Chuẩn bị thuốc theo danh mục được phép sử dụng, ưu tiên chế phẩm sinh học ở ruộng mật độ thấp.
4. Không phun tràn lan khi mật độ dưới ngưỡng 0,5 con/m².""",
        "cover_label": "Tình hình sinh vật gây hại",
    },
    # ── Dự tính, dự báo ──────────────────────────────────────────────────────
    {
        "slug": "du-bao-ray-nau-hai-tuan-toi",
        "title": "Dự báo rầy nâu hai tuần tới: nguy cơ cao trên diện rộng, cần phòng trừ sớm",
        "type": "forecast",
        "category": "du-bao",
        "days_ago": 0,
        "views": 2410,
        "featured": True,
        "alert": "CB-001",
        "summary": (
            "Trên cơ sở dữ liệu điều tra 4 tuần liên tiếp và điều kiện thời tiết dự báo, rầy nâu có khả năng "
            "duy trì mức nguy cơ cao, tỷ lệ hại dự kiến 25–32% trên 1.500 ha lúa giai đoạn làm đòng đến trổ."
        ),
        "content": """## Nội dung nhận định

Theo phân tích dữ liệu điều tra và thời tiết, rầy nâu tiếp tục gia tăng trong hai tuần tới trên địa bàn
toàn tỉnh. Mức độ nguy cơ được đánh giá là **cao**, dự kiến tỷ lệ hại trung bình 25–32%, cục bộ có thể
vượt 50% nếu không phòng trừ kịp thời.

| Nội dung | Dự báo 2 tuần tới |
|---|---|
| Sinh vật gây hại | Rầy nâu (Nilaparvata lugens) |
| Cây trồng, giai đoạn | Lúa, làm đòng đến trổ |
| Phạm vi | Toàn tỉnh, trọng tâm các huyện ven đê |
| Mức độ nguy cơ | Cao |
| Tỷ lệ hại dự kiến | 25–32%, cục bộ trên 50% |
| Diện tích ảnh hưởng dự kiến | 1.500 ha |

## Căn cứ nhận định

1. Mật độ rầy nâu tăng liên tiếp 4 tuần, từ 750 lên 1.850 con/m², chưa có dấu hiệu chững lại.
2. Tỷ lệ rầy cánh ngắn tăng lên 62% — quần thể đã ổn định và có sức sinh sản cao.
3. Nhiệt độ dự báo 26–30°C, ẩm độ trên 85%, có mưa giông chiều tối: đúng điều kiện tối ưu của rầy.
4. Diện tích lúa giai đoạn làm đòng đến trổ chiếm 68% — giai đoạn mẫn cảm nhất với rầy nâu.
5. Chưa ghi nhận đợt thiên địch bùng phát đủ để khống chế rầy tự nhiên.

## Ý nghĩa với công tác chỉ đạo

> Dự báo này là cơ sở để ban hành bản tin cảnh báo và phân công nhiệm vụ kiểm tra thực địa.
> Kết luận chuyên môn cuối cùng vẫn thuộc cơ quan có thẩm quyền sau khi đối chiếu thực tế.

Nếu mật độ điều tra tuần tới vượt 2.500 con/m², cần nâng mức cảnh báo và mở rộng phạm vi phòng trừ.
Ngược lại, nếu xuất hiện mưa lớn kéo dài làm rầy bị rửa trôi, có thể hạ mức nguy cơ xuống trung bình.

## Khuyến nghị

- Duy trì điều tra 3–5 ngày/lần trên toàn bộ điểm cố định.
- Rà soát ngưỡng kinh tế theo giai đoạn sinh trưởng trước khi quyết định phun.
- Chuẩn bị vật tư thuốc đặc hiệu rầy tại các Trạm, không khuyến khích nông dân tự ý phun tràn lan.
- Tổ chức tuyên truyền trên hệ thống truyền thanh xã về dấu hiệu nhận biết cháy rầy.""",
        "cover_label": "Dự tính, dự báo",
    },
    {
        "slug": "du-tinh-du-bao-sinh-vat-hai-vu-dong-xuan",
        "title": "Dự tính, dự báo sinh vật gây hại cây trồng vụ Đông Xuân 2026",
        "type": "forecast",
        "category": "du-bao",
        "days_ago": 9,
        "views": 1502,
        "featured": False,
        "summary": (
            "Dự báo tổng thể vụ Đông Xuân: rầy nâu và bệnh đạo ôn ở mức cao trên lúa, sâu keo mùa thu "
            "hại ngô ở mức trung bình, bệnh vàng lá gân xanh trên cây có múi tiếp tục lan rộng ở vùng chuyên canh."
        ),
        "content": """## Bối cảnh vụ Đông Xuân

Vụ Đông Xuân 2026 dự kiến gieo cấy 28.500 ha lúa, 4.200 ha ngô và 1.800 ha rau màu. Đây là vụ có điều
kiện nhiệt độ thấp, ẩm độ cao đầu vụ và mưa phùn cuối vụ — môi trường thuận lợi cho nhóm bệnh nấm và
vi khuẩn phát triển.

## Dự báo theo cây trồng

| Cây trồng | Sinh vật gây hại | Mức nguy cơ | Giai đoạn rủi ro cao |
|---|---|---|---|
| Lúa | Rầy nâu | Cao | Đẻ nhánh muộn – làm đòng |
| Lúa | Bệnh đạo ôn lá | Rất cao | Đẻ nhánh – làm đòng |
| Lúa | Bệnh bạc lá vi khuẩn | Trung bình | Sau mưa giông, trổ bông |
| Lúa | Sâu cuốn lá nhỏ | Trung bình | Làm đòng – trổ |
| Ngô | Sâu keo mùa thu | Trung bình | 3–6 lá |
| Rau màu | Sâu tơ, bọ nhảy | Trung bình | Cây con – phân cành |
| Cây có múi | Vàng lá gân xanh | Cao | Ra lộc non |

## Nhóm bệnh cần đặc biệt chú ý

**Bệnh đạo ôn** là rủi ro số một của vụ Đông Xuân, vì giai đoạn đẻ nhánh đến làm đòng trùng với thời
kỳ âm u, sương mù nhiều, nhiệt độ 20–24°C. Bệnh có thể bùng phát rất nhanh, chỉ 5–7 ngày đã lây lan
toàn ruộng nếu không phát hiện kịp.

**Bệnh bạc lá vi khuẩn** thường xuất hiện sau mưa giông kèm gió mạnh làm lá bị tổn thương — đây là
đường xâm nhập của vi khuẩn. Ruộng bón thừa đạm hoặc để ngập sâu có nguy cơ cao hơn.

## Biện pháp chủ động

1. Bố trí cơ cấu giống hợp lý, không dùng một giống duy nhất trên diện rộng.
2. Xuống giống tập trung, né giai đoạn mẫn cảm khỏi đỉnh cao dịch hại.
3. Vệ sinh đồng ruộng, cày vùi tàn dư sau thu hoạch để cắt nguồn bệnh.
4. Tổ chức điều tra định kỳ ngay từ đầu vụ, không chờ đến khi thấy dịch.
5. Chuẩn bị kế hoạch phòng trừ theo từng mức nguy cơ, tránh mua thuốc tràn lan.""",
        "cover_label": "Dự tính, dự báo",
    },
    # ── Khuyến cáo phòng trừ ──────────────────────────────────────────────────
    {
        "slug": "khuyen-cao-phong-tru-ray-nau-lam-dong",
        "title": "Khuyến cáo phòng trừ rầy nâu giai đoạn làm đòng: phun đúng lúc, đúng chỗ",
        "type": "advice",
        "category": "canh-bao",
        "days_ago": 2,
        "views": 3120,
        "featured": True,
        "alert": "CB-001",
        "summary": (
            "Rầy nâu ở giai đoạn làm đòng có thể gây cháy rầy làm mất trắng năng suất chỉ trong 7–10 ngày. "
            "Khuyến cáo tập trung vào ngưỡng kinh tế theo giai đoạn sinh trưởng, kỹ thuật phun vào gốc "
            "và bảo vệ thiên địch thay vì phun tràn lan."
        ),
        "content": """## Vì sao giai đoạn làm đòng là giai đoạn quyết định

Từ làm đòng đến trổ, cây lúa dồn toàn bộ dinh dưỡng vào bông. Rầy nâu chích hút nhựa ở phần gốc thân,
lấy đi lượng đạm và đường mà bông cần. Khi mật độ vượt ngưỡng, cây khô từ gốc lên, cả khóm lúa đổ rạp
và chuyển màu vàng nâu — hiện tượng nông dân gọi là **cháy rầy**. Ruộng bị cháy rầy ở giai đoạn này
thường mất 50–100% năng suất, không có biện pháp cứu.

## Ngưỡng kinh tế theo giai đoạn

| Giai đoạn lúa | Ngưỡng phun (con/m²) | Ghi chú |
|---|---|---|
| Mạ - mới sạ | 3.000 | Rầy cánh dài, chưa ổn định quần thể |
| Đẻ nhánh | 1.500 | Bắt đầu có rầy cánh ngắn |
| Làm đòng | 2.000 | Giai đoạn mẫn cảm, không chờ thêm |
| Trổ - vào chắc | 2.000 | Phun phải bảo đảm thời gian cách ly |

Quy tắc quan trọng: **điều tra trước khi phun, và chỉ phun khi vượt ngưỡng**. Phun theo lịch cố định
là nguyên nhân chính gây bùng phát rầy ở vụ sau do tiêu diệt thiên địch.

## Kỹ thuật phun đúng

1. Chọn thời điểm sáng sớm (6–8 giờ) hoặc chiều mát (16–18 giờ), không phun khi trời nắng gắt.
2. Hạ vòi phun thấp, hướng vào gốc lúa — nơi rầy cư trú, khoảng 15–20 cm trên mặt nước.
3. Lượng nước phun 400–500 lít/ha, không phun quá loãng vì thuốc không tới gốc.
4. Trước khi phun, rút nước ruộng còn 3–5 cm để thuốc tập trung ở vùng gốc.
5. Không trộn quá 2 loại thuốc; kiểm tra kỹ nhãn về thời gian cách ly.

## Bảo vệ thiên địch

Nhện lùn, bọ rùa 6 chấm đốm, bọ xít mù xanh và ong ký sinh trứng rầy là những thiên địch quan trọng
nhất trên ruộng lúa. Chúng có thể giữ rầy dưới ngưỡng gây hại nếu không bị thuốc phổ rộng tiêu diệt.

- Không phun thuốc phổ rộng trừ sâu khi mật độ rầy còn thấp.
- Duy trì bờ ruộng có cỏ hoa để thiên địch có nơi trú ngụ.
- Nếu đã phun thuốc trừ rầy, không phun thêm thuốc trừ sâu khác cùng lúc.

## Dấu hiệu phải xử lý ngay

> Thấy rầy bu đầy gốc lúa khi lay nhẹ khóm, hoặc từ 5–7 con rầy trưởng thành trên một khóm — đó là
> lúc quần thể đã vượt xa ngưỡng, cần xử lý trong 24 giờ.

Sau khi phun, kiểm tra lại sau 3 ngày. Nếu mật độ vẫn trên 1.000 con/m² cần phun nhắc lại bằng thuốc
khác nhóm hoạt chất để tránh kháng thuốc. Không phun quá 2 lần liên tiếp cùng một hoạt chất.""",
        "cover_label": "Khuyến cáo phòng trừ",
    },
    {
        "slug": "nguyen-tac-4-dung-su-dung-thuoc-bvtv",
        "title": "Nguyên tắc 4 đúng khi sử dụng thuốc bảo vệ thực vật: đúng thuốc, đúng liều, đúng lúc, đúng cách",
        "type": "advice",
        "category": "huong-dan",
        "days_ago": 6,
        "views": 2870,
        "featured": False,
        "summary": (
            "Bốn sai lầm phổ biến nhất khi phun thuốc là tăng liều, phun khi chưa có dịch, phun sai thời điểm "
            "và không bảo hộ lao động. Bốn đúng giúp giảm chi phí, tăng hiệu quả và bảo đảm an toàn nông sản."
        ),
        "content": """## Đúng thuốc

Chọn thuốc theo đúng đối tượng gây hại, không theo thói quen hay quảng cáo. Rầy nâu là côn trùng
chích hút phải dùng thuốc lưu dẫn nội hấp hoặc tiếp xúc đặc hiệu rầy, không dùng thuốc trừ sâu ăn lá.
Bệnh nấm phải dùng thuốc trừ nấm, không dùng thuốc trừ khuẩn.

Chỉ dùng thuốc có trong **Danh mục thuốc bảo vệ thực vật được phép sử dụng tại Việt Nam** hiện hành và
còn hạn sử dụng. Không mua thuốc không nhãn, không rõ nguồn gốc.

## Đúng liều lượng, nồng độ

Tăng liều không làm hiệu quả cao hơn mà làm tăng chi phí, tăng tồn dư và đẩy nhanh quá trình kháng
thuốc của dịch hại. Luôn đọc nhãn, đong bằng dụng cụ chuẩn có chia vạch.

| Sai lầm phổ biến | Hệ quả |
|---|---|
| Tăng 1,5–2 lần liều khuyến cáo | Dịch hại kháng thuốc nhanh, chi phí tăng, tồn dư vượt ngưỡng |
| Pha loãng hơn để "phun cho đều" | Không đủ nồng độ diệt dịch hại, lãng phí |
| Trộn 3–4 loại thuốc cùng lúc | Kết tủa, giảm hiệu lực, ngộ độc cây trồng |

## Đúng thời điểm

Nguyên tắc chuẩn là **phun khi dịch hại vượt ngưỡng kinh tế**, ở giai đoạn sâu non tuổi nhỏ hoặc khi
bệnh mới xuất hiện. Với nấm bệnh, phun phòng trước khi thời tiết chuyển xấu hiệu quả hơn phun chữa
khi bệnh đã lan.

Không phun buổi trưa nắng nóng, không phun khi trời sắp mưa trong 4 giờ tới, không phun khi có gió
mạnh trên cấp 3 vì thuốc bay sang ruộng khác và người xung quanh.

## Đúng cách, đúng kỹ thuật

1. Hiệu chỉnh bình phun trước khi dùng, kiểm tra đầu vòi không tắc, không rò rỉ.
2. Phun đúng vị trí dịch hại: rầy ở gốc, sâu cuốn lá ở mặt trên lá, nấm đạo ôn ở mặt lá.
3. Đi ngược chiều gió để thuốc không bay vào người.
4. Không ăn uống, hút thuốc trong khi phun; rửa tay bằng xà phòng sau khi phun.
5. Thu gom bao bì thuốc về nơi quy định, tuyệt đối không vứt xuống kênh mương.

## Thời gian cách ly

Thời gian cách ly là số ngày tối thiểu từ lần phun cuối đến thu hoạch, ghi rõ trên nhãn thuốc. Đây là
yêu cầu bắt buộc để nông sản không vượt ngưỡng tồn dư tối đa cho phép.

> Bán nông sản trước thời gian cách ly có thể khiến lô hàng bị từ chối tại cửa khẩu hoặc bị thu hồi
> trong nước — thiệt hại lớn hơn rất nhiều so với việc chờ thêm vài ngày.

## Bảo hộ lao động tối thiểu

Mũ che, khẩu trang than hoạt tính, kính bảo hộ, găng tay chống thấm, quần áo dài tay và ủng. Không mặc
quần đùi, áo may ô khi phun thuốc — đây là nguyên nhân hàng đầu gây ngộ độc thuốc BVTV.""",
        "cover_label": "Khuyến cáo phòng trừ",
    },
    # ── Hướng dẫn kỹ thuật ────────────────────────────────────────────────────
    {
        "slug": "quy-trinh-phong-tru-benh-dao-on",
        "title": "Quy trình kỹ thuật phòng trừ bệnh đạo ôn hại lúa theo từng giai đoạn sinh trưởng",
        "type": "guide",
        "category": "huong-dan",
        "days_ago": 3,
        "views": 4210,
        "featured": True,
        "alert": "CB-002",
        "summary": (
            "Bệnh đạo ôn do nấm Pyricularia oryzae gây ra, có thể làm mất trắng cả ruộng trong 7–10 ngày "
            "nếu gặp thời tiết âm u, ẩm độ cao. Quy trình dưới đây hướng dẫn nhận biết và phòng trừ theo "
            "từng giai đoạn, từ xử lý giống đến khi lúa vào chắc."
        ),
        "content": """## Nhận biết bệnh đạo ôn

Bệnh đạo ôn gây hại ở tất cả bộ phận trên mặt đất của cây lúa nhưng phổ biến nhất là trên lá. Vết bệnh
điển hình có dạng **hình thoi**, giữa màu xám tro, viền nâu đậm, kích thước 1–2 cm. Khi bệnh nặng, các
vết liên kết thành mảng lớn làm lá cháy khô.

Trên cổ bông, bệnh gây vết thắt màu nâu thâm, làm bông lúa gãy rụng hoặc lép toàn bộ — đây là dạng
đạo ôn cổ bông gây thiệt hại nặng nhất, thường xuất hiện sau khi lúa trổ gặp mưa.

## Điều kiện phát sinh, phát triển

| Yếu tố | Điều kiện thuận lợi |
|---|---|
| Nhiệt độ | 20–28°C, tối ưu 24–26°C |
| Ẩm độ không khí | Trên 85%, có sương mù hoặc mưa phùn |
| Thời tiết | Âm u kéo dài trên 3 ngày, ít nắng |
| Kỹ thuật canh tác | Bón thừa đạm, bón muộn, sạ dày |
| Giống | Giống nhiễm bệnh, gieo cấy liên tục nhiều vụ |

## Biện pháp theo từng giai đoạn

### 1. Trước khi gieo sạ

- Chọn giống có khả năng chống chịu đạo ôn, luân phiên 2–3 giống giữa các vụ.
- Xử lý hạt giống bằng nước nóng 54°C trong 10 phút hoặc thuốc xử lý hạt được phép sử dụng.
- Vệ sinh đồng ruộng, cày vùi tàn dư rơm rạ sau thu hoạch để diệt nguồn nấm tồn tại.

### 2. Giai đoạn mạ - đẻ nhánh

- Sạ thưa 80–100 kg/ha, không vượt 120 kg/ha.
- Bón phân cân đối theo nguyên tắc **3 giảm 3 tăng**: giảm lượng giống, giảm đạm, giảm thuốc hóa học.
- Không bón đạm khi trời âm u, nhiệt độ dưới 22°C.
- Thăm đồng 3 ngày/lần, phát hiện vết bệnh đầu tiên để phun kịp thời.

### 3. Giai đoạn làm đòng - trổ

Đây là giai đoạn quyết định với đạo ôn cổ bông:

- Phun phòng đạo ôn cổ bông khi lúa bắt đầu trổ, nhắc lại sau 5–7 ngày nếu thời tiết vẫn âm u.
- Thời điểm phun tốt nhất là khi bông còn trong bẹ, chưa trổ thoát.
- Giữ mực nước ruộng 3–5 cm, không để ruộng khô hạn đột ngột.

### 4. Trước thu hoạch

- Ngừng phun theo đúng thời gian cách ly ghi trên nhãn thuốc.
- Vệ sinh đồng ruộng, xử lý rơm rạ trước vụ sau.

## Thuốc và nhóm hoạt chất

| Nhóm hoạt chất | Đặc điểm sử dụng |
|---|---|
| Tricyclazole | Nội hấp mạnh, phòng và chữa, dùng phổ biến cho đạo ôn lá |
| Isoprothiolane | Lưu dẫn, hiệu quả cả đạo ôn lá và cổ bông |
| Propiconazole | Nhóm DMI, tác dụng chữa bệnh nhanh |
| Azoxystrobin | Nhóm QoI, phòng bệnh dài ngày |
| Fenoxanil | Chuyên đạo ôn, hiệu quả giai đoạn muộn |

Luân phiên nhóm hoạt chất giữa các lần phun. Nấm đạo ôn đã ghi nhận kháng với nhiều nhóm thuốc, đặc
biệt khi dùng lặp lại một hoạt chất trên nhiều vụ liên tiếp.

## Lưu ý kỹ thuật quan trọng

> Không phun thuốc trừ nấm đạo ôn bằng bình xịt tia nước mạnh vì giọt nước bắn từ lá bệnh sang lá khỏe
> sẽ làm lây lan bào tử nấm.

Nên phun vào chiều mát, sau khi sương đã tan hẳn. Với ruộng đã có bệnh, giảm ngay lượng đạm còn lại
trong kế hoạch bón, tăng kali để cây cứng cáp. Theo dõi thời tiết trước mỗi đợt bón phân.""",
        "cover_label": "Hướng dẫn kỹ thuật",
    },
    {
        "slug": "ky-thuat-3-giam-3-tang-va-1-phai-5-giam",
        "title": "Kỹ thuật 3 giảm 3 tăng và 1 phải 5 giảm trong canh tác lúa",
        "type": "guide",
        "category": "huong-dan",
        "days_ago": 12,
        "views": 5340,
        "featured": False,
        "summary": (
            "Hai gói kỹ thuật được áp dụng rộng rãi ở đồng bằng sông Cửu Long và nhiều tỉnh phía Bắc, giúp "
            "giảm 20–30% lượng giống, giảm 20–40% thuốc trừ sâu, tăng hiệu quả kinh tế 10–15% mỗi vụ."
        ),
        "content": """## 3 giảm 3 tăng

Ba giảm: **giảm lượng giống gieo sạ, giảm phân đạm, giảm thuốc bảo vệ thực vật**. Ba tăng: **tăng năng
suất, tăng chất lượng nông sản, tăng hiệu quả kinh tế**.

### Giảm lượng giống gieo sạ

Sạ dày là nguyên nhân gốc của nhiều vấn đề: cây cạnh tranh dinh dưỡng, tán lá rậm giữ ẩm độ cao tạo
điều kiện cho nấm bệnh, và dễ bị đổ ngã. Khuyến cáo sạ 80–100 kg/ha với giống thường, 60–80 kg/ha nếu
gieo bằng công cụ sạ hàng.

| Lượng sạ (kg/ha) | Hệ quả |
|---|---|
| 180–200 | Ruộng rậm, đạo ôn và rầy nâu nặng, chi phí thuốc cao |
| 120–150 | Chấp nhận được nhưng cần tăng cường điều tra |
| 80–100 | Khuyến cáo, cây khỏe, ít sâu bệnh, lúa đẻ nhánh bù |

### Giảm phân đạm

Đạm là nguồn dinh dưỡng ưa thích của cả rầy nâu lẫn nấm đạo ôn. Bón đạm cân đối theo khuyến cáo giúp
cây cứng, chống chịu sâu bệnh tốt hơn nhiều so với bón thừa.

Cách bón khuyến cáo cho lúa vụ Đông Xuân:

1. Bón lót trước khi gieo: 30% lượng đạm cả vụ cùng toàn bộ lân.
2. Bón thúc lần 1 khi lúa 2–3 lá: 40% đạm.
3. Bón thúc lần 2 khi lúa bắt đầu làm đòng: 30% đạm còn lại, kết hợp kali.
4. Không bón đạm sau khi lúa đã trổ.

Quan sát màu lá để điều chỉnh: lá xanh nhạt đúng chuẩn ở giai đoạn làm đòng, lá xanh đậm đậm là dấu
hiệu đã bón thừa đạm.

### Giảm thuốc bảo vệ thực vật

Chỉ phun khi dịch hại vượt ngưỡng kinh tế, theo kết quả điều tra thực tế chứ không theo lịch. Bảo
tồn thiên địch để chúng khống chế dịch tự nhiên.

## 1 phải 5 giảm

**Một phải**: phải dùng giống xác nhận, có nguồn gốc rõ ràng, chất lượng tốt.

**Năm giảm**:

1. Giảm lượng giống gieo sạ.
2. Giảm lượng phân đạm.
3. Giảm thuốc bảo vệ thực vật hóa học.
4. Giảm lượng nước tưới.
5. Giảm thất thoát sau thu hoạch.

### Kỹ thuật tưới nước ướt khô xen kẽ

Sau khi lúa bén rễ, cho nước ngập 3–5 cm, chờ đến khi mặt ruộng khô se lại lộ rãnh rồi tưới tiếp. Mực
nước được điều khiển theo chu kỳ ướt khô giúp:

- Rễ lúa ăn sâu hơn, cây cứng chắc, ít đổ ngã.
- Giảm khí mê-tan phát thải, giảm hại môi trường.
- Rầy nâu bị ức chế vì mất điều kiện ẩm thường xuyên.
- Tiết kiệm 20–30% lượng nước tưới.

## Kết quả áp dụng

Trên các mô hình đã tham chiếu tại địa bàn tương tự, áp dụng đồng thời hai gói kỹ thuật giúp:

| Chỉ tiêu | Trước áp dụng | Sau áp dụng |
|---|---|---|
| Lượng giống (kg/ha) | 180 | 90 |
| Số lần phun thuốc/vụ | 5–6 | 2–3 |
| Năng suất (tấn/ha) | 5,2 | 5,8 |
| Lợi nhuận (%) | 100 | 112–118 |

## Điều kiện áp dụng

Kỹ thuật chỉ phát huy hiệu quả khi làm đồng loạt, có sự hướng dẫn của cán bộ chuyên môn và đi đôi với
điều tra sinh vật gây hại định kỳ. Nông dân cần được tập huấn trước khi áp dụng ở vụ đầu tiên.""",
        "cover_label": "Hướng dẫn kỹ thuật",
    },
    {
        "slug": "nhan-biet-va-phong-tru-sau-keo-mua-thu",
        "title": "Nhận biết và phòng trừ sâu keo mùa thu hại ngô, giai đoạn 3–6 lá là quyết định",
        "type": "guide",
        "category": "huong-dan",
        "days_ago": 5,
        "views": 3610,
        "featured": False,
        "alert": "CB-003",
        "summary": (
            "Sâu keo mùa thu (Spodoptera frugiperda) đã gây hại trên ngô ở nhiều địa phương. Sâu non tuổi "
            "1–3 ăn biểu bì lá, từ tuổi 4 đục vào loa kèn và cắn đứt điểm sinh trưởng khiến cây chết. "
            "Phòng trừ hiệu quả nhất ở giai đoạn 3–6 lá."
        ),
        "content": """## Nguồn gốc và phạm vi

Sâu keo mùa thu là loài sâu ăn lá ngô có nguồn gốc châu Mỹ, lần đầu ghi nhận tại châu Á năm 2018 và
nhanh chóng trở thành dịch hại chính trên ngô ở nhiều nước Đông Nam Á. Sâu còn gây hại trên lúa, mía,
cỏ và một số cây thức ăn gia súc.

## Đặc điểm nhận biết

Trứng được đẻ thành ổ 100–200 quả, phủ lớp vảy màu xám. Sâu non có màu thay đổi, từ xanh nhạt đến nâu
sẫm. Hai đặc điểm nhận biết rõ nhất:

- Đầu sâu có **chữ Y ngược** màu vàng nhạt.
- Đốt áp cuối có **4 chấm đen** xếp thành hình vuông.

Phân sâu có dạng hạt màu vàng nâu, kết thành đám trong loa kèn — cách phát hiện nhanh nhất ngoài đồng.
Nhộng nằm trong đất ở độ sâu 2–8 cm.

## So sánh mức gây hại theo tuổi sâu

| Tuổi sâu | Thời gian (ngày) | Kiểu gây hại |
|---|---|---|
| 1 | 1–2 | Cạo biểu bì, để lại lớp màng trắng |
| 2–3 | 2–4 | Ăn thủng lá, lá bị lỗ chỗ |
| 4–6 | 4–8 | Ăn mạnh, đục loa kèn, cắn điểm sinh trưởng |

## Ngưỡng và thời điểm phòng trừ

Thời điểm vàng là **ngô 3–6 lá**, khi sâu non ở tuổi 1–3 chưa vào sâu trong loa kèn. Ngưỡng xử lý:
0,5 con/m² hoặc 5% cây có sâu ở giai đoạn này.

Khi sâu đã ở tuổi 4–6 và nằm trong loa kèn, hiệu quả thuốc giảm mạnh. Giai đoạn này nên chuyển sang
biện pháp thủ công: nhỏ vào loa kèn dung dịch sinh học hoặc bắt sâu trực tiếp.

## Biện pháp phòng trừ tổng hợp

### Biện pháp canh tác

- Gieo đúng thời vụ, đồng loạt để né đỉnh cao sâu.
- Luân canh ngô với cây họ đậu để phá vòng đời sâu.
- Vệ sinh tàn dư, cày vùi sau thu hoạch.
- Bón phân cân đối, tránh thừa đạm.

### Biện pháp sinh học

- Phun chế phẩm Bacillus thuringiensis (Bt) khi sâu mới nở.
- Sử dụng nấm xanh, nấm trắng trong điều kiện ẩm độ cao.
- Thả bọ đuôi kìm, ong ký sinh trứng là biện pháp đang được nhân rộng.

### Biện pháp hóa học

Chỉ dùng khi mật độ vượt ngưỡng, ưu tiên thuốc nhóm diamide, spinosyn hoặc thuốc tác động lên hệ thần
kinh. Phun vào chiều tối vì sâu keo hoạt động mạnh vào đêm. Hướng vòi phun vào loa kèn non.

Luân phiên hoạt chất giữa các lần phun vì sâu keo mùa thu đã ghi nhận kháng nhiều nhóm thuốc nhanh.

## Lưu ý quan trọng

> Ở ruộng ngô nhỏ hơn 0,5 ha và mật độ sâu thấp, biện pháp bắt tay và ngắt ổ trứng thường đạt hiệu quả
> tương đương phun thuốc mà không tốn chi phí và bảo vệ được thiên địch.

Sau thu hoạch không đốt tàn dư mà cày vùi. Sâu keo mùa thu có thể tồn tại trong tàn dư ngô, rơm rạ ở
trạng thái nhộng và gây hại vụ sau.""",
        "cover_label": "Hướng dẫn kỹ thuật",
    },
    {
        "slug": "benh-vang-lun-lun-xoan-la-ray-nau-moi-gioi",
        "title": "Bệnh vàng lùn và lùn xoắn lá: hai bệnh do vi-rút lan truyền qua rầy nâu, không có thuốc chữa",
        "type": "guide",
        "category": "huong-dan",
        "days_ago": 15,
        "views": 2980,
        "featured": False,
        "summary": (
            "Vàng lùn và lùn xoắn lá đều do vi-rút lan truyền qua rầy nâu và không có thuốc chữa. Biện pháp "
            "duy nhất là quản lý môi giới rầy nâu, sạ thưa và nhổ bỏ cây bệnh ngay từ giai đoạn đầu."
        ),
        "content": """## Hai bệnh phải hiểu đúng bản chất

Nhiều nông dân nhầm tưởng lúa vàng là do thiếu phân nên bón thêm đạm, làm bệnh nặng hơn. Thực tế có
hai bệnh vi-rút phổ biến và rất nguy hiểm trên lúa:

| Bệnh | Tác nhân | Triệu chứng chính | Môi giới |
|---|---|---|---|
| Vàng lùn | Rice grassy stunt virus | Lúa lùn, lá vàng, chồi lá mọc thẳng | Rầy nâu |
| Lùn xoắn lá | Rice ragged stunt virus | Lá xanh đậm, rách mép, xoắn ở đỉnh, lùn | Rầy nâu |

Điểm chung: **cả hai đều không có thuốc chữa**. Khi cây đã nhiễm vi-rút, không biện pháp nào cứu được.
Vì vậy toàn bộ hiệu quả nằm ở **phòng bệnh trước khi nhiễm**.

## Cơ chế lan truyền

Rầy nâu chích hút nhựa cây. Khi chích vào cây bệnh, vi-rút xâm nhập cơ thể rầy, nhân lên trong khoảng
6–24 giờ, sau đó khi rầy chuyển sang cây khỏe, vi-rút truyền sang cây mới. Vì vậy sự có mặt của rầy
nâu không chỉ là vấn đề chích hút mà còn là vấn đề môi giới bệnh.

Điều nguy hiểm: chỉ cần 5–10 con rầy mang vi-rút trên một mét vuông cũng đủ gây nhiễm cho nhiều khóm
lúa. Ngưỡng gây bệnh thấp hơn rất nhiều so với ngưỡng gây cháy rầy.

## Giai đoạn mẫn cảm

Lúa nhiễm vi-rút ở giai đoạn **mạ đến 40 ngày sau sạ** chịu thiệt hại nặng nhất, có thể mất trắng. Nếu
nhiễm ở giai đoạn muộn hơn, cây vẫn có thể cho năng suất nhưng giảm 20–40%.

> Nguyên tắc: cây càng nhỏ nhiễm càng nặng. Đây là lý do của chiến lược "né rầy" — bố trí thời vụ để
> giai đoạn mẫn cảm không trùng đỉnh cao rầy nâu.

## Biện pháp phòng

1. **Sạ thưa, sạ đúng lịch**: mật độ thấp giảm cơ hội rầy gặp cây con.
2. **Né rầy**: bố trí thời vụ né đỉnh cao quần thể rầy, gieo sạ đồng loạt theo khu vực.
3. **Quản lý rầy nâu môi giới**: điều tra và phun khi mật độ vượt ngưỡng, đặc biệt 40 ngày đầu sau sạ.
4. **Nhổ bỏ cây bệnh**: cây biểu hiện triệu chứng phải nhổ và tiêu hủy ngay, không để làm nguồn lây.
5. **Vệ sinh đồng ruộng**: xử lý rơm rạ, cỏ bờ sau thu hoạch để diệt nơi trú của rầy.

## Sai lầm phổ biến

| Sai lầm | Hệ quả |
|---|---|
| Bón thêm đạm khi thấy lúa vàng | Bệnh nặng hơn, rầy thích cây giàu đạm |
| Phun thuốc trừ nấm, trừ khuẩn | Không có tác dụng với vi-rút, chỉ lãng phí |
| Chờ đến khi cả ruộng vàng mới xử lý | Đã quá muộn, dịch đã lan toàn đồng |
| Giữ cây bệnh để "xem có hồi không" | Cây không hồi, là nguồn lây cho ruộng bên |

## Thông điệp tuyên truyền

Hai bệnh này không nằm ở cây lúa mà nằm ở con rầy. Quản lý tốt rầy nâu trong 40 ngày đầu sau sạ là
biện pháp duy nhất hiệu quả, rẻ nhất và chắc chắn nhất.""",
        "cover_label": "Hướng dẫn kỹ thuật",
    },
    {
        "slug": "quan-ly-dich-hai-tong-hop-tren-rau-mau",
        "title": "Quản lý dịch hại tổng hợp (IPM) trên rau màu: giảm thuốc, an toàn cho người tiêu dùng",
        "type": "guide",
        "category": "huong-dan",
        "days_ago": 18,
        "views": 2245,
        "featured": False,
        "summary": (
            "Rau màu là nhóm cây có thời gian sinh trưởng ngắn, thu hoạch liên tục nên dư lượng thuốc BVTV "
            "là vấn đề nóng. IPM giúp giảm 30–50% số lần phun, bảo đảm an toàn thực phẩm mà không giảm năng suất."
        ),
        "content": """## Vì sao rau màu cần IPM

Rau ăn lá như cải, xà lách có thời gian từ gieo đến thu hoạch chỉ 25–35 ngày. Nếu phun thuốc sát ngày
thu hoạch, dư lượng sẽ còn nguyên trên sản phẩm khi tới bàn ăn. Trong khi đó, sâu tơ, bọ nhảy và bệnh
sương mai lại rất khó kiểm soát nếu chỉ dựa vào thuốc hóa học.

IPM là tiếp cận **phối hợp nhiều biện pháp**, ưu tiên biện pháp sinh thái, và chỉ dùng thuốc như giải
pháp cuối cùng khi các biện pháp khác không đủ.

## Bốn tầng biện pháp theo thứ tự ưu tiên

### Tầng 1 — Biện pháp canh tác

- Luân canh cây khác họ để phá vòng đời sâu tơ, bọ nhảy.
- Vệ sinh đồng ruộng, dọn tàn dư cây bệnh sau thu hoạch.
- Bón phân cân đối, không thừa đạm làm lá mềm dễ bị sâu.
- Trồng mật độ hợp lý, tạo thông thoáng giảm ẩm độ trong luống.
- Che phủ bằng màng nông nghiệp để ngăn bọ nhảy và rầy.

### Tầng 2 — Biện pháp sinh học

| Thiên địch, chế phẩm | Đối tượng kiểm soát |
|---|---|
| Ong ký sinh trứng Trichogramma | Sâu tơ, sâu xanh |
| Bacillus thuringiensis (Bt) | Sâu non bộ cánh vảy |
| Nấm xanh Metarhizium | Bọ nhảy, rầy |
| Nấm trắng Beauveria | Sâu đất, bọ nhảy |
| Bọ đuôi kìm | Sâu đất, sâu non |

Sử dụng chế phẩm sinh học đúng cách: phun chiều mát, không pha chung với thuốc trừ nấm vì sẽ diệt nấm
có ích trong chế phẩm.

### Tầng 3 — Biện pháp thủ công, cơ giới

- Dùng bẫy dính vàng thu hút bọ nhảy, rầy, ruồi đục lá.
- Bẫy pheromone cho sâu tơ, sâu xanh.
- Bắt sâu bằng tay ở diện tích nhỏ.
- Ngắt bỏ lá, quả bị bệnh ngay khi phát hiện.

### Tầng 4 — Biện pháp hóa học

Chỉ dùng khi mật độ vượt ngưỡng, chọn thuốc ít độc, có thời gian cách ly ngắn, và tuyệt đối tuân thủ
thời gian cách ly trước thu hoạch.

## Ngưỡng kinh tế tham khảo trên rau

| Cây | Sinh vật gây hại | Ngưỡng xử lý |
|---|---|---|
| Cải bắp | Sâu tơ | 10–15 con/cây (giai đoạn cây con) |
| Cải bắp | Bọ nhảy | 20–30 con/cây |
| Cà chua | Sâu xanh | 2–4 con/cây |
| Dưa chuột | Bệnh sương mai | Khi vết bệnh đầu tiên xuất hiện |

## Ghi chép và truy xuất nguồn gốc

Mỗi vụ nên ghi lại: ngày gieo, loại thuốc đã dùng, ngày phun, liều lượng và ngày thu hoạch. Đây là căn
cứ chứng minh sản phẩm an toàn khi được kiểm tra và là nền tảng cho truy xuất nguồn gốc.

> Người tiêu dùng ngày càng quan tâm đến nguồn gốc rau. Nhật ký canh tác đầy đủ chính là lợi thế cạnh
> tranh của hợp tác xã, không chỉ là thủ tục.

## Kết quả kỳ vọng

Áp dụng đầy đủ bốn tầng biện pháp thường đạt: giảm 30–50% số lần phun thuốc, giảm 20–30% chi phí vật tư,
năng suất giữ nguyên hoặc tăng nhẹ, và quan trọng nhất là sản phẩm đạt kiểm tra dư lượng.""",
        "cover_label": "Hướng dẫn kỹ thuật",
    },
    {
        "slug": "benh-vang-la-gan-xanh-tren-cay-co-mui",
        "title": "Bệnh vàng lá gân xanh trên cây có múi: hiểu đúng để phòng, vì không có thuốc chữa",
        "type": "guide",
        "category": "huong-dan",
        "days_ago": 21,
        "views": 1760,
        "featured": False,
        "alert": "CB-004",
        "summary": (
            "Bệnh vàng lá gân xanh (Greening, HLB) do vi khuẩn Candidatus Liberibacter asiaticus gây ra, "
            "lan qua rầy chổng cánh và cành ghép nhiễm bệnh. Bệnh không có thuốc chữa, phòng là biện pháp duy nhất."
        ),
        "content": """## Bệnh nguy hiểm nhất của cây có múi

Vàng lá gân xanh được xem là bệnh hủy diệt với ngành trồng cây có múi trên toàn thế giới. Cây nhiễm
bệnh vẫn có thể ra quả vài năm nhưng năng suất giảm dần, quả nhỏ, méo, vị đắng và cuối cùng cây chết.

## Nhận biết triệu chứng

Triệu chứng điển hình và dễ nhầm nhất:

- **Vàng lá không đối xứng**: một nửa lá vàng, nửa còn lại còn xanh — khác với thiếu dinh dưỡng gây
  vàng đối xứng.
- **Gân lá còn xanh** nổi rõ trên nền lá vàng.
- Cành bệnh mọc thẳng đứng, lá nhỏ và dày hơn bình thường.
- Quả nhỏ, méo, chín ngược (chín từ cuống xuống), hạt lép và có màu nâu.
- Rễ tơ bị thối, cây suy dần.

Cây nhiễm bệnh ở giai đoạn đầu có thể không biểu hiện triệu chứng nhưng vẫn là nguồn lây — đó là lý do
bệnh lan rất âm thầm.

## Đường lan truyền

| Đường lây | Mức độ nguy hiểm |
|---|---|
| Rầy chổng cánh (Diaphorina citri) | Cao nhất, lan theo vườn |
| Cành ghép, mắt ghép nhiễm bệnh | Rất cao, lây ngay từ cây giống |
| Dụng cụ cắt tỉa không khử trùng | Trung bình |

Rầy chổng cánh ưa cư trú trên chồi non và lộc non. Thời điểm vườn ra lộc cũng là thời điểm rầy hoạt
động mạnh nhất.

## Vì sao không có thuốc chữa

Vi khuẩn gây bệnh nằm trong mạch dẫn của cây, khu trú ở mô libe. Không có hoạt chất nào đủ hiệu lực để
tiêu diệt vi khuẩn trong mạch dẫn mà không gây hại cây. Các thuốc kháng sinh nông nghiệp chỉ ức chế tạm
thời và không được khuyến cáo vì nguy cơ kháng kháng sinh.

## Chiến lược phòng bệnh

1. **Giống sạch bệnh**: chỉ mua cây giống từ vườn ươm được chứng nhận, có nhãn truy xuất.
2. **Quản lý rầy chổng cánh**: phun thuốc vào các đợt ra lộc non, luân phiên hoạt chất.
3. **Kiểm tra vườn định kỳ 7–10 ngày/lần**: phát hiện và chặt bỏ cây bệnh ngay.
4. **Khử trùng dụng cụ**: rửa và khử trùng kéo cắt tỉa giữa các cây.
5. **Không trồng xen cây có múi không rõ nguồn** trong vùng đã có bệnh.

> Chặt bỏ cây bệnh là quyết định khó về kinh tế nhưng cần thiết để bảo vệ cả vườn. Một cây bệnh giữ
> lại có thể lây cho hàng chục cây khỏe trong vòng hai năm.

## Lưu ý về chẩn đoán

Triệu chứng vàng lá gân xanh có thể nhầm với thiếu kẽm, thiếu magiê hoặc bệnh Tristeza. Khi nghi ngờ,
cần lấy mẫu gửi phòng thí nghiệm để xét nghiệm PCR — đây là căn cứ chính xác nhất trước khi quyết định
chặt bỏ cây.""",
        "cover_label": "Hướng dẫn kỹ thuật",
    },
    # ── Bản tin chuyên ngành ──────────────────────────────────────────────────
    {
        "slug": "ban-tin-chuyen-nganh-tuan-44",
        "title": "Bản tin chuyên ngành tuần 44: tổng hợp diễn biến sinh vật gây hại và khuyến nghị chỉ đạo",
        "type": "bulletin",
        "category": "ban-tin",
        "days_ago": 1,
        "views": 1310,
        "featured": False,
        "summary": (
            "Tổng hợp diễn biến sinh vật gây hại trên lúa, ngô và cây có múi trong tuần 44; cảnh báo "
            "hai đối tượng cần ưu tiên chỉ đạo là rầy nâu và bệnh đạo ôn lá."
        ),
        "content": """## Tóm tắt tuần

Tuần 44 ghi nhận ba diễn biến đáng chú ý: rầy nâu tăng mạnh ở các huyện ven đê, bệnh đạo ôn lá bùng
phát sau đợt sương mù kéo dài, và sâu keo mùa thu bắt đầu xuất hiện trên ngô đông xuân.

| Cây trồng | Diện tích gieo trồng (ha) | Diện tích nhiễm (ha) | Mức độ chính |
|---|---|---|---|
| Lúa | 28.500 | 1.240 | Rầy nâu, đạo ôn |
| Ngô | 4.200 | 185 | Sâu keo mùa thu |
| Rau màu | 1.800 | 92 | Sâu tơ, bọ nhảy |
| Cây có múi | 3.400 | 46 | Vàng lá gân xanh |

## Hai đối tượng ưu tiên chỉ đạo

### 1. Rầy nâu trên lúa

Mật độ trung bình 1.850 con/m², tăng 46% so với tuần trước. Tỷ lệ rầy cánh ngắn đạt 62% — dấu hiệu quần
thể ổn định và chuẩn bị bùng phát. Yêu cầu các Trạm tăng tần suất điều tra lên 3 ngày/lần trên toàn bộ
điểm cố định.

### 2. Bệnh đạo ôn lá

Đã ghi nhận vết bệnh tại 5/12 điểm điều tra, tỷ lệ lá hại 3–8%, cao nhất 15%. Thời tiết sương mù kéo
dài đến 9 giờ sáng tạo điều kiện lý tưởng cho nấm phát triển. Nguy cơ đạo ôn cổ bông rất cao nếu lúa
trổ trong hai tuần tới.

## Khuyến nghị chỉ đạo

1. Ban hành bản tin cảnh báo rầy nâu và đạo ôn, phát trên kênh web và thông báo nội bộ.
2. Phân công nhiệm vụ kiểm tra thực địa sau xử lý cho các Trạm trọng điểm.
3. Tuyên truyền nông dân không phun tràn lan, chỉ phun khi vượt ngưỡng kinh tế.
4. Rà soát dự trữ thuốc đặc hiệu tại các Trạm, bảo đảm sẵn sàng khi dịch bùng phát.

## Dữ liệu kèm theo

Số liệu chi tiết theo từng điểm điều tra đã được cập nhật vào phân hệ Điều tra và có thể kết xuất báo
cáo tiến độ từ phân hệ Báo cáo. Đề nghị các đơn vị đối chiếu số liệu trước ngày 05 hằng tuần.""",
        "cover_label": "Bản tin chuyên ngành",
    },
    # ── Tin tức sự kiện ───────────────────────────────────────────────────────
    {
        "slug": "khoi-dong-he-thong-quan-ly-dieu-tra",
        "title": "Khởi động hệ thống quản lý điều tra sinh vật gây hại phục vụ công tác chỉ đạo",
        "type": "news",
        "category": "tin-tuc",
        "days_ago": 30,
        "views": 987,
        "featured": False,
        "summary": (
            "Hệ thống chính thức đi vào vận hành, cho phép cập nhật dữ liệu điều tra ngoài đồng, "
            "tổng hợp báo cáo tự động và phát hành bản tin cảnh báo tới các đơn vị trong cùng một quy trình."
        ),
        "content": """## Mục tiêu của hệ thống

Hệ thống được xây dựng nhằm thay thế quy trình tổng hợp báo cáo thủ công bằng ghi chép giấy, vốn mất
nhiều thời gian và dễ sai lệch khi chuyển qua nhiều khâu. Toàn bộ dữ liệu điều tra từ cấp xã, huyện
được nhập trực tiếp vào phân hệ Điều tra và tổng hợp tự động.

## Chức năng chính

- **Danh mục chuyên môn**: cây trồng, sinh vật gây hại, giai đoạn sinh trưởng, mức độ gây hại.
- **Điều tra**: kế hoạch, tuyến điều tra, điểm cố định, phiếu điều tra và quy trình xác nhận hai cấp.
- **Dự tính, dự báo**: so sánh tỷ lệ hại thực tế với ngưỡng chuyên môn để xác định mức nguy cơ.
- **Cảnh báo**: phát hành bản tin tới đơn vị nhận, kèm nhiệm vụ theo dõi sau cảnh báo.
- **Bản đồ**: hiển thị điểm điều tra và vùng nguy cơ trên nền bản đồ số.
- **Báo cáo**: kết xuất báo cáo tiến độ, tình hình phát sinh và diện tích bị ảnh hưởng.

## Phân quyền theo vai trò

Hệ thống áp dụng phân quyền theo mô-đun và hành động, tách biệt rõ người nhập liệu, người xác nhận và
người phê duyệt. Một phiếu điều tra do cán bộ điều tra nhập phải được cán bộ chuyên môn xác nhận mới
được đưa vào tổng hợp chính thức.

## Kế hoạch triển khai

1. Tuần 1–2: tập huấn cho cán bộ các Trạm về nhập liệu và quy trình xác nhận.
2. Tuần 3–4: nhập thử dữ liệu 12 tuần gần nhất, đối chiếu với sổ ghi chép cũ.
3. Từ tuần 5: vận hành chính thức, báo cáo tuần lấy trực tiếp từ hệ thống.

## Đề nghị các đơn vị

Các Trạm cử cán bộ tham gia đầy đủ, chuẩn bị sổ ghi chép điều tra cũ để đối chiếu trong giai đoạn nhập
thử. Mọi vướng mắc trong quá trình sử dụng phản ánh về Chi cục để được hỗ trợ kịp thời.""",
        "cover_label": "Tin tức - sự kiện",
    },
    {
        "slug": "tap-huan-ipm-cho-nong-dan",
        "title": "Tập huấn IPM cho hơn 300 nông dân: giảm thuốc, tăng hiệu quả, bảo vệ sức khỏe",
        "type": "news",
        "category": "tin-tuc",
        "days_ago": 8,
        "views": 1420,
        "featured": False,
        "summary": (
            "Lớp tập huấn được tổ chức tại bốn xã trọng điểm, hướng dẫn nông dân nhận biết thiên địch, "
            "điều tra đồng ruộng và áp dụng ngưỡng kinh tế thay vì phun thuốc theo lịch."
        ),
        "content": """## Nội dung tập huấn

Chương trình tập huấn kéo dài ba ngày mỗi lớp, kết hợp lý thuyết tại hội trường và thực hành trực tiếp
trên đồng ruộng. Học viên được chia nhóm, tự điều tra ruộng mẫu và thảo luận quyết định phun hay không
phun dựa trên số liệu thu được.

## Bốn nội dung cốt lõi

1. **Nhận biết sinh vật gây hại**: phân biệt rầy nâu với các loài rầy khác, nhận diện vết bệnh đạo ôn
   hình thoi, phát hiện sâu keo qua phân sâu trong loa kèn.
2. **Nhận biết thiên địch**: nhện lùn, bọ rùa, bọ xít mù xanh, ong ký sinh — những "đồng minh" thường
   bị phun thuốc tiêu diệt cùng.
3. **Điều tra và ngưỡng kinh tế**: dùng khay đập 5 điểm chéo góc, đếm mật độ và so với ngưỡng trước
   khi quyết định.
4. **Kỹ thuật phun an toàn**: bảo hộ lao động, pha thuốc đúng liều, thời gian cách ly trước thu hoạch.

## Kết quả bước đầu

Sau tập huấn, các hộ tham gia cam kết giảm số lần phun so với vụ trước. Nhóm hộ thực hành tại xã A1 đã
giảm từ 5,4 lần phun xuống 2,6 lần phun mỗi vụ, chi phí thuốc giảm gần một nửa trong khi năng suất
không đổi.

| Chỉ tiêu | Vụ trước | Vụ này (nhóm thực hành) |
|---|---|---|
| Số lần phun thuốc trừ sâu | 5,4 | 2,6 |
| Chi phí thuốc (nghìn đồng/ha) | 3.200 | 1.750 |
| Năng suất (tấn/ha) | 5,3 | 5,5 |

## Định hướng tiếp theo

Duy trì nhóm nông dân nòng cốt tại mỗi xã để hỗ trợ lẫn nhau và làm hạt nhân tuyên truyền cho vụ sau.
Cán bộ Trạm sẽ duy trì lịch thăm đồng cùng nông dân ít nhất 2 tuần một lần trong suốt vụ.""",
        "cover_label": "Tin tức - sự kiện",
    },
    {
        "slug": "hoi-nghi-tong-ket-cong-tac-bvtv",
        "title": "Hội nghị tổng kết công tác bảo vệ thực vật: đánh giá kết quả và định hướng vụ tới",
        "type": "news",
        "category": "tin-tuc",
        "days_ago": 25,
        "views": 742,
        "featured": False,
        "summary": (
            "Hội nghị đánh giá tỷ lệ diện tích nhiễm sinh vật gây hại được phát hiện sớm đạt 87%, "
            "giảm 15% lượng thuốc BVTV sử dụng so với cùng kỳ và đề ra bốn nhiệm vụ trọng tâm cho vụ tới."
        ),
        "content": """## Kết quả nổi bật

Công tác điều tra và dự tính dự báo được duy trì ổn định với 12 điểm điều tra cố định trên toàn tỉnh.
Tỷ lệ diện tích nhiễm được phát hiện và cảnh báo kịp thời đạt 87%, tăng 9 điểm phần trăm so với cùng kỳ.

| Chỉ tiêu | Cùng kỳ | Năm nay | So sánh |
|---|---|---|---|
| Điểm điều tra cố định | 8 | 12 | +4 |
| Diện tích nhiễm được cảnh báo kịp thời | 78% | 87% | +9 điểm |
| Lượng thuốc BVTV sử dụng | 100% | 85% | −15% |
| Số bản tin cảnh báo phát hành | 14 | 22 | +8 |

## Hạn chế cần khắc phục

1. Chất lượng phiếu điều tra chưa đồng đều, còn tình trạng nhập liệu muộn so với quy định.
2. Việc dự báo dựa trên cảm nhận chuyên môn chưa được chuẩn hóa bằng ngưỡng và dữ liệu định lượng.
3. Công tác tuyên truyền chưa đến được nhóm nông dân sản xuất nhỏ, manh mún.

## Bốn nhiệm vụ trọng tâm

- Chuẩn hóa toàn bộ ngưỡng kinh tế và tiêu chí đánh giá nguy cơ theo quy chuẩn kỹ thuật quốc gia.
- Tăng cường kiểm tra chéo 10% số phiếu điều tra để nâng cao chất lượng dữ liệu.
- Đẩy mạnh tuyên truyền bằng hình ảnh trực quan, video ngắn phù hợp với điện thoại thông minh.
- Mở rộng áp dụng IPM ra nhóm cây rau màu và cây ăn quả có múi.

## Kết luận của hội nghị

Hội nghị thống nhất nguyên tắc: mọi khuyến cáo phòng trừ phải dựa trên dữ liệu điều tra thực tế và
ngưỡng chuyên môn đã được phê duyệt, không dựa trên cảm tính hay áp lực thương mại từ thuốc BVTV.""",
        "cover_label": "Tin tức - sự kiện",
    },
    {
        "slug": "ung-pho-mua-lon-ngap-ung",
        "title": "Ứng phó mưa lớn, ngập úng: bốn việc cần làm ngay để hạn chế thiệt hại mùa vụ",
        "type": "news",
        "category": "tin-tuc",
        "days_ago": 11,
        "views": 2050,
        "featured": False,
        "summary": (
            "Dự báo mưa lớn diện rộng trong 3–4 ngày tới, nguy cơ ngập úng cục bộ tại các vùng trũng. "
            "Khuyến cáo các địa phương chủ động tiêu úng, bảo vệ diện tích lúa và rau màu đang trong giai đoạn mẫn cảm."
        ),
        "content": """## Tình hình dự báo

Mưa lớn diện rộng được dự báo trong 3–4 ngày tới với tổng lượng mưa 120–200 mm, cục bộ trên 250 mm.
Các vùng trũng, ven sông và khu vực thoát nước kém có nguy cơ ngập úng cao. Diện tích lúa giai đoạn
làm đòng đến trổ hiện chiếm 68% — giai đoạn mẫn cảm nhất với ngập.

## Bốn việc cần làm ngay

### 1. Kiểm tra và khơi thông hệ thống tiêu úng

Rà soát toàn bộ kênh mương, cống, trạm bơm. Khơi thông các điểm tắc nghẽn trước khi mưa đến. Chuẩn bị
máy bơm dự phòng tại các vùng trũng.

### 2. Hạ mực nước ruộng chủ động

Với ruộng lúa đang làm đòng, hạ mực nước xuống 3–5 cm trước khi mưa để có dư địa chứa nước. Không để
nước sâu quá 15 cm vì lúa ngập sâu trên 3 ngày sẽ giảm năng suất rõ rệt.

### 3. Bảo vệ rau màu và vườn cây

- Lên luống cao, khơi rãnh thoát nước.
- Che phủ tạm bằng bạt với diện tích rau đang thu hoạch.
- Với vườn cây có múi, kiểm tra và khơi thông mương thoát để tránh thối rễ.

### 4. Tạm ngừng phun thuốc

Không phun thuốc BVTV trước và trong mưa lớn vì thuốc sẽ bị rửa trôi, gây lãng phí và ô nhiễm nguồn nước.

## Sau khi mưa rút

1. Kiểm tra và đánh giá mức thiệt hại từng thửa.
2. Xử lý ngay bệnh bạc lá, đốm sọc vi khuẩn — nhóm bệnh phát sinh mạnh sau mưa giông.
3. Tỉa bỏ lá, cành thối ở rau màu, phun thuốc trừ nấm phòng bệnh chân thối.
4. Bón bổ sung kali, không bón đạm ngay sau ngập vì rễ chưa phục hồi.

> Ruộng bị ngập trên 3 ngày cần đánh giá lại năng suất dự kiến. Nếu thiệt hại trên 70%, chuyển sang
> phương án gieo cấy lại bằng giống ngắn ngày để kịp khung thời vụ.

## Trách nhiệm các đơn vị

Các Trạm Trồng trọt và BVTV trực 24/24 trong thời gian mưa lớn, tổng hợp thiệt hại báo cáo về Chi cục
chậm nhất 24 giờ sau khi mưa kết thúc.""",
        "cover_label": "Tin tức - sự kiện",
    },
    # ── Thông báo ─────────────────────────────────────────────────────────────
    {
        "slug": "thong-bao-lich-dieu-tra-dinh-ky",
        "title": "Thông báo lịch điều tra định kỳ và phân công nhiệm vụ tháng 11",
        "type": "notice",
        "category": "thong-bao",
        "days_ago": 1,
        "views": 486,
        "featured": False,
        "summary": (
            "Từ tháng 11, điều tra định kỳ được thực hiện vào thứ Hai hằng tuần, số liệu phải được nhập "
            "và gửi xác nhận trước 16 giờ thứ Ba. Phân công cụ thể theo từng Trạm."
        ),
        "content": """## Lịch điều tra

Điều tra định kỳ thực hiện **thứ Hai hằng tuần** tại toàn bộ 12 điểm cố định. Trường hợp thời tiết xấu,
lùi sang thứ Ba nhưng phải báo cáo lý do.

## Quy trình nhập liệu

1. Cán bộ điều tra nhập phiếu vào phân hệ Điều tra ngay trong ngày.
2. Phiếu phải có đủ số liệu mật độ, tỷ lệ hại và tình trạng ruộng.
3. Gửi xác nhận trước **16 giờ thứ Ba**.
4. Cán bộ chuyên môn xác nhận trước 17 giờ thứ Tư để số liệu vào báo cáo tuần.

Phiếu gửi muộn sau thời hạn trên sẽ không được đưa vào báo cáo tuần, đơn vị chịu trách nhiệm giải trình.

## Phân công

| Đơn vị | Điểm điều tra | Cán bộ phụ trách |
|---|---|---|
| Trạm Huyện A | Điểm A1-1, A1-2, A2-1, A2-2 | Hoàng Điều Tra 1 |
| Trạm Huyện B | Điểm B1-1, B1-2, B2-1, B2-2 | Vũ Điều Tra 2 |

## Lưu ý

- Mang đủ dụng cụ: khay đập, thước, sổ ghi, máy ảnh hoặc điện thoại chụp ảnh hiện trường.
- Chụp ảnh ruộng điều tra, đính kèm phiếu để làm căn cứ kiểm tra chéo.
- Trường hợp phát hiện dịch bất thường, báo ngay về Chi cục, không chờ đến lịch định kỳ.""",
        "cover_label": "Thông báo",
    },
    {
        "slug": "thong-bao-tam-ngung-phun-thuoc-bao-ve-ong-mat",
        "title": "Thông báo tạm ngừng phun thuốc trừ sâu trong thời gian hoa nở để bảo vệ ong mật",
        "type": "notice",
        "category": "thong-bao",
        "days_ago": 7,
        "views": 623,
        "featured": False,
        "summary": (
            "Trong thời gian cây ăn quả và rau màu ra hoa, đề nghị tạm ngừng phun thuốc trừ sâu vào ban ngày "
            "để bảo vệ đàn ong mật — vừa bảo vệ năng suất do ong thụ phấn, vừa tránh thiệt hại cho hộ nuôi ong."
        ),
        "content": """## Lý do

Ong mật là tác nhân thụ phấn quan trọng bậc nhất cho cây ăn quả và nhiều loại rau màu. Thiếu ong thụ
phấn, tỷ lệ đậu quả có thể giảm 30–60%. Trong khi đó, phun thuốc trừ sâu vào ban ngày khi cây đang nở
hoa có thể tiêu diệt toàn bộ đàn ong đi lấy mật.

## Yêu cầu cụ thể

1. **Không phun thuốc trừ sâu vào ban ngày** trong thời gian cây ra hoa, đặc biệt 8–16 giờ.
2. Nếu buộc phải phun, thực hiện **sau 17 giờ** khi ong đã về tổ.
3. Ưu tiên thuốc ít độc với ong, tránh nhóm thuốc phổ rộng như pyrethroid.
4. Không phun khi có gió mạnh làm thuốc bay sang vườn lân cận.
5. Thông báo trước cho các hộ nuôi ong trong bán kính 2 km nếu có kế hoạch phun.

## Trách nhiệm

Các Trạm phổ biến nội dung này tới các hợp tác xã, tổ chức dịch vụ phun thuốc và hộ nông dân trên địa
bàn. Trường hợp phát hiện thiệt hại đàn ong do phun thuốc, các bên liên quan phối hợp xác minh và xử lý
theo quy định.

> Đây là biện pháp đôi bên cùng có lợi: nông dân được thụ phấn tốt hơn, người nuôi ong giữ được đàn,
> môi trường giảm ô nhiễm thuốc bảo vệ thực vật.

## Thời gian áp dụng

Từ ngày ra thông báo đến hết thời kỳ hoa nở của các vườn cây ăn quả chính trên địa bàn, dự kiến 4–6 tuần.""",
        "cover_label": "Thông báo",
    },
]


class Command(BaseCommand):
    help = "Ghép nội dung thực tế (bài viết, cảnh báo, dự báo, ảnh đại diện) vào cổng thông tin."

    def add_arguments(self, parser):
        parser.add_argument("--force", action="store_true", help="Ghi đè nội dung bài viết đã có.")
        parser.add_argument("--no-cover", action="store_true", help="Không sinh ảnh đại diện.")

    @transaction.atomic
    def handle(self, *args, **options):
        self.force = options["force"]
        self.make_covers = not options["no_cover"]
        random.seed(2026)

        self.catalogs()
        self.alerts()
        created, updated = self.articles()

        from cms import insights

        scored = insights.refresh_hot_scores()
        self.stdout.write(self.style.SUCCESS(
            f"Xong: {created} bài mới, {updated} bài cập nhật, chấm điểm {scored} bài."))

        top = insights.hot_posts(limit=5)
        if top:
            self.stdout.write("\nTin nóng nhất trên cổng thông tin:")
            for p in top:
                self.stdout.write(f"  {p.hot_score:6.2f}  {p.get_post_type_display():<24} {p.title[:64]}")

    # ---------- danh mục chuyên môn ----------
    def catalogs(self):
        from catalog.models import Crop, GrowthStage, PestSpecies

        from cms.models import Category

        for slug, name, order in CATEGORIES:
            Category.objects.update_or_create(slug=slug, defaults={"name": name, "order": order})

        self.crops = {}
        for code, name, sci in CROPS:
            self.crops[code] = Crop.objects.update_or_create(
                code=code, defaults={"name": name, "scientific_name": sci})[0]

        self.pests = {}
        for code, name, sci, ptype, crops, guidance in PESTS:
            pest, _ = PestSpecies.objects.update_or_create(
                code=code, defaults={"name": name, "scientific_name": sci, "pest_type": ptype,
                                     "control_guidance": guidance})
            pest.crops.set([self.crops[c] for c in crops])
            self.pests[code] = pest

        for code, name, crop in STAGES:
            GrowthStage.objects.update_or_create(code=code, defaults={"name": name, "crop": self.crops[crop]})

    # ---------- bản tin cảnh báo ----------
    def alerts(self):
        from accounts.models import AdminDivision, Unit

        from alerts.models import Alert, AlertRevision, FollowUpTask
        from accounts.models import User
        from forecasts.models import Forecast, Threshold

        today = timezone.localdate()
        districts = list(AdminDivision.objects.filter(level=2))
        units = list(Unit.objects.filter(parent__isnull=False))
        expert = User.objects.filter(role="expert").first()
        approver = User.objects.filter(role="approver").first()
        forecast = Forecast.objects.first()
        threshold = Threshold.objects.first()

        self.alerts_map = {}
        for spec in ALERTS:
            days_from, days_to = spec["valid_from"], spec["valid_to"]
            alert, created = Alert.objects.update_or_create(
                code=spec["code"],
                defaults={
                    "title": spec["title"],
                    "pest": self.pests[spec["pest"]],
                    "crop": self.crops[spec["crop"]],
                    "valid_from": today + timedelta(days=days_from),
                    "valid_to": today + timedelta(days=days_to),
                    "risk_level": spec["risk_level"],
                    "forecast": forecast if spec["pest"] == "RNN" else None,
                    "basis": spec["basis"],
                    "guidance": spec["guidance"],
                    "channels": ["web", "notify"],
                    "status": "published",
                    "created_by": expert,
                    "approved_by": approver,
                    "published_at": timezone.now() - timedelta(days=max(0, -days_from) + 1),
                })
            if created:
                alert.divisions.set(districts)
                alert.recipient_units.set(units)
                AlertRevision.objects.create(
                    alert=alert, action="publish", version=1, user=approver,
                    snapshot={"title": alert.title, "risk_level": alert.risk_level},
                    note="Phát hành bản tin cảnh báo.")
            self.alerts_map[spec["code"]] = alert

        # nhiệm vụ theo dõi sau cảnh báo
        followups = [
            ("CB-001", "Kiểm tra thực tế sau xử lý rầy nâu tại các xã ven đê", 5, "doing"),
            ("CB-002", "Đánh giá hiệu quả phun trừ đạo ôn lá sau 7 ngày", 3, "assigned"),
            ("CB-003", "Kiểm tra mật độ sâu keo lứa mới trên ngô 3–6 lá", 6, "assigned"),
            ("CB-004", "Rà soát, chặt bỏ cây có múi nhiễm vàng lá gân xanh", 10, "assigned"),
        ]
        surveyor = User.objects.filter(role="surveyor").first()
        for code, title, days, status in followups:
            alert = self.alerts_map[code]
            FollowUpTask.objects.get_or_create(
                alert=alert, title=title,
                defaults={"division": districts[0] if districts else None,
                          "unit": units[0] if units else None,
                          "assignee": surveyor,
                          "due_date": today + timedelta(days=days),
                          "status": status})

        # dự báo cho sâu keo nếu chưa có
        from catalog.models import GrowthStage

        Forecast.objects.get_or_create(
            title="Dự báo sâu keo mùa thu hại ngô đông xuân",
            defaults={
                "pest": self.pests["SAU"], "crop": self.crops["NGO"],
                "division": districts[0] if districts else None,
                "stage": GrowthStage.objects.filter(code="NGO-3L").first(),
                "valid_from": today, "valid_to": today + timedelta(days=21),
                "risk_level": "medium", "expected_rate": 18, "expected_area": 185,
                "basis": "Mật độ sâu non 0,3–1,4 con/m² tại 4 xã; bướm đã vũ hóa sau đợt rộ đầu.",
                "recommendation": "Thăm đồng 3 ngày/lần ở giai đoạn 3–6 lá, phun khi vượt 0,5 con/m².",
                "threshold": threshold, "origin": "manual", "status": "confirmed",
                "created_by": expert, "confirmed_by": approver, "confirmed_at": timezone.now(),
            })

    # ---------- bài viết ----------
    def articles(self):
        from cms.models import Post, PostRevision
        from accounts.models import User

        from cms.models import Category

        now = timezone.now()
        author = User.objects.filter(role="editor").first()
        approver = User.objects.filter(role="approver").first()
        cats = {c.slug: c for c in Category.objects.all()}

        created_count = updated_count = 0
        for index, spec in enumerate(ARTICLES):
            cat = cats.get(spec["category"])
            defaults = {
                "title": spec["title"],
                "post_type": spec["type"],
                "category": cat,
                "summary": spec["summary"],
                "content": spec["content"].strip(),
                "status": "published",
                "is_featured": spec.get("featured", False),
                "published_at": now - timedelta(days=spec["days_ago"], hours=index % 9 + 1),
                "author": author,
                "reviewed_by": approver,
                "review_note": "Duyệt nội dung chuyên ngành.",
                "alert": self.alerts_map.get(spec.get("alert") or ""),
                "views": spec["views"],
                "version": 1,
            }
            post = Post.objects.filter(slug=spec["slug"]).first()
            if post and not self.force:
                if self._is_untouched_seed(post):
                    # Bài do chính lệnh này tạo và chưa ai sửa: cập nhật theo bản mới,
                    # để chạy lại seeder sau khi nâng cấp nội dung vẫn nhận bản mới.
                    for field, value in defaults.items():
                        setattr(post, field, value)
                    post.save()
                    updated_count += 1
                else:
                    updated_count += 1
                    if self.make_covers and not post.cover:
                        self._attach_cover(post, spec, index)
                    continue
            elif post:
                for field, value in defaults.items():
                    setattr(post, field, value)
                post.save()
                updated_count += 1
            else:
                post = Post.objects.create(slug=spec["slug"], **defaults)
                created_count += 1
                PostRevision.objects.create(
                    post=post, version=1, action="create", title=post.title,
                    content=post.content, note=SEED_NOTE, user=author)

            if self.make_covers and (self.force or not post.cover):
                self._attach_cover(post, spec, index)

        return created_count, updated_count

    @staticmethod
    def _is_untouched_seed(post) -> bool:
        """Bài do seeder tạo và chưa bị biên tập viên sửa tay."""
        return post.revisions.count() == 1 and post.revisions.first().note == SEED_NOTE

    def _attach_cover(self, post, spec, index):
        label = spec.get("cover_label") or post.get_post_type_display()
        content = render_cover(label, spec["title"], spec["type"], seed=index + 17)
        post.cover.save(f"{spec['slug']}.jpg", content, save=True)
        self.stdout.write(f"  ảnh: {spec['slug']}.jpg")
