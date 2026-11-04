# 📐 Tổng quan 19 Mockup Giao diện Hệ thống AgriGov TT&BVTV

**Phiên bản**: v4.2.0-SEC  
**Ngày tạo**: 01/11/2026  
**Design System**: Tailwind CSS Material Design 3 Extended Palette  
**Fonts**: Inter (Display, Headline, Body, Label, Data Tabular)  
**Icons**: Google Material Symbols Outlined  

---

## 🎨 **Design Tokens Cốt lõi**

### **Color Palette**
```
Primary (Green Agriculture):    #00652c → #15803d → #79db8d
Secondary (Amber Warning):      #904d00 → #fe932c → #ffb77d
Tertiary (Red Emergency):       #b20010 → #d82324 → #ffb4ab
Surface Layers (5 steps):       #ffffff → #eff4ff → #e6eeff → #d5e3fd → #dde9ff
```

### **Typography Scale**
- **Display**: 32px / 24px (Headlines chính)
- **Headline**: 20px / 18px / 16px (Tiêu đề phụ)
- **Body**: 15px / 14px / 13px (Nội dung)
- **Label**: 13px / 12px / 11px (Nhãn, Badge, Metadata)
- **Data Tabular**: 13px / Mono (Mã số, Tọa độ, Checksum)

### **Spacing System**
```
space-2xs: 0.125rem (2px)   |  margin:          1rem (16px)
space-xs:  0.25rem  (4px)   |  margin-desktop:  2rem (32px)
space-sm:  0.5rem   (8px)   |  gutter:          1rem (16px)
space-md:  0.75rem  (12px)  |  gutter-desktop:  1.5rem (24px)
space-lg:  1rem     (16px)  |
space-xl:  1.5rem   (24px)  |
space-2xl: 2rem     (32px)  |
space-3xl: 3rem     (48px)  |
```

### **Border Radius**
```
DEFAULT: 0.125rem (2px)   — Subtle, professional
lg:      0.25rem  (4px)   — Standard cards
xl:      0.5rem   (8px)   — Panels, modals
full:    9999px           — Pills, badges, avatars (CRITICAL FIX từ 0.75rem)
```

---

## 📋 **Index 19 Mockup**

| # | Tên Mockup | Module | Mô tả ngắn | Priority |
|---|------------|--------|------------|----------|
| **01** | **Phân hệ 9: Quản trị hệ thống** | `sysadmin` | RBAC matrix, User roster với MSCB/CA badges, SoD permission grid, Audit trail | 🔴 Critical |
| **02** | **Danh sách Biểu mẫu QCVN** | `surveys` | Survey template browser, QCVN metadata cards, Rule engine toggle | 🟡 High |
| **03** | **Chi tiết Biểu mẫu + Modal** | `surveys` | Electronic form canvas, Field-level validation rules, Save/Publish actions | 🟡 High |
| **04** | **Sandbox Simulator (PASS)** | `surveys` | Survey execution test environment, Mock data generator, Validation preview (SUCCESS) | 🟢 Medium |
| **05** | **Sandbox Simulator (FAIL)** | `surveys` | GPS discrepancy detection, Rule engine violation alert (FAIL STATE) | 🟢 Medium |
| **06** | **Video KYC Audit Session** | `surveys` | Live streaming verification interface, Inspector identity watermark, Recording controls | 🟢 Medium |
| **07-11** | **Forensics & EXIF Analysis** | `surveys` | Photo metadata viewer, GPS spoofing detection, Velocity anomaly map, EXIF extraction, Field evidence gallery | 🟢 Medium |
| **12** | **Audit Trail (Normal)** | `sysadmin` | Activity log timeline, User actions, Print management, Normal operation state | 🟡 High |
| **13** | **Audit Trail (LOCKDOWN)** | `sysadmin` | Security incident lockdown view, Red alert banner, Immutable log sealed | 🔴 Critical |
| **14** | **Two-Man Rule Dual CA** | `sysadmin` | Emergency unlock workflow, Dual signature requirement, PKI token verification | 🔴 Critical |
| **15** | **Success: Giải trừ Phong tỏa** | `sysadmin` | Post-unlock success state, Restoration confirmation, Security clearance certificate | 🟡 High |
| **16** | **PDF Viewer: Biên bản CA** | `sysadmin` | A4 official document renderer, Embedded VGCA signature panel, Hash integrity check | 🟡 High |
| **17** | **Danh sách Hồ sơ Thanh tra** | `sysadmin` | Master-detail layout, Inspection dossier table, Contextual sidebar, Photo evidence grid | 🟡 High |
| **18** | **Chi tiết MSVT Xuất khẩu** | `sysadmin` / `catalog` | Production Unit Code (PUC) detail view, GIS map canvas, SPS compliance checklist, e-Phyto QR | 🟡 High |
| **19** | **PDF/A Certificate Viewer** | `sysadmin` / `catalog` | ISO 19005-1 compliant certificate preview, Guilloche watermark, PKI chain visualizer, Security controls | 🟢 Medium |

---

## 🗂️ **Mapping Mockup → Django Module**

### **1. Core Shell & Navigation**
**File**: `templates/base_ui.html`  
**Nội dung**:
- Fixed sidebar navigation (64 cols width, z-50)
- Top header bar với search, alerts badge, user profile
- Dynamic `live_alert` ticker (context processor)
- `current_season` selector
- Permission-based menu rendering (`{% if perms_map.module_name %}`

### **Mockup 01-16: Phân hệ 9 - SysAdmin & Security**

**Module**: `sysadmin/`, `accounts/`  
**Templates cần tạo / update**:

| Mockup | Template Path | View Function | URL Pattern |
|--------|---------------|---------------|-------------|
| 01 | `sysadmin/index.html` | `sysadmin_dashboard` | `/sysadmin/` |
| 01 | `sysadmin/role_matrix.html` | `role_matrix` | `/sysadmin/roles/` |
| 01 | `sysadmin/user_roster.html` | `user_list` | `/sysadmin/users/` |
| 12 | `sysadmin/audit_log.html` | `audit_log` | `/sysadmin/audit/` |
| 13 | `sysadmin/lockdown_alert.html` | `lockdown_view` (alert state) | `/sysadmin/lockdown/` |
| 14 | `sysadmin/two_man_unlock.html` | `two_man_rule_unlock` | `/sysadmin/unlock/<id>/` |
| 15 | `sysadmin/unlock_success.html` | `unlock_success` | `/sysadmin/unlock/<id>/success/` |
| 16 | `sysadmin/pdf_viewer.html` | `pdf_document_viewer` | `/sysadmin/docs/<id>/view/` |
| 17 | `sysadmin/inspection_dossiers.html` | `inspection_dossier_list` | `/sysadmin/inspections/` |

**Models cần có**:
- ✅ `accounts.User` (CustomUser với MSCB, CA token fields)
- ✅ `accounts.RolePermission` (RBAC matrix)
- ✅ `core.AuditLog` (Activity tracking)
- ✅ `sysadmin.LockdownEvent` (Security incident)
- ✅ `sysadmin.InspectionDossier` (#BB-TT-2025/089)

---

### **Mockup 02-06: Electronic Survey & Rule Engine**

**Module**: `surveys/`  
**Templates cần tạo / update**:

| Mockup | Template Path | View Function | URL Pattern |
|--------|---------------|---------------|-------------|
| 02 | `surveys/template_list.html` | `survey_template_list` | `/surveys/templates/` |
| 03 | `surveys/template_detail.html` | `survey_template_detail` | `/surveys/templates/<id>/` |
| 03 | `surveys/partials/rule_modal.html` | (HTMX modal) | `/surveys/templates/<id>/rules/` |
| 04 | `surveys/sandbox.html` | `sandbox_simulator` | `/surveys/sandbox/<template_id>/` |
| 05 | `surveys/sandbox_fail.html` | (Same view, FAIL state) | `/surveys/sandbox/<template_id>/?result=fail` |
| 06 | `surveys/video_kyc.html` | `video_kyc_session` | `/surveys/kyc/<record_id>/` |
| 03 | `surveys/record_detail.html` | `survey_record_detail` | `/surveys/records/<id>/` |
| 03 | `surveys/record_list.html` | `survey_record_list` | `/surveys/records/` |

**Models cần có**:
- ✅ `surveys.SurveyRecord`
- ✅ `surveys.SurveyPoint`
- ✅ `surveys.SurveyTask`
- ✅ `surveys.SurveyPlan`
- ⚠️ **Cần thêm**: `surveys.ValidationRule` (Rule engine logic)

---

### **Mockup 18-19: MSVT (Mã số Vùng trồng) & Certificates**

**Module**: `catalog/`, `sysadmin/`  
**Templates cần tạo**:

| Mockup | Template Path | View Function | URL Pattern |
|--------|---------------|---------------|-------------|
| 18 | `catalog/production_unit_detail.html` | `production_unit_detail` | `/catalog/puc/<code>/` |
| 19 | `catalog/certificate_viewer.html` | `certificate_pdf_viewer` | `/catalog/puc/<code>/certificate/` |

**Models cần có**:
- ⚠️ **Cần tạo**: `catalog.ProductionUnitCode` (MSVT model)
  ```python
  class ProductionUnitCode(models.Model):
      code = models.CharField(max_length=20, unique=True)  # VN-BGO-0082
      area_hectares = models.DecimalField(max_digits=10, decimal_places=2)
      location = models.CharField(max_length=500)
      crop = models.ForeignKey('catalog.Crop', ...)
      issued_at = models.DateTimeField()
      expires_at = models.DateTimeField()
      certificate_pdf_path = models.FileField(upload_to='certificates/')
      sha256_checksum = models.CharField(max_length=64)
      vgca_signature_valid = models.BooleanField(default=False)
  ```

---

### **Mockup 01 (GIS Cockpit) — Đã implement sẵn**

**Module**: `mapview/`  
**Templates**: `mapview/map.html` ✅ (Đã có từ trước)  
**Views**: `mapview.views.map_view` ✅  
**APIs**:
- `/map/api/points/` ✅
- `/map/api/routes/` ✅
- `/map/api/timeline/` ✅

---

### **CMS Public Portal (Mockup 4 từ conversation cũ)**

**Module**: `cms/`  
**Template**: `cms/home.html`  
**Content**:
- Live breaking alert ticker
- Featured bulletin with weekly pest density trend chart
- Technical handbook guide cards
- Pesticide lookup search form
- Planting calendar widget
- Citizen feedback stream

---

## 🛠️ **Chiến lược Triển khai**

### **Phase 1: Foundation (Ngay lập tức)**
1. ✅ Tạo `templates/base_ui.html` (Modern shell)
2. ✅ Update `core/templatetags/ui.py` (Tailwind badge filters)
3. ✅ Fix CSS conflicts: `static/css/leaflet_tailwind_fix.css`
4. ✅ Update `core/context_processors.py` (`live_alert`, `current_season`)

### **Phase 2: High Priority Modules (Tuần 1)**
5. **SysAdmin Dashboard** (Mockup 01)
   - `sysadmin/index.html`
   - `sysadmin/role_matrix.html`
   - `sysadmin/user_roster.html`

6. **Survey Management** (Mockup 02-03)
   - `surveys/template_list.html`
   - `surveys/template_detail.html`
   - `surveys/record_detail.html`

### **Phase 3: Security & Compliance (Tuần 2)**
7. **Audit Trail & Lockdown** (Mockup 12-15)
   - `sysadmin/audit_log.html`
   - `sysadmin/lockdown_alert.html`
   - `sysadmin/two_man_unlock.html`

8. **Inspection Dossiers** (Mockup 17)
   - `sysadmin/inspection_dossiers.html`

### **Phase 4: Advanced Features (Tuần 3)**
9. **MSVT Certificates** (Mockup 18-19)
   - Tạo model `ProductionUnitCode`
   - `catalog/production_unit_detail.html`
   - `catalog/certificate_viewer.html` (PDF/A renderer)

10. **Video KYC & Forensics** (Mockup 06-11)
    - `surveys/video_kyc.html`
    - `surveys/forensics_viewer.html`

### **Phase 5: Polish & Testing (Tuần 4)**
11. Run full test suite: `python manage.py test`
12. Browser compatibility testing (Chrome, Edge, Firefox)
13. Mobile responsive verification
14. Performance optimization (Lazy loading images, CDN caching)

---

## 📐 **Critical Design Specifications**

### **1. Sidebar Navigation**
- **Width**: `w-64` (256px fixed)
- **z-index**: `z-50`
- **Background**: `bg-surface-container-low`
- **Active state**: `bg-primary-container text-on-primary-container rounded-xl`

### **2. Top Header Bar**
- **Height**: `h-16` (64px fixed)
- **Background**: `bg-surface/80 backdrop-blur-xl`
- **Left offset**: `left-64` (matches sidebar)
- **z-index**: `z-40`

### **3. Main Content Area**
- **Left padding**: `pl-64` (sidebar width)
- **Top padding**: `pt-16` (header height)
- **Container padding**: `px-space-xl` (24px horizontal)

### **4. Badge Components**
```html
<!-- Primary Badge -->
<span class="px-2.5 py-1 rounded-full bg-primary-container text-on-primary-container 
             font-label-md text-label-md font-semibold shadow-sm">
  Active
</span>

<!-- CA Signature Badge -->
<span class="inline-flex items-center gap-1.5 px-2.5 py-1 rounded-full 
             bg-surface-container text-on-surface font-label-sm text-label-sm">
  <span class="material-symbols-outlined text-[14px] text-primary">verified</span>
  Ký số VGCA
</span>
```

### **5. Card Layout**
```html
<div class="bg-surface-container-lowest p-space-xl rounded-xl shadow-sm 
            flex flex-col gap-space-md">
  <!-- Card content -->
</div>
```

### **6. Table Style**
- **Header**: `bg-surface-container-low text-on-surface-variant font-label-sm uppercase`
- **Row hover**: `hover:bg-surface-container-low transition-colors`
- **Selected row**: `bg-primary-fixed/20`

---

## ✅ **Checklist Triển khai**

### **Core Infrastructure**
- [ ] `templates/base_ui.html` created
- [ ] `core/templatetags/ui.py` updated with Tailwind filters
- [ ] `static/css/leaflet_tailwind_fix.css` added
- [ ] `core/context_processors.py` updated (`live_alert`, `current_season`)

### **Module: SysAdmin**
- [ ] `sysadmin/index.html` (Dashboard)
- [ ] `sysadmin/role_matrix.html` (RBAC matrix)
- [ ] `sysadmin/user_roster.html` (User list)
- [ ] `sysadmin/audit_log.html` (Activity log)
- [ ] `sysadmin/lockdown_alert.html` (Security incident)
- [ ] `sysadmin/two_man_unlock.html` (Dual CA unlock)
- [ ] `sysadmin/unlock_success.html` (Success state)
- [ ] `sysadmin/pdf_viewer.html` (Document viewer)
- [ ] `sysadmin/inspection_dossiers.html` (Thanh tra list)

### **Module: Surveys**
- [ ] `surveys/template_list.html` (QCVN templates)
- [ ] `surveys/template_detail.html` (Form designer)
- [ ] `surveys/record_detail.html` (Survey execution)
- [ ] `surveys/record_list.html` (Survey queue)
- [ ] `surveys/sandbox.html` (Test simulator)
- [ ] `surveys/video_kyc.html` (Video verification)
- [ ] `surveys/forensics_viewer.html` (EXIF analysis)

### **Module: Catalog (MSVT)**
- [ ] Model `ProductionUnitCode` created
- [ ] `catalog/production_unit_detail.html` (MSVT detail)
- [ ] `catalog/certificate_viewer.html` (PDF/A viewer)

### **Testing**
- [ ] All templates render without errors
- [ ] Permission guards work correctly
- [ ] Mobile responsive on iPhone/Android
- [ ] `python manage.py test` passes 100%

---

## 📞 **Contact & Support**

**Technical Lead**: AgriGov Development Team  
**Design System**: Material Design 3 + AgriGov Custom Tokens  
**Framework**: Django 5.2 + Tailwind CSS CDN  
**Last Updated**: 01/11/2026 03:21 AM GMT+7

---

*Document này là nguồn chân lý duy nhất (Single Source of Truth) cho toàn bộ thiết kế UI/UX của hệ thống AgriGov.*
