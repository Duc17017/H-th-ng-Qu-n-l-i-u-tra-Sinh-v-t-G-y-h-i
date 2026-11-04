from django import forms

from core.forms import StyledForm, StyledModelForm
from . import models as m


class PostForm(StyledModelForm):
    class Meta:
        model = m.Post
        fields = ["title", "post_type", "category", "summary", "content", "cover", "is_featured", "alert"]
        widgets = {"content": forms.Textarea(attrs={"rows": 14}), "summary": forms.Textarea(attrs={"rows": 3})}

    def clean_cover(self):
        f = self.cleaned_data.get("cover")
        if f and hasattr(f, "size") and f.size > 5 * 1024 * 1024:
            raise forms.ValidationError("Ảnh vượt quá 5 MB.")
        return f


class CategoryForm(StyledModelForm):
    class Meta:
        model = m.Category
        fields = ["name", "slug", "order"]


class NoteForm(StyledForm):
    note = forms.CharField(label="Ý kiến", required=False, widget=forms.Textarea(attrs={"rows": 3}))
