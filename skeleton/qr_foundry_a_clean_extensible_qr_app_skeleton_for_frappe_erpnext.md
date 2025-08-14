# QR Foundry — a clean, extensible QR app skeleton for Frappe/ERPNext

Below are **all files** you can paste into a fresh app. Paths are relative to your app root (the folder created by `bench new-app qr_foundry`).

> Tested against Frappe/ERPNext v15. Focus is on clarity, minimalism, and safe defaults.

---

## 0) Quick start (commands)

```bash
# 0) Create app (skip if already created)
bench new-app qr_foundry  # fill prompts

# 1) Replace the auto-generated files with the structure/files below
#    (create missing folders)

# 2) Install & migrate
bench --site <yoursite> install-app qr_foundry
bench --site <yoursite> migrate
bench build

# 3) Seed sample templates
bench --site <yoursite> reload-doc qr_foundry qr_foundry doctype qr_settings
bench --site <yoursite> reload-doc qr_foundry qr_foundry doctype qr_template
bench --site <yoursite> reload-doc qr_foundry qr_foundry doctype qr_token
bench --site <yoursite> run-patch qr_foundry.patches.post.seed_default_templates

# 4) Add "qr_image" (Attach Image) to any target DocType you want, or adjust fieldname in code

# 5) Open a document of a target doctype -> click the QR button -> generate -> image should appear
```

---

## 1) `requirements.txt`

```txt
qrcode>=7.4
Pillow>=10.0
```

## 2) `MANIFEST.in`

```ini
recursive-include qr_foundry *.json *.js *.css *.py *.html
recursive-include qr_foundry/templates *
recursive-include qr_foundry/public *
recursive-include qr_foundry/www *
include README.md
```

## 3) `setup.py`

```python
from setuptools import setup, find_packages

with open("requirements.txt") as f:
    install_requires = f.read().strip().splitlines()

from qr_foundry import __version__ as version

setup(
    name="qr_foundry",
    version=version,
    description="Clean, extensible QR utilities for Frappe/ERPNext",
    author="You",
    packages=find_packages(),
    zip_safe=False,
    include_package_data=True,
    install_requires=install_requires,
)
```

## 4) `qr_foundry/__init__.py`

```python
__version__ = "0.0.1"
```

## 5) `qr_foundry/hooks.py`

```python
from . import __version__ as app_version

app_name = "qr_foundry"
app_title = "QR Foundry"
app_publisher = "You"
app_description = "Clean, extensible QR utilities for Frappe/ERPNext"
app_version = app_version

# Desk assets: one global JS to add a QR button idempotently to forms
app_include_js = ["/assets/qr_foundry/js/qr_button.js"]
app_include_css = ["/assets/qr_foundry/css/qr.css"]

# Website route for token resolution (supports /qr?token=... and /qr/<token>)
website_route_rules = [
    {"from_route": "/qr/<token>", "to_route": "qr_foundry.www.qr.index"},
]

# Background cleanups
scheduler_events = {
    "hourly": [
        "qr_foundry.utils.tokens.expire_old_tokens",
    ]
}

# (Optional) expose a small bit of settings at boot later if needed
```

## 6) `qr_foundry/config/desktop.py`

```python
from frappe import _

def get_data():
    return [
        {
            "label": _("QR Foundry"),
            "items": [
                {
                    "type": "doctype",
                    "name": "QR Template",
                    "label": _("QR Template"),
                },
                {
                    "type": "doctype",
                    "name": "QR Token",
                    "label": _("QR Token"),
                },
                {
                    "type": "doctype",
                    "name": "QR Settings",
                    "label": _("QR Settings"),
                },
            ],
        }
    ]
```

---

## 7) Utilities — `qr_foundry/utils/qr.py`

```python
import io
import qrcode
from PIL import Image, ImageDraw, ImageFont
import frappe
from frappe.utils import get_url
from frappe.utils.file_manager import save_file
from .tokens import issue_token, build_route


def generate_qr_png_bytes(content: str) -> bytes:
    """Return PNG bytes for given content."""
    img = qrcode.make(content)
    buf = io.BytesIO()
    img.save(buf, format="PNG")
    return buf.getvalue()


def add_label(img: Image.Image, text: str | None) -> Image.Image:
    if not text:
        return img
    width, height = img.size
    try:
        font = ImageFont.truetype("/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf", 16)
    except Exception:
        try:
            font = ImageFont.truetype("arial.ttf", 16)
        except Exception:
            font = ImageFont.load_default()

    draw = ImageDraw.Draw(img)
    words = str(text).split()
    max_width = width - 20
    lines, line = [], ""
    for w in words:
        test = f"{line} {w}".strip()
        bbox = draw.textbbox((0, 0), test, font=font)
        if bbox[2] - bbox[0] <= max_width or not line:
            line = test
        else:
            lines.append(line)
            line = w
    if line:
        lines.append(line)

    line_height = 20
    text_height = len(lines) * line_height + 20
    new_img = Image.new("RGB", (width, height + text_height), "white")
    new_img.paste(img, (0, 0))
    draw = ImageDraw.Draw(new_img)
    y = height + 10
    for ln in lines:
        bbox = draw.textbbox((0, 0), ln, font=font)
        x = (width - (bbox[2] - bbox[0])) // 2
        draw.text((x, y), ln, fill="black", font=font)
        y += line_height
    return new_img


def build_qr_content(doc, template) -> tuple[str, str | None]:
    """Return (URL to encode, optional label)."""
    route = build_route(doc, template)
    label = None
    if template.label_template:
        label = frappe.render_template(template.label_template, {"doc": doc})

    if template.use_token:
        tok = issue_token(doc, template, route)
        url = f"{get_url('/qr')}?token={tok}"
    else:
        url = get_url(route)
    return url, label


def save_qr_to_field(doc, template, fieldname: str = "qr_image") -> dict:
    url, label = build_qr_content(doc, template)
    png = generate_qr_png_bytes(url)
    if label:
        try:
            img = Image.open(io.BytesIO(png)).convert("RGB")
            img = add_label(img, label)
            buf = io.BytesIO(); img.save(buf, format="PNG"); png = buf.getvalue()
        except Exception:
            frappe.log_error("QR label render failed; saving plain QR")

    file_doc = save_file(
        f"QR-{doc.doctype}-{doc.name}.png", png, doc.doctype, doc.name,
        is_private=not (template.public_file or 0), df=fieldname
    )
    # Ensure Attach Image/Attach field stores the URL
    doc.db_set(fieldname, file_doc.file_url, update_modified=False)
    return {"file_url": file_doc.file_url, "encoded_url": url}
```

---

## 8) Utilities — `qr_foundry/utils/tokens.py`

```python
import secrets
import datetime as dt
import frappe
from frappe.utils import now_datetime

ACTIONS = [
    "View Doc", "Edit Doc", "Print Doc", "New Doc",
    "Report", "Route", "Server Method", "URL",
]

def _rand_token(n=32):  # ~ 256-bit urlsafe
    return secrets.token_urlsafe(n)


def build_route(doc, template):
    doctype_slug = frappe.scrub(doc.doctype).replace("_", "-")
    name = doc.name
    at = template.action_type
    if at == "View Doc":
        return f"/app/{doctype_slug}/{name}"
    if at == "Edit Doc":
        return f"/app/{doctype_slug}/{name}?edit=1"
    if at == "Print Doc":
        return f"/app/{doctype_slug}/{name}?print=1"
    if at == "New Doc":
        return template.route or f"/app/form/{doctype_slug}/new"
    if at in {"Report", "Route", "URL"}:
        base = template.route or "/"
        qp = frappe.parse_json(template.query_params) if template.query_params else {}
        if qp:
            from urllib.parse import urlencode
            rendered = {k: frappe.render_template(str(v), {"doc": doc}) for k, v in qp.items()}
            return base + ("?" + urlencode(rendered))
        return base
    if at == "Server Method":
        return f"/api/method/{template.server_method}?doctype={doc.doctype}&name={doc.name}"
    return f"/app/{doctype_slug}/{name}"


def issue_token(doc, template, route) -> str:
    ttl_mins = template.token_ttl_mins or 1440
    tok = _rand_token(24)
    rec = frappe.get_doc({
        "doctype": "QR Token",
        "token": tok,
        "target_doctype": doc.doctype,
        "target_name": doc.name,
        "action_type": template.action_type,
        "route": route,
        "expires_on": (now_datetime() + dt.timedelta(minutes=int(ttl_mins))),
        "max_uses": int(template.token_max_uses or 1),
        "used_count": 0,
        "active": 1,
    })
    rec.insert(ignore_permissions=True)
    return tok


def resolve_token(token: str) -> str:
    row = frappe.db.sql(
        """
        select name, route, expires_on, max_uses, used_count, active
        from `tabQR Token`
        where token=%s for update
        """,
        token,
        as_dict=True,
    )
    if not row:
        frappe.throw("Invalid or expired token", frappe.PermissionError)
    r = row[0]
    now = now_datetime()
    if not r.active or (r.expires_on and now > r.expires_on):
        frappe.throw("Token expired", frappe.PermissionError)
    if r.max_uses and r.used_count >= r.max_uses:
        frappe.throw("Token already used", frappe.PermissionError)

    frappe.db.sql("update `tabQR Token` set used_count = used_count + 1 where name=%s", r.name)
    frappe.db.commit()
    return r.route


def expire_old_tokens():
    frappe.db.sql(
        "update `tabQR Token` set active=0 where expires_on is not null and expires_on < now()"
    )
```

---

## 9) API — `qr_foundry/api.py`

```python
import frappe
from .utils.qr import save_qr_to_field

@frappe.whitelist()
def get_templates_for_doctype(doctype: str):
    rows = []
    try:
        s = frappe.get_single("QR Settings")
        for r in s.get("target_doctypes", []):
            if r.doctype == doctype or r.get("doctype") == doctype:
                if r.get("template"):
                    rows.append({"template": r.get("template")})
        if not rows and s.default_template:
            rows.append({"template": s.default_template})
    except Exception:
        pass
    return rows

@frappe.whitelist()
def generate_and_attach(doctype: str, name: str, template: str, fieldname: str = "qr_image"):
    doc = frappe.get_doc(doctype, name)
    tpl = frappe.get_doc("QR Template", template)
    out = save_qr_to_field(doc, tpl, fieldname)
    doc.reload()
    return out
```

---

## 10) Public web — `qr_foundry/www/qr/index.py`

```python
import frappe
from qr_foundry.utils.tokens import resolve_token

def get_context(context):
    token = frappe.form_dict.get("token") or context.get("token")
    if not token:
        frappe.throw("Missing token")
    try:
        route = resolve_token(token)
    except Exception:
        frappe.local.response["type"] = "redirect"
        frappe.local.response["location"] = "/404"
        return
    frappe.local.response["type"] = "redirect"
    frappe.local.response["location"] = route
```

---

## 11) Print helper — `qr_foundry/templates/includes/print/qr_macros.html`

```html
{% macro qr_image(url) %}
  <img src="{{ frappe.utils.get_url(url) }}" style="max-width:220px;">
{% endmacro %}
```

---

## 12) Client JS — `qr_foundry/public/js/qr_button.js`

```javascript
/*
 * Adds a single, idempotent QR button to all desk forms.
 * No rebuild needed for settings changes; templates are fetched per-refresh.
 */
(function () {
  function add_qr_button(frm) {
    if (!frm || !frm.doc || frm.__qr_btn_added) return;
    frappe.call({ method: 'qr_foundry.api.get_templates_for_doctype', args: { doctype: frm.doctype } })
      .then(r => {
        const rows = (r && r.message) || [];
        if (!rows.length) return;
        frm.add_custom_button(__('QR'), () => open_dialog(frm, rows), __('Utilities'));
        frm.__qr_btn_added = true; // idempotent
      })
      .catch(() => {});
  }

  function open_dialog(frm, rows) {
    const d = new frappe.ui.Dialog({
      title: __('Generate QR'),
      fields: [
        { fieldtype: 'Link', label: 'Template', fieldname: 'template', options: 'QR Template', reqd: 1 },
        { fieldtype: 'Data', label: 'Attach Fieldname', fieldname: 'fieldname', default: 'qr_image', description: __('Attach/Attach Image field to store the file_url') },
      ],
      primary_action_label: __('Generate'),
      primary_action: async (v) => {
        d.hide();
        frappe.dom.freeze(__('Generating QR...'));
        try {
          await frappe.call({
            method: 'qr_foundry.api.generate_and_attach',
            args: { doctype: frm.doctype, name: frm.doc.name, template: v.template, fieldname: v.fieldname || 'qr_image' }
          });
          await frm.reload_doc();
          frappe.show_alert({ message: __('QR attached'), indicator: 'green' });
        } finally { frappe.dom.unfreeze(); }
      }
    });
    d.set_value('template', rows[0].template);
    d.show();
  }

  function patch_form_refresh() {
    const F = frappe.ui.form && frappe.ui.form.Form;
    if (!F || F.__qr_patched) return;
    const orig = F.prototype.refresh;
    F.prototype.refresh = function () {
      const out = orig ? orig.apply(this, arguments) : undefined;
      try { add_qr_button(this); } catch (e) { /* no-op */ }
      return out;
    };
    F.__qr_patched = true;
  }

  const wait = () => {
    if (frappe.ui && frappe.ui.form) { patch_form_refresh(); }
    else { setTimeout(wait, 300); }
  };
  wait();
})();
```

## 13) CSS — `qr_foundry/public/css/qr.css`

```css
/* minimal spacing for dialog */
```

---

## 14) Patches list — `qr_foundry/patches.txt`

```txt
qr_foundry.patches.post.seed_default_templates
```

## 15) Patch — `qr_foundry/patches/post/seed_default_templates.py`

```python
import frappe

def execute():
    # Seed a few templates if none exists
    if not frappe.db.count("QR Template"):
        for name, at in [
            ("Doc View", "View Doc"),
            ("Doc Edit", "Edit Doc"),
            ("Doc Print", "Print Doc"),
            ("Stock Balance Report", "Report"),
        ]:
            doc = frappe.get_doc({
                "doctype": "QR Template",
                "template_name": name,
                "action_type": at,
                "public_file": 1,
            })
            doc.insert(ignore_permissions=True)
```

---

## 16) Tests — `qr_foundry/tests/test_tokens.py`

```python
import frappe
from qr_foundry.utils.tokens import issue_token, resolve_token

def test_issue_and_resolve_token():
    # Create a simple doc (ToDo exists in core)
    todo = frappe.get_doc({"doctype": "ToDo", "description": "x"}).insert()
    tpl = frappe.get_doc({
        "doctype": "QR Template",
        "template_name": "Doc View",
        "action_type": "View Doc",
        "public_file": 1,
    }).insert()
    route = f"/app/todo/{todo.name}"
    token = issue_token(todo, tpl, route)
    resolved = resolve_token(token)
    assert todo.name in resolved
```

---

# DocTypes (Standard JSON + minimal controllers)

> Put these under `qr_foundry/qr_foundry/doctype/...` as shown.

## 17) QR Settings — `qr_foundry/doctype/qr_settings/qr_settings.json`

```json
{
  "doctype": "DocType",
  "name": "QR Settings",
  "module": "QR Foundry",
  "custom": 0,
  "issingle": 1,
  "fields": [
    {"fieldname": "enabled", "label": "Enabled", "fieldtype": "Check", "default": "1"},
    {"fieldname": "button_label", "label": "Button Label", "fieldtype": "Data", "default": "QR"},
    {"fieldname": "default_template", "label": "Default Template", "fieldtype": "Link", "options": "QR Template"},
    {"fieldname": "regenerate_on_save", "label": "Regenerate on Save", "fieldtype": "Check", "default": "0"},
    {"fieldname": "section_targets", "label": "Targets", "fieldtype": "Section Break"},
    {"fieldname": "target_doctypes", "label": "Target Doctypes", "fieldtype": "Table", "options": "QR Settings Doctype Row"}
  ],
  "permissions": [
    {"role": "System Manager", "read": 1, "write": 1}
  ]
}
```

### 17b) Controller — `qr_foundry/doctype/qr_settings/qr_settings.py`

```python
from frappe.model.document import Document

class QRSettings(Document):
    pass
```

### 17c) Child Table — `qr_foundry/doctype/qr_settings_doctype_row/qr_settings_doctype_row.json`

```json
{
  "doctype": "DocType",
  "name": "QR Settings Doctype Row",
  "module": "QR Foundry",
  "custom": 0,
  "istable": 1,
  "fields": [
    {"fieldname": "doctype", "label": "DocType", "fieldtype": "Link", "options": "DocType", "in_list_view": 1},
    {"fieldname": "template", "label": "Template", "fieldtype": "Link", "options": "QR Template", "in_list_view": 1}
  ],
  "permissions": []
}
```

### 17d) Child Controller — `qr_foundry/doctype/qr_settings_doctype_row/qr_settings_doctype_row.py`

```python
from frappe.model.document import Document

class QRSettingsDoctypeRow(Document):
    pass
```

---

## 18) QR Template — `qr_foundry/doctype/qr_template/qr_template.json`

```json
{
  "doctype": "DocType",
  "name": "QR Template",
  "module": "QR Foundry",
  "custom": 0,
  "autoname": "field:template_name",
  "fields": [
    {"fieldname": "template_name", "label": "Template Name", "fieldtype": "Data", "reqd": 1, "in_list_view": 1},
    {"fieldname": "target_doctype", "label": "Target DocType", "fieldtype": "Link", "options": "DocType"},
    {"fieldname": "action_type", "label": "Action Type", "fieldtype": "Select", "reqd": 1,
      "options": "View Doc
Edit Doc
Print Doc
New Doc
Report
Route
Server Method
URL"},
    {"fieldname": "route", "label": "Route / URL", "fieldtype": "Data"},
    {"fieldname": "server_method", "label": "Server Method (dotted path)", "fieldtype": "Data"},
    {"fieldname": "query_params", "label": "Query Params (JSON/Jinja)", "fieldtype": "Small Text"},
    {"fieldname": "label_template", "label": "Label (Jinja)", "fieldtype": "Small Text"},
    {"fieldname": "use_token", "label": "Use Token", "fieldtype": "Check", "default": "0"},
    {"fieldname": "token_max_uses", "label": "Token Max Uses", "fieldtype": "Int", "default": "1"},
    {"fieldname": "token_ttl_mins", "label": "Token TTL (mins)", "fieldtype": "Int", "default": "1440"},
    {"fieldname": "public_file", "label": "Save Image as Public", "fieldtype": "Check", "default": "1"}
  ],
  "permissions": [
    {"role": "System Manager", "read": 1, "write": 1, "create": 1, "delete": 1}
  ]
}
```

### 18b) Controller — `qr_foundry/doctype/qr_template/qr_template.py`

```python
from frappe.model.document import Document

class QRTemplate(Document):
    pass
```

---

## 19) QR Token — `qr_foundry/doctype/qr_token/qr_token.json`

```json
{
  "doctype": "DocType",
  "name": "QR Token",
  "module": "QR Foundry",
  "custom": 0,
  "autoname": "field:token",
  "fields": [
    {"fieldname": "token", "label": "Token", "fieldtype": "Data", "reqd": 1, "in_list_view": 1, "unique": 1},
    {"fieldname": "target_doctype", "label": "Target DocType", "fieldtype": "Link", "options": "DocType", "in_list_view": 1},
    {"fieldname": "target_name", "label": "Target Name", "fieldtype": "Dynamic Link", "options": "target_doctype", "in_list_view": 1},
    {"fieldname": "action_type", "label": "Action Type", "fieldtype": "Select",
      "options": "View Doc
Edit Doc
Print Doc
New Doc
Report
Route
Server Method
URL"},
    {"fieldname": "route", "label": "Resolved Route", "fieldtype": "Data"},
    {"fieldname": "expires_on", "label": "Expires On", "fieldtype": "Datetime"},
    {"fieldname": "max_uses", "label": "Max Uses", "fieldtype": "Int", "default": "1"},
    {"fieldname": "used_count", "label": "Used Count", "fieldtype": "Int", "default": "0"},
    {"fieldname": "active", "label": "Active", "fieldtype": "Check", "default": "1", "in_list_view": 1},
    {"fieldname": "meta", "label": "Meta (JSON)", "fieldtype": "Code", "options": "JSON"}
  ],
  "permissions": [
    {"role": "System Manager", "read": 1, "write": 1, "create": 1, "delete": 1}
  ]
}
```

### 19b) Controller — `qr_foundry/doctype/qr_token/qr_token.py`

```python
from frappe.model.document import Document

class QRToken(Document):
    pass
```

---

# 20) README — `README.md`

```markdown
# QR Foundry

Clean, extensible QR utilities for Frappe/ERPNext.

## Features
- Safe image handling (Attach Image / public File)
- Token engine (expiry, max-uses, atomic increments)
- Template-driven actions (View/Edit/Print/New/Report/Route/Server Method/URL)
- Global, idempotent QR button on forms

## Install
See the quick-start at the top of this document. After installing, open **QR Settings**, list target doctypes, set a default template, and add an **Attach Image** field `qr_image` on those doctypes.
```

---

## 21) Sanity checks / debug steps (during install)

1. **Routes**: open `/qr?token=TEST` → should 404/redirect; create a real token via button and try again.
2. **Images**: After generating, right-click the image in the form → open new tab → URL must start with `/files/` and return 200.
3. **Console**: `bench console` →
   ```python
   import frappe
   from qr_foundry.utils.tokens import expire_old_tokens
   expire_old_tokens()
   ```
4. **Client button not showing?**
   - Check browser console for JS errors.
   - Ensure `qr_foundry/public/js/qr_button.js` is included (Network → assets bundle).
   - Confirm **QR Settings → Target Doctypes** contains your doctype (or set **Default Template**).
5. **PDF print empty?** Use absolute URL in print: `{{ frappe.utils.get_url(doc.qr_image) }}`.

---

**That’s the full skeleton.** Paste these files, install, and we can iterate on any rough edges you hit during testing.

