from django import forms


class StyledFormMixin:
    """Gắn CSS và kiểu nhập liệu phù hợp (ngày, giờ, chọn nhiều) cho mọi form."""

    def _style(self):
        for name, field in self.fields.items():
            w = field.widget
            if isinstance(w, forms.CheckboxInput):
                continue
            css = "form-control"
            if isinstance(w, (forms.Select, forms.SelectMultiple)):
                css = "form-select"
            w.attrs["class"] = (w.attrs.get("class", "") + " " + css).strip()
            if isinstance(field, forms.DateTimeField):
                field.widget = forms.DateTimeInput(attrs=dict(w.attrs, type="datetime-local"), format="%Y-%m-%dT%H:%M")
                field.input_formats = ["%Y-%m-%dT%H:%M", "%Y-%m-%d %H:%M:%S", "%Y-%m-%d %H:%M"]
            elif isinstance(field, forms.DateField):
                field.widget = forms.DateInput(attrs=dict(w.attrs, type="date"), format="%Y-%m-%d")
                field.input_formats = ["%Y-%m-%d", "%d/%m/%Y"]


class StyledModelForm(StyledFormMixin, forms.ModelForm):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self._style()


class StyledForm(StyledFormMixin, forms.Form):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self._style()
