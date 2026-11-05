from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.core.exceptions import PermissionDenied
from django.core.paginator import Paginator
from django.db.models import F, Q
from django.http import JsonResponse
from django.shortcuts import get_object_or_404, redirect, render
from django.utils import timezone
from django.views.decorators.http import require_POST

from core.permissions import has_perm, perm_required
from . import forms as f
from . import insights
from . import models as m

# Số ô tin nổi bật trên trang chủ công khai.
FEATURED_SLOTS = 4


def public_posts():
    return m.Post.objects.filter(status="published").filter(
        Q(published_at__isnull=True) | Q(published_at__lte=timezone.now())).select_related("category")


def home(request):
    """Cổng thông tin.

    Khách chưa đăng nhập chỉ thấy tin nổi bật, cảnh báo và bản tin — đủ để biết
    đơn vị đang cảnh báo gì, nhưng không đọc được toàn bộ kho nội dung.
    Người đã đăng nhập thấy thêm danh sách tin mới đầy đủ.
    """
    from alerts.models import Alert

    today = timezone.localdate()
    posts = public_posts()

    # Tin nổi bật: bài biên tập viên ghim trước, thiếu thì bổ sung bằng bài
    # điểm cao nhất do thuật toán chọn — cổng thông tin không bao giờ trống.
    featured = list(posts.filter(is_featured=True).select_related("category")[:6])
    if len(featured) < FEATURED_SLOTS:
        featured += insights.hot_posts(limit=FEATURED_SLOTS - len(featured),
                                       exclude_ids=[p.pk for p in featured])
    pinned = {p.pk for p in featured}
    hot = insights.hot_posts(limit=4, exclude_ids=pinned)
    # "Tin mới" không lặp lại bài đã nằm trong khối nổi bật / đang quan tâm.
    shown = pinned | {p.pk for p in hot}

    return render(request, "cms/home.html", {
        "featured": featured,
        "hot": hot,
        "latest": posts.exclude(pk__in=shown)[:8] if request.user.is_authenticated else [],
        "bulletins": posts.filter(post_type__in=["bulletin", "forecast", "advice"])[:5],
        "alerts": Alert.objects.filter(status__in=["published", "updated"], valid_from__lte=today, valid_to__gte=today)
                       .select_related("pest", "crop").prefetch_related("divisions")[:5],
        "categories": m.Category.objects.all(),
        "is_guest": not request.user.is_authenticated,
    })


def post_list(request):
    """Danh sách tin: chỉ tiêu đề công khai, nội dung cần đăng nhập."""
    qs = public_posts()
    t, c, q = request.GET.get("type"), request.GET.get("cat"), request.GET.get("q", "").strip()
    if t:
        qs = qs.filter(post_type=t)
    if c:
        qs = qs.filter(category__slug=c)
    if q:
        qs = qs.filter(Q(title__icontains=q) | Q(summary__icontains=q) | Q(content__icontains=q))
    return render(request, "cms/post_list.html", {
        "page": Paginator(qs, 12).get_page(request.GET.get("page")), "types": m.Post.TYPES,
        "categories": m.Category.objects.all(), "q": q, "t": t, "c": c,
        "is_guest": not request.user.is_authenticated})


@login_required
def post_public(request, slug):
    """Chi tiết bài viết. Bắt buộc đăng nhập — khách được chuyển tới trang đăng nhập
    rồi quay lại đúng bài này (LOGIN_URL có ?next=)."""
    post = get_object_or_404(m.Post, slug=slug)
    # Người có quyền quản lý nội dung được xem trước bài chưa đăng
    if not post.is_public and not has_perm(request.user, "cms", "edit"):
        raise PermissionDenied
    if post.is_public:
        m.Post.objects.filter(pk=post.pk).update(views=F("views") + 1)
        post.refresh_from_db(fields=["views"])
        insights.refresh_hot_scores(m.Post.objects.filter(pk=post.pk))
    related = public_posts().filter(post_type=post.post_type).exclude(pk=post.pk)[:4]
    return render(request, "cms/post_public.html", {
        "post": post, "related": related, "assistant": insights.brief(post)})


@login_required
@require_POST
def post_ask(request, slug):
    """Trợ lý đọc bài: trả lời câu hỏi dựa trên chính nội dung bài viết."""
    post = get_object_or_404(m.Post, slug=slug)
    if not post.is_public and not has_perm(request.user, "cms", "edit"):
        raise PermissionDenied
    result = insights.answer(post, request.POST.get("question", ""))
    return JsonResponse(result)


# ------------------------------------------------------------ quản trị nội dung
@perm_required("cms", "view")
def manage_list(request):
    qs = m.Post.objects.select_related("author", "category")
    if request.GET.get("status"):
        qs = qs.filter(status=request.GET["status"])
    if request.GET.get("type"):
        qs = qs.filter(post_type=request.GET["type"])
    q = request.GET.get("q", "").strip()
    if q:
        qs = qs.filter(title__icontains=q)
    if request.user.role == "editor":
        qs = qs.filter(Q(author=request.user) | Q(status__in=["review", "approved", "published"]))
    return render(request, "cms/manage_list.html", {
        "page": Paginator(qs, 20).get_page(request.GET.get("page")), "statuses": m.Post.STATUSES, "types": m.Post.TYPES,
        "can_create": has_perm(request.user, "cms", "create"), "q": q})


@perm_required("cms", "view")
def manage_detail(request, pk):
    post = get_object_or_404(m.Post, pk=pk)
    u = request.user
    return render(request, "cms/manage_detail.html", {
        "post": post, "revisions": post.revisions.select_related("user"), "note_form": f.NoteForm(),
        "can_edit": post.editable and has_perm(u, "cms", "edit"),
        "can_submit": post.status in ("draft", "unpublished") and has_perm(u, "cms", "edit"),
        "can_review": post.status == "review" and has_perm(u, "cms", "confirm"),
        "can_publish": post.status == "approved" and has_perm(u, "cms", "approve"),
        "can_unpublish": post.status == "published" and has_perm(u, "cms", "approve"),
        "can_revise": post.status == "published" and has_perm(u, "cms", "edit"),
    })


def _save_rev(post, action, user, note=""):
    m.PostRevision.objects.create(post=post, version=post.version, action=action, title=post.title,
                                  content=post.content, note=note, user=user)


def _form(request, post):
    form = f.PostForm(request.POST or None, request.FILES or None, instance=post)
    if request.method == "POST" and form.is_valid():
        obj = form.save(commit=False)
        if post is None:
            obj.author = request.user
        obj.save()
        _save_rev(obj, "edit" if post else "create", request.user)
        messages.success(request, "Đã lưu bài viết.")
        return redirect("cms:manage_detail", pk=obj.pk)
    return render(request, "cms/post_form.html", {"form": form, "post": post})


@perm_required("cms", "create")
def manage_create(request):
    return _form(request, None)


@perm_required("cms", "edit")
def manage_edit(request, pk):
    post = get_object_or_404(m.Post, pk=pk)
    if not post.editable:
        messages.error(request, "Bài viết đang chờ duyệt hoặc đã đăng. Hãy gỡ bài / tạo bản điều chỉnh trước khi sửa.")
        return redirect("cms:manage_detail", pk=pk)
    return _form(request, post)


@require_POST
@perm_required("cms", "view")  # quyền chi tiết theo từng hành động được kiểm tra bên trong
def manage_action(request, pk, action):
    post = get_object_or_404(m.Post, pk=pk)
    u, note = request.user, request.POST.get("note", "").strip()
    flows = {
        "submit": ({"draft", "unpublished"}, "review", ("cms", "edit")),
        "approve": ({"review"}, "approved", ("cms", "confirm")),
        "return": ({"review"}, "draft", ("cms", "confirm")),
        "publish": ({"approved"}, "published", ("cms", "approve")),
        "unpublish": ({"published"}, "unpublished", ("cms", "approve")),
        "revise": ({"published"}, "unpublished", ("cms", "edit")),
    }
    if action not in flows:
        raise PermissionDenied
    allowed, to, (mod, act) = flows[action]
    if not has_perm(u, mod, act):
        raise PermissionDenied
    if post.status not in allowed:
        messages.error(request, "Trạng thái bài viết không cho phép thao tác này.")
        return redirect("cms:manage_detail", pk=pk)
    if action == "return" and not note:
        messages.error(request, "Cần nhập lý do trả lại.")
        return redirect("cms:manage_detail", pk=pk)
    post.status = to
    if action in ("approve", "return"):
        post.reviewed_by, post.review_note = u, note
    if action == "publish":
        post.published_at = timezone.now()
    if action == "revise":
        post.version += 1
    post.save()
    _save_rev(post, action, u, note)
    messages.success(request, "Đã cập nhật trạng thái bài viết.")
    return redirect("cms:manage_detail", pk=pk)


# ------------------------------------------------------------ tin nóng ở cổng
@perm_required("cms", "view")
def hot_board(request):
    """Bảng tin nóng: xem điểm thuật toán chấm và ghim lên cổng thông tin."""
    insights.refresh_hot_scores()
    qs = (m.Post.objects.filter(status="published")
          .select_related("category", "author")
          .order_by("-hot_score", "-published_at"))
    return render(request, "cms/hot_board.html", {
        "page": Paginator(qs, 25).get_page(request.GET.get("page")),
        "can_feature": has_perm(request.user, "cms", "edit"),
        "half_life": insights.HALF_LIFE_HOURS,
    })


@require_POST
@perm_required("cms", "edit")
def hot_toggle_feature(request, pk):
    """Ghim / bỏ ghim một bài lên khối tin nổi bật của cổng thông tin."""
    post = get_object_or_404(m.Post, pk=pk)
    post.is_featured = not post.is_featured
    post.save(update_fields=["is_featured", "updated_at"])
    insights.refresh_hot_scores(m.Post.objects.filter(pk=post.pk))
    messages.success(request, "Đã ghim lên cổng thông tin." if post.is_featured
                     else "Đã bỏ ghim khỏi cổng thông tin.")
    return redirect(request.POST.get("next") or "cms:hot_board")
