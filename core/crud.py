"""CRUD dùng chung: sinh các view danh sách / tạo / sửa / xóa / chi tiết có phân quyền và nhật ký."""
from django.contrib import messages
from django.core.exceptions import PermissionDenied
from django.core.paginator import Paginator
from django.db.models import ProtectedError, Q
from django.shortcuts import get_object_or_404, redirect, render
from django.urls import path, reverse

from .audit import history_for
from .permissions import has_perm, perm_required


class Crud:
    def __init__(self, key, model, form, title, module, columns, search=(), filters=(),
                 list_qs=None, delete=True, order=None, can_edit=None, extra_ctx=None, select_related=()):
        self.key = key
        self.model = model
        self.form = form
        self.title = title
        self.module = module
        self.columns = columns          # [(label, attr_or_callable)]
        self.search = search
        self.filters = filters          # [field names] lọc theo FK/choice
        self.list_qs = list_qs
        self.delete_enabled = delete
        self.order = order
        self.can_edit = can_edit        # callable(user, obj) -> bool
        self.extra_ctx = extra_ctx
        self.select_related = select_related
        self.app_ns = None

    # ---- helpers
    def url(self, name, *args):
        return reverse(f"{self.app_ns}:{self.key}_{name}", args=args)

    def queryset(self, request):
        qs = self.list_qs(request) if self.list_qs else self.model.objects.all()
        if self.select_related:
            qs = qs.select_related(*self.select_related)
        if self.order:
            qs = qs.order_by(*self.order)
        return qs

    def _cell(self, obj, attr):
        if callable(attr):
            return attr(obj)
        v = obj
        for part in attr.split("."):
            v = getattr(v, part, None)
            if callable(v):
                v = v()
            if v is None:
                break
        if isinstance(v, bool):
            return "Có" if v else "Không"
        return v

    def _filter_defs(self, qs):
        defs = []
        for name in self.filters:
            f = self.model._meta.get_field(name)
            if f.choices:
                opts = list(f.choices)
            elif f.is_relation:
                opts = [(o.pk, str(o)) for o in f.related_model.objects.all()[:500]]
            elif f.get_internal_type() == "BooleanField":
                opts = [("1", "Có"), ("0", "Không")]
            else:
                continue
            defs.append((name, f.verbose_name, opts))
        return defs

    def _apply_filters(self, request, qs):
        for name in self.filters:
            val = request.GET.get(name)
            if val in (None, ""):
                continue
            f = self.model._meta.get_field(name)
            if f.get_internal_type() == "BooleanField":
                qs = qs.filter(**{name: val == "1"})
            else:
                qs = qs.filter(**{name: val})
        return qs

    # ---- views
    def list_view(self, request):
        qs = self.queryset(request)
        q = request.GET.get("q", "").strip()
        if q and self.search:
            cond = Q()
            for s in self.search:
                cond |= Q(**{f"{s}__icontains": q})
            qs = qs.filter(cond)
        qs = self._apply_filters(request, qs)
        page = Paginator(qs, 25).get_page(request.GET.get("page"))
        rows = []
        for obj in page.object_list:
            rows.append({
                "obj": obj,
                "cells": [self._cell(obj, a) for _, a in self.columns],
                "editable": has_perm(request.user, self.module, "edit") and (not self.can_edit or self.can_edit(request.user, obj)),
                "edit_url": self.url("edit", obj.pk),
                "delete_url": self.url("delete", obj.pk),
                "detail_url": self.url("detail", obj.pk),
            })
        ctx = {
            "crud": self, "page": page, "rows": rows, "q": q,
            "headers": [h for h, _ in self.columns],
            "filter_defs": self._filter_defs(qs),
            "can_create": has_perm(request.user, self.module, "create"),
            "create_url": self.url("create"),
        }
        if self.extra_ctx:
            ctx.update(self.extra_ctx(request) or {})
        return render(request, "crud/list.html", ctx)

    def _form_view(self, request, obj=None):
        form = self.form(request.POST or None, request.FILES or None, instance=obj, **self._form_kwargs(request))
        if request.method == "POST" and form.is_valid():
            saved = form.save(commit=False)
            if hasattr(saved, "set_audit_user"):
                saved.set_audit_user(request.user)
            for attr in ("created_by",):
                if obj is None and hasattr(saved, attr) and getattr(saved, attr + "_id", None) is None:
                    setattr(saved, attr, request.user)
            saved.save()
            form.save_m2m()
            messages.success(request, "Đã lưu dữ liệu thành công.")
            return redirect(self.url("detail", saved.pk))
        return render(request, "crud/form.html", {
            "crud": self, "form": form, "obj": obj,
            "title": ("Chỉnh sửa " if obj else "Thêm mới ") + self.title.lower(),
            "back_url": self.url("list"),
        })

    def _form_kwargs(self, request):
        try:
            import inspect

            if "user" in inspect.signature(self.form.__init__).parameters:
                return {"user": request.user}
        except (TypeError, ValueError):
            pass
        return {}

    def create_view(self, request):
        if not has_perm(request.user, self.module, "create"):
            raise PermissionDenied
        return self._form_view(request)

    def edit_view(self, request, pk):
        if not has_perm(request.user, self.module, "edit"):
            raise PermissionDenied
        obj = get_object_or_404(self.queryset(request), pk=pk)
        if self.can_edit and not self.can_edit(request.user, obj):
            messages.error(request, "Bản ghi ở trạng thái không cho phép chỉnh sửa.")
            return redirect(self.url("detail", pk))
        return self._form_view(request, obj)

    def delete_view(self, request, pk):
        if not self.delete_enabled or not has_perm(request.user, self.module, "edit"):
            raise PermissionDenied
        obj = get_object_or_404(self.queryset(request), pk=pk)
        if self.can_edit and not self.can_edit(request.user, obj):
            messages.error(request, "Bản ghi ở trạng thái không cho phép xóa.")
            return redirect(self.url("detail", pk))
        if request.method == "POST":
            try:
                obj.delete()
                messages.success(request, "Đã xóa bản ghi.")
                return redirect(self.url("list"))
            except ProtectedError:
                messages.error(request, "Không thể xóa vì bản ghi đang được sử dụng ở dữ liệu khác.")
                return redirect(self.url("detail", pk))
        return render(request, "crud/confirm_delete.html", {"crud": self, "obj": obj, "back_url": self.url("detail", pk)})

    def detail_view(self, request, pk):
        obj = get_object_or_404(self.queryset(request), pk=pk)
        fields = []
        for f in obj._meta.fields:
            if f.name in ("password",):
                continue
            val = getattr(obj, f"get_{f.name}_display")() if f.choices else getattr(obj, f.name)
            if isinstance(val, bool):
                val = "Có" if val else "Không"
            fields.append((f.verbose_name, val))
        ctx = {
            "crud": self, "obj": obj, "fields": fields,
            "history": history_for(obj),
            "can_edit": has_perm(request.user, self.module, "edit") and (not self.can_edit or self.can_edit(request.user, obj)),
            "can_delete": self.delete_enabled and has_perm(request.user, self.module, "edit") and (not self.can_edit or self.can_edit(request.user, obj)),
            "back_url": self.url("list"),
            "edit_url": self.url("edit", obj.pk),
            "delete_url": self.url("delete", obj.pk),
        }
        return render(request, "crud/detail.html", ctx)

    def urls(self, app_ns):
        self.app_ns = app_ns
        m, v = self.module, perm_required
        k = self.key
        return [
            path(f"{k}/", v(m, "view")(self.list_view), name=f"{k}_list"),
            path(f"{k}/new/", v(m, "create")(self.create_view), name=f"{k}_create"),
            path(f"{k}/<int:pk>/", v(m, "view")(self.detail_view), name=f"{k}_detail"),
            path(f"{k}/<int:pk>/edit/", v(m, "edit")(self.edit_view), name=f"{k}_edit"),
            path(f"{k}/<int:pk>/delete/", v(m, "edit")(self.delete_view), name=f"{k}_delete"),
        ]
