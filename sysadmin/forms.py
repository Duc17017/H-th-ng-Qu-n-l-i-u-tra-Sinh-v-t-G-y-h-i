from django import forms

from core.forms import StyledForm, StyledModelForm
from . import models as m


class ConfigForm(StyledModelForm):
    class Meta:
        model = m.SystemConfig
        fields = ["key", "value", "description"]


class DocumentForm(StyledModelForm):
    class Meta:
        model = m.Document
        fields = ["code", "title", "kind", "description"]


class VersionForm(StyledModelForm):
    class Meta:
        model = m.DocumentVersion
        fields = ["document", "version", "file", "issued_date", "note", "is_current"]

    def clean_file(self):
        f = self.cleaned_data.get("file")
        if f and hasattr(f, "size") and f.size > 20 * 1024 * 1024:
            raise forms.ValidationError("Tệp vượt quá 20 MB.")
        if f and hasattr(f, "name"):
            ext = f.name.lower().rsplit(".", 1)[-1] if "." in f.name else ""
            if ext not in ("pdf", "doc", "docx", "xls", "xlsx", "ppt", "pptx", "png", "jpg", "jpeg", "txt"):
                raise forms.ValidationError("Định dạng tệp không được hỗ trợ.")
        return f


class ConfirmRestoreForm(StyledForm):
    name = forms.CharField(widget=forms.HiddenInput)
    confirm = forms.CharField(label="Gõ KHOI PHUC để xác nhận")

    def clean_confirm(self):
        if self.cleaned_data["confirm"].strip().upper() != "KHOI PHUC":
            raise forms.ValidationError("Chưa đúng cụm xác nhận.")
        return self.cleaned_data["confirm"]
