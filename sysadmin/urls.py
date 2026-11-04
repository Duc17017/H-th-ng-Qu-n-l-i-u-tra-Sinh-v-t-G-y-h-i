from django.urls import path

from core.crud import Crud
from . import forms as f
from . import models as m
from . import views as v

app_name = "sysadmin"

configs = Crud("configs", m.SystemConfig, f.ConfigForm, "Cấu hình hệ thống", "system",
               [("Khóa", "key"), ("Giá trị", "value"), ("Mô tả", "description")], search=("key", "description"))
docs = Crud("docs", m.Document, f.DocumentForm, "Tài liệu", "system",
            [("Mã", "code"), ("Tên", "title"), ("Loại", "get_kind_display"), ("Phiên bản áp dụng", "current_version")],
            search=("code", "title"), filters=("kind",))
versions = Crud("versions", m.DocumentVersion, f.VersionForm, "Phiên bản tài liệu", "system",
                [("Tài liệu", "document"), ("Phiên bản", "version"), ("Ngày ban hành", "issued_date"), ("Áp dụng", "is_current")],
                search=("document__code", "version"), filters=("document",), select_related=("document",))

urlpatterns = [
    path("", v.index, name="index"),
    path("audit/", v.audit_log, name="audit"),
    path("logins/", v.login_history, name="logins"),
    path("documents/", v.documents, name="documents"),
    path("documents/download/<int:pk>/", v.document_download, name="document_download"),
    path("backups/", v.backups, name="backups"),
    path("backups/download/<str:name>/", v.backup_download, name="backup_download"),
]
for c in (configs, docs, versions):
    urlpatterns += c.urls("sysadmin")
