"""Chấm điểm tin nóng và trợ lý đọc bài — chạy hoàn toàn nội bộ, không gọi dịch vụ ngoài.

Toàn bộ xử lý ở đây là thuật toán tất định trên văn bản và số liệu thật trong CSDL:
không có mô hình ngôn ngữ, không gửi dữ liệu ra internet (phù hợp triển khai mạng nội bộ).

Hai nhóm chức năng:
    * Xếp hạng tin:  score_post(), refresh_hot_scores()
    * Trợ lý đọc:    summary(), key_points(), glossary(), answer()
"""

from __future__ import annotations

import math
import re
import unicodedata
from datetime import timedelta

# ─── tham số xếp hạng ─────────────────────────────────────────────────────────
HALF_LIFE_HOURS = 72.0          # độ "nguội" của tin theo thời gian
STALE_AFTER_HOURS = 6           # quá hạn này thì trang chủ tự chấm lại
TYPE_WEIGHT = {                 # mức độ cần đưa tin theo loại bài
    "forecast": 8.0,
    "situation": 8.0,
    "advice": 7.0,
    "bulletin": 6.0,
    "notice": 4.0,
    "guide": 5.0,
    "news": 3.0,
}
SENTENCE_SPLIT = re.compile(r"(?<=[.!?;:])\s+|\n+")
TOKEN_RE = re.compile(r"\w+", re.UNICODE)


# ─── tiện ích văn bản ─────────────────────────────────────────────────────────
_RAW_STOPWORDS = """
va và cua của cho trong ngoài trên dưới với để mà thì là các những một hai ba khi nhưng
hay hoặc nếu vì nên rồi đã đang sẽ bị được có không chưa rất quá hơn kém từ đến theo tại
do đó này kia ấy nào gì ai sao bao nhiêu những việc vấn đề cần phải nếu như về ở ra vào
theo cùng cả chỉ còn lại mỗi tuy dù bởi nếu mà cũng vẫn đều rằng thì đây đó kìa
""".split()


def _fold(text: str) -> str:
    """Bỏ dấu tiếng Việt để so khớp không phân biệt dấu."""
    text = (text or "").lower().replace("đ", "d")
    return "".join(c for c in unicodedata.normalize("NFD", text) if unicodedata.category(c) != "Mn")


STOPWORDS = {_fold(w) for w in _RAW_STOPWORDS}


def _tokens(text: str) -> list[str]:
    # Bỏ dấu trước khi tách từ để người dùng gõ không dấu vẫn tra được.
    return [t for t in TOKEN_RE.findall(_fold(text)) if len(t) > 1 and t not in STOPWORDS]


def _sentences(text: str) -> list[str]:
    parts = [s.strip() for s in SENTENCE_SPLIT.split(text or "")]
    out, seen = [], set()
    for s in parts:
        if len(s) < 20:
            continue
        key = _fold(re.sub(r"[^\w\s]", "", s))
        if key in seen:
            continue
        seen.add(key)
        out.append(s)
    return out


def _plain(post) -> str:
    """Văn bản thuần của bài: tóm tắt + nội dung, đã bỏ ký tự định dạng."""
    from core.textfmt import strip_markdown

    return strip_markdown(f"{post.summary or ''}\n{post.content or ''}").strip()


# ─── 1. xếp hạng tin ──────────────────────────────────────────────────────────
def score_post(post, max_views: int = 1, now=None) -> float:
    """Điểm tin nóng 0–100. Công thức tuyến tính có trọng số, không ngẫu nhiên."""
    from django.utils import timezone

    now = now or timezone.now()
    published = post.published_at or post.created_at
    if published is None:
        return 0.0

    # 35 điểm: lượt xem, nén theo logarit để bài cũ không áp đảo vĩnh viễn
    views = max(0, post.views or 0)
    max_views = max(1, max_views)
    view_part = 35.0 * (math.log10(1 + views) / math.log10(1 + max_views))

    # 30 điểm: độ mới, giảm một nửa mỗi HALF_LIFE_HOURS giờ
    age_hours = max(0.0, (now - published).total_seconds() / 3600.0)
    recency_part = 30.0 * math.exp(-age_hours * math.log(2) / HALF_LIFE_HOURS)

    # 10 điểm: biên tập viên ghim nổi bật
    featured_part = 10.0 if post.is_featured else 0.0

    # 8 điểm: gắn với bản tin cảnh báo đang hiệu lực
    alert_part = 8.0 if getattr(post, "alert_id", None) and _alert_is_live(post) else 0.0

    # tối đa 8 điểm: loại bài
    type_part = TYPE_WEIGHT.get(post.post_type, 3.0)

    # tối đa 6 điểm: mức hoàn chỉnh nội dung
    complete_part = (3.0 if post.summary else 0.0) + (3.0 if post.cover else 0.0)

    # tối đa 3 điểm: có cập nhật lại sau khi đăng
    revised_part = 0.0
    if post.updated_at and published and post.updated_at > published + timedelta(days=1):
        revised_part = 3.0

    return round(min(100.0, view_part + recency_part + featured_part + alert_part
                     + type_part + complete_part + revised_part), 2)


def _alert_is_live(post) -> bool:
    from django.utils import timezone

    alert = post.alert
    if alert is None:
        return False
    today = timezone.localdate()
    return alert.status in ("published", "updated") and alert.valid_from <= today <= alert.valid_to


def refresh_hot_scores(queryset=None) -> int:
    """Tính lại điểm cho các bài đã đăng. Trả về số bài đã cập nhật."""
    from django.utils import timezone

    from .models import Post

    qs = queryset if queryset is not None else Post.objects.filter(status="published")
    posts = list(qs.select_related("alert"))
    if not posts:
        return 0
    max_views = max([p.views or 0 for p in posts] + [1])
    now = timezone.now()
    changed = []
    for p in posts:
        value = score_post(p, max_views=max_views, now=now)
        if p.hot_score != value or p.hot_computed_at is None:
            p.hot_score = value
            p.hot_computed_at = now
            changed.append(p)
    if changed:
        Post.objects.bulk_update(changed, ["hot_score", "hot_computed_at"], batch_size=200)
    return len(changed)


def scores_are_stale() -> bool:
    from django.utils import timezone

    from .models import Post

    latest = (Post.objects.filter(status="published")
              .order_by("-hot_computed_at").values_list("hot_computed_at", flat=True).first())
    if latest is None:
        return True
    return (timezone.now() - latest) > timedelta(hours=STALE_AFTER_HOURS)


def hot_posts(limit=4, exclude_ids=()):
    """Các bài điểm cao nhất, đã tự chấm lại nếu số liệu cũ."""
    from .models import Post

    if scores_are_stale():
        refresh_hot_scores()
    qs = Post.objects.filter(status="published").exclude(pk__in=list(exclude_ids) or [-1])
    return list(qs.select_related("category").order_by("-hot_score", "-published_at")[:limit])


# ─── 2. trợ lý đọc bài ────────────────────────────────────────────────────────
def summary(post, max_sentences: int = 3) -> str:
    """Tóm tắt trích rút: chọn câu đại diện nhất, giữ nguyên thứ tự xuất hiện."""
    if post.summary:
        return post.summary.strip()
    sentences = _sentences(_plain(post))
    if not sentences:
        return "Bài viết chưa có nội dung để tóm tắt."
    picked = _rank_sentences(sentences, max_sentences)
    return " ".join(sentences[i] for i in sorted(picked))


def key_points(post, max_points: int = 5) -> list[str]:
    """Các ý chính dạng gạch đầu dòng."""
    sentences = _sentences(_plain(post))
    if not sentences:
        return []
    picked = _rank_sentences(sentences, max_points)
    return [sentences[i] for i in sorted(picked)]


def _rank_sentences(sentences: list[str], count: int) -> list[int]:
    """Xếp hạng câu theo tần suất từ có trọng số IDF và vị trí trong bài."""
    count = max(1, min(count, len(sentences)))
    tokenized = [_tokens(s) for s in sentences]
    df: dict[str, int] = {}
    for toks in tokenized:
        for t in set(toks):
            df[t] = df.get(t, 0) + 1
    total = len(sentences)
    scored: list[tuple[float, int]] = []
    for idx, toks in enumerate(tokenized):
        if not toks:
            scored.append((0.0, idx))
            continue
        weight = 0.0
        for t in toks:
            idf = math.log((total + 1) / (df.get(t, 1) + 0.5))
            weight += idf
        weight /= math.sqrt(len(toks))                 # chuẩn hoá độ dài câu
        weight += 2.0 / (1 + idx)                      # câu đầu thường là nêu vấn đề
        if 60 <= len(sentences[idx]) <= 320:
            weight *= 1.15                             # ưu tiên câu đủ ý, không quá dài
        scored.append((weight, idx))
    scored.sort(reverse=True)
    return [idx for _, idx in scored[:count]]


# Từ điển thuật ngữ chuyên ngành bảo vệ thực vật, giải thích cho người xem phổ thông.
GLOSSARY = {
    "ipm": "Quản lý dịch hại tổng hợp: phối hợp nhiều biện pháp (giống, canh tác, sinh học, hóa học) "
           "thay vì chỉ phun thuốc.",
    "ngưỡng kinh tế": "Mật độ dịch hại mà nếu vượt qua thì thiệt hại mùa màng lớn hơn chi phí phòng trừ.",
    "sinh vật gây hại": "Sinh vật (côn trùng, nấm bệnh, cỏ dại, tuyến trùng…) làm giảm năng suất cây trồng.",
    "thiên địch": "Sinh vật có ích ăn hoặc ký sinh lên sinh vật gây hại, giúp hạn chế dịch tự nhiên.",
    "thuốc bảo vệ thực vật": "Chế phẩm dùng để phòng trừ sinh vật gây hại; phải dùng đúng loại, "
                            "đúng liều và đúng thời gian cách ly.",
    "thời gian cách ly": "Số ngày tối thiểu từ lần phun cuối đến khi thu hoạch để nông sản an toàn.",
    "dự tính": "Nhận định khả năng sinh vật gây hại phát sinh, phát triển trong thời gian tới.",
    "dự báo": "Nhận định định lượng mức độ, phạm vi sinh vật gây hại có thể gây ra trong tương lai.",
    "cấp độ rủi ro": "Mức nguy hại của dịch hại, từ thấp đến rất cao, dùng để quyết định biện pháp.",
    "phun rải": "Biện pháp phun thuốc hoặc rải thuốc trên diện rộng theo kế hoạch.",
    "bệnh đạo ôn": "Bệnh nấm trên lúa, gây vết hình thoi trên lá, nặng có thể lụi cả khóm.",
    "bệnh vàng lùn": "Bệnh do vi-rút lan truyền qua rầy nâu, làm lúa vàng và lùn, không có thuốc chữa.",
    "rầy nâu": "Côn trùng chích hút nhựa lúa, vừa gây cháy rầy vừa là môi giới truyền vi-rút vàng lùn.",
    "sâu cuốn lá": "Sâu non cuốn lá lúa và ăn phần thịt lá phía trong.",
    "sâu keo mùa thu": "Sâu ăn lá ngô rất phàm ăn, gây hại nặng nếu không phát hiện sớm.",
    "tuyến trùng": "Giun tròn ký sinh ở rễ, làm cây còi cọc và dễ nhiễm bệnh khác.",
    "nấm": "Nhóm sinh vật gây phần lớn bệnh cây trồng, phát triển mạnh khi ẩm độ cao.",
    "vi-rút": "Tác nhân gây bệnh nhỏ hơn vi khuẩn, thường lây qua côn trùng môi giới hoặc giống.",
    "cách ly": "Khoảng thời gian hoặc khoảng cách an toàn để tránh lây nhiễm hoặc tồn dư.",
    "cơ cấu mùa vụ": "Bố trí cây trồng và thời vụ trong năm để né dịch hại và tối ưu năng suất.",
    "gieo sạ": "Biện pháp gieo hạt trực tiếp xuống ruộng thay vì cấy mạ.",
    "mật độ": "Số lượng sinh vật gây hại trên một đơn vị diện tích hoặc một khóm cây.",
    "tỷ lệ hại": "Phần trăm cây hoặc diện tích bị sinh vật gây hại.",
    "chỉ số hại": "Chỉ số tổng hợp mức độ và mức phổ biến của sinh vật gây hại.",
    "phòng trừ": "Các biện pháp ngăn ngừa và diệt trừ sinh vật gây hại.",
    "giống kháng": "Giống cây có khả năng chống lại hoặc chịu được một loại dịch hại.",
    "luân canh": "Trồng xen kẽ các loại cây khác nhau trên cùng thửa đất để cắt vòng đời dịch hại.",
    "biện pháp sinh học": "Dùng thiên địch, chế phẩm vi sinh để kiểm soát dịch hại thay cho thuốc hóa học.",
}


def glossary(post, limit: int = 8) -> list[dict]:
    """Tìm các thuật ngữ chuyên môn có trong bài và trả kèm lời giải thích."""
    haystack = " " + _fold(_plain(post) + " " + (post.title or "")) + " "
    found = []
    for term, meaning in GLOSSARY.items():
        key = _fold(term)
        # So khớp theo ranh giới từ để "hại" không khớp bên trong "sinh vật gây hại".
        if re.search(r"(?<!\w)" + re.escape(key) + r"(?!\w)", haystack):
            found.append({"term": _display_term(term), "meaning": meaning})
        if len(found) >= limit:
            break
    return found


def _display_term(term: str) -> str:
    return term[:1].upper() + term[1:]


def define(question: str) -> dict | None:
    """Tra nghĩa một thuật ngữ xuất hiện trong câu hỏi, tra trên toàn từ điển."""
    folded = " " + _fold(question) + " "
    best, best_len = None, 0
    for term, meaning in GLOSSARY.items():
        key = _fold(term)
        if not re.search(r"(?<!\w)" + re.escape(key) + r"(?!\w)", folded):
            continue
        if len(key) > best_len:                 # ưu tiên thuật ngữ dài, cụ thể hơn
            best, best_len = {"term": _display_term(term), "meaning": meaning}, len(key)
    return best


def answer(post, question: str) -> dict:
    """Trả lời câu hỏi dựa trên nội dung bài viết (truy hồi, không bịa thêm)."""
    question = (question or "").strip()
    if not question:
        return {"ok": False, "answer": "Chưa có câu hỏi.", "source": ""}

    # câu hỏi về thuật ngữ
    folded_q = _fold(question)
    if "la gi" in folded_q or "nghia la" in folded_q or folded_q.startswith("giai thich") or "dinh nghia" in folded_q:
        item = define(question)
        if item:
            return {"ok": True, "answer": item["meaning"], "source": f"Từ điển thuật ngữ · {item['term']}"}

    sentences = _sentences(_plain(post))
    if not sentences:
        return {"ok": False, "answer": "Bài viết chưa có nội dung để tra cứu.", "source": ""}

    q_tokens = set(_tokens(question))
    if not q_tokens:
        return {"ok": False, "answer": "Câu hỏi chưa có từ khoá rõ ràng.", "source": ""}

    best, best_idx = 0.0, -1
    for idx, sentence in enumerate(sentences):
        s_tokens = set(_tokens(sentence))
        if not s_tokens:
            continue
        overlap = len(q_tokens & s_tokens)
        if not overlap:
            continue
        # ưu tiên câu chứa nhiều từ khoá, đủ dài để có nghĩa và không quá dài
        value = overlap / math.sqrt(len(s_tokens)) * (1.0 + 0.4 / (1 + idx))
        if len(sentence) < 50:
            value *= 0.45
        # Câu có dấu kết câu là câu văn đầy đủ; mảnh bảng, tiêu đề mục thì không.
        value *= 1.1 if sentence.endswith((".", "!", "?")) else 0.55
        if value > best:
            best, best_idx = value, idx

    if best_idx < 0 or best < 0.05:
        return {
            "ok": False,
            "answer": "Không tìm thấy đoạn nào trong bài trả lời câu hỏi này. "
                      "Bạn thử hỏi bằng từ khoá khác hoặc xem mục ý chính.",
            "source": "",
        }
    return {"ok": True, "answer": sentences[best_idx], "source": "Trích từ nội dung bài viết"}


def brief(post) -> dict:
    """Gói toàn bộ kết quả trợ lý cho một bài, dùng cho giao diện."""
    return {
        "summary": summary(post),
        "points": key_points(post),
        "terms": glossary(post),
    }
