0) What we’re standardizing (single source of truth)

One canonical function: compute_and_persist_encoded(qr_list_doc) in qr_ops.py

If link_type == "Token" → ensure/issue token → set encoded_url = absolute('/qr?token=…').

Else → build route with your _build_route(...).

Never fallback Token→Direct.

All renderers (Preview/Attach/Print) call that first, then render.

No circular imports: qr_ops.py may import from tokens.py, but tokens.py must NOT import from qr_ops.py.

1) Make token utilities independent (break the cycle)

File: qr_foundry/qr_foundry/services/tokens.py

Replace the file contents with this self-contained version (no imports from qr_ops):

from __future__ import annotations
import frappe
import secrets
from frappe import _
from frappe.utils import get_url

def issue_token_for_qr_list(qr_list_name: str):
    """
    Create a new Active token for this QR List and return the doc.
    Does NOT render/attach a PNG (callers handle that).
    """
    if not frappe.db.exists("DocType", "QR Token"):
        frappe.throw(_("QR Token doctype is not installed."))

    token = secrets.token_urlsafe(32)
    doc = frappe.get_doc({
        "doctype": "QR Token",
        "qr_list": qr_list_name,
        "token": token,
        "status": "Active",
    })
    doc.insert(ignore_permissions=True)
    return doc

def ensure_active_token_for_qr_list(qr_list_name: str) -> str:
    """
    Return an active token string for this QR List, issuing one if none exists.
    """
    tok = frappe.get_all(
        "QR Token",
        filters={"qr_list": qr_list_name, "status": "Active"},
        fields=["name", "token"],
        order_by="creation desc",
        limit=1,
    )
    if tok:
        return tok[0]["token"]

    token_doc = issue_token_for_qr_list(qr_list_name)
    return token_doc.token

def build_token_resolver_url(raw_token: str) -> str:
    """Absolute resolver URL for a token."""
    return get_url(f"/qr?token={raw_token}")


Why: this removes tokens.py -> qr_ops.py imports, so qr_ops.py can safely import ensure_active_token_for_qr_list without circular import.

2) Centralize “compute & persist” (no fallback) + expose QR-List renderers

File: qr_foundry/qr_foundry/services/qr_ops.py

Append or replace the relevant parts with the following (keep your existing _build_route(...) and attach_qr_image_to_qr_list(...) if they already exist; otherwise use these):

from __future__ import annotations
import frappe
from frappe.utils import get_url
from frappe.utils.file_manager import save_file
from qr_foundry.services.tokens import ensure_active_token_for_qr_list, build_token_resolver_url
from qr_foundry.utils.qr import generate_qr_png, make_data_uri

# ---------- core single-source-of-truth ----------

def compute_and_persist_encoded(qr_list_doc) -> str:
    """
    Compute encoded_url for this QR List based on link_type and persist it.
    NO fallback Token→Direct. Returns encoded_url (absolute URL).
    """
    link_type = (qr_list_doc.link_type or "").strip()

    if link_type == "Token":
        raw = ensure_active_token_for_qr_list(qr_list_doc.name)
        encoded = build_token_resolver_url(raw)
    else:
        # Use your existing direct/value/manual route builder
        encoded = _build_route(
            qr_list_doc.target_doctype,
            qr_list_doc.target_name,
            getattr(qr_list_doc, "action", None),
            getattr(qr_list_doc, "report_name", None),
        )
        # Ensure absolute URL for off-site scans
        if not (encoded or "").startswith(("http://", "https://")):
            encoded = get_url(encoded)

    qr_list_doc.db_set("encoded_url", encoded, update_modified=False)
    return encoded

# ---------- QR-List level preview / attach ----------

def preview_qr_for_qr_list(qr_list_name: str) -> str:
    """
    Return a data URI PNG for the given QR List.
    """
    row = frappe.get_doc("QR List", qr_list_name)
    encoded = compute_and_persist_encoded(row)
    label = getattr(row, "label_text", None)
    png = generate_qr_png(encoded, label=label)
    return make_data_uri(png)

def attach_qr_image_to_qr_list(qr_list_name: str, *, file_basename: str | None = None) -> dict:
    """
    Render a PNG for this QR List and attach it to QR List.image (private).
    Returns {file_url, absolute_file_url, encoded_url}.
    """
    row = frappe.get_doc("QR List", qr_list_name)
    encoded = compute_and_persist_encoded(row)
    label = getattr(row, "label_text", None)
    png = generate_qr_png(encoded, label=label)

    # Use a stable filename
    if not file_basename:
        file_basename = f"{row.name}.png"

    # Frappe 15 signature (positional args)
    f = save_file(
        file_basename,  # fname
        png,            # content (bytes)
        "QR List",      # dt
        row.name,       # dn
        decode=False,
        is_private=1,
        df="image",     # attach into the Attach Image field on QR List
    )

    absolute = get_url(f.file_url) if f.file_url else None
    row.db_set("file_url", f.file_url, update_modified=False)
    row.db_set("absolute_file_url", absolute, update_modified=False)

    return {
        "file_url": f.file_url,
        "absolute_file_url": absolute,
        "encoded_url": encoded,
    }

# (optional convenience, if you need a single entrypoint)
def generate_qr_image_for_qr_list(qr_list_name: str) -> dict:
    """Convenience wrapper: compute+render+attach."""
    return attach_qr_image_to_qr_list(qr_list_name)


This gives us form-level Preview/Attach for QR List, using the same compute logic as documents.

3) Fix API endpoints to use the single source of truth

File: qr_foundry/qr_foundry/api.py

Replace the relevant bits with these versions (they’re safe on Frappe 15 and avoid the direct-path leak):

from __future__ import annotations
import base64
import frappe
from frappe import _
from frappe.utils.file_manager import save_file

from qr_foundry.services.qr_ops import (
    preview_qr_for_qr_list,
    compute_and_persist_encoded,
    attach_qr_image_to_qr_list,
)
from qr_foundry.services.tokens import issue_token_for_qr_list

ALLOWED_GENERATOR_ROLES = {"System Manager", "QR Manager"}

def _ensure_can_generate():
    roles = set(frappe.get_roles() or [])
    if not (roles & ALLOWED_GENERATOR_ROLES):
        frappe.throw(_("You are not allowed to generate QR codes."), frappe.PermissionError)

# ---- QR List endpoints (bring back UI functionality)

@frappe.whitelist()
def preview_qr_list(qr_list_name: str) -> dict:
    _ensure_can_generate()
    data_uri = preview_qr_for_qr_list(qr_list_name)
    return {"data_uri": data_uri, "qr_list": qr_list_name}

@frappe.whitelist()
def attach_qr_list(qr_list_name: str) -> dict:
    _ensure_can_generate()
    out = attach_qr_image_to_qr_list(qr_list_name)
    out["qr_list"] = qr_list_name
    return out

# ---- Doc-level endpoints (token-safe)

@frappe.whitelist()
def preview_for_doc(doctype: str, name: str) -> dict:
    """
    Ensure a QR List exists for (doctype, name), then compute (no fallback) and preview.
    """
    _ensure_can_generate()
    info = generate_for_doc(doctype, name)   # your existing idempotent creator; returns {"qr_list": "...", ...}
    qr_name = info["qr_list"]

    # 🔒 ensure encoded_url matches current link_type (and ensure/issue token if Token)
    compute_and_persist_encoded(frappe.get_doc("QR List", qr_name))

    data_uri = preview_qr_for_qr_list(qr_name)
    return {"data_uri": data_uri, "qr_list": qr_name}

@frappe.whitelist()
def attach_qr_to_doc(doctype: str, name: str) -> dict:
    """
    Ensure QR List for (doctype, name), compute (no fallback), render + attach PNG to the target doc.
    """
    _ensure_can_generate()
    doc = frappe.get_doc(doctype, name)
    doc.check_permission("write")

    info = generate_for_doc(doctype, name)
    qr_name = info["qr_list"]

    # 🔒 ensure encoded_url is correct before rendering
    compute_and_persist_encoded(frappe.get_doc("QR List", qr_name))

    # Render for QR List (authoritative PNG) and then also attach the PNG binary to the target doc
    prev = preview_qr_for_qr_list(qr_name)
    b64 = prev.split(",", 1)[1]
    png = base64.b64decode(b64)

    f = save_file(
        f"QR-{doctype}-{name}.png",
        png,
        doctype,
        name,
        decode=False,
        is_private=1,
    )
    return {"file_url": f.file_url, "file_name": f.name, "qr_list": qr_name}


Note: we don’t call issue_token_for_qr_list directly here. compute_and_persist_encoded(...) calls ensure_* internally when link_type is Token. That’s how we avoid Token→Direct fallbacks.

4) Add QR-List form buttons (so users can render from the QR List)

File (new): qr_foundry/qr_foundry/public/js/qr_foundry/qr_list_buttons.js

frappe.ui.form.on("QR List", {
  refresh(frm) {
    if (frm.is_new()) return;

    // Preview
    frm.add_custom_button("Preview QR", async () => {
      try {
        const r = await frappe.call({
          method: "qr_foundry.api.preview_qr_list",
          args: { qr_list_name: frm.doc.name },
        });
        const data_uri = r.message && r.message.data_uri;
        if (!data_uri) return;
        const d = new frappe.ui.Dialog({
          title: "QR Preview",
          size: "large",
          primary_action_label: "Close",
          primary_action() { d.hide(); }
        });
        d.$body.append(`<div style="text-align:center"><img src="${data_uri}" style="max-width: 100%; height:auto"/></div>`);
        d.show();
      } catch (e) {
        frappe.msgprint({ title: __("QR Preview Failed"), message: e.message || e, indicator: "red" });
      }
    }, __("QR Foundry"));

    // (Re)Generate + attach PNG to QR List.image
    frm.add_custom_button("Regenerate & Attach", async () => {
      try {
        const r = await frappe.call({
          method: "qr_foundry.api.attach_qr_list",
          args: { qr_list_name: frm.doc.name },
        });
        if (r.message && r.message.file_url) {
          await frm.reload_doc();
          frappe.show_alert({ message: __("QR image attached"), indicator: "green" });
        }
      } catch (e) {
        frappe.msgprint({ title: __("Attach Failed"), message: e.message || e, indicator: "red" });
      }
    }, __("QR Foundry"));
  },
});


Then include it in hooks (see next step).

5) Ensure the assets are actually loaded (no more 404s)

File: qr_foundry/qr_foundry/hooks.py

Add/update the includes so they point to /assets/... (Frappe 15 serves from there):

# JS assets
app_include_js = [
    "/assets/qr_foundry/js/qr_foundry/index.js",
    "/assets/qr_foundry/js/qr_foundry/qr_list_buttons.js",
]

# If you have no CSS, omit app_include_css entirely.
# app_include_css = ["/assets/qr_foundry/css/qr_foundry.css"]

# Jinja helpers etc. (keep your existing ones here)
# jinja = {"methods": ["qr_foundry.print_helpers.qr_data_uri", ...]}

# If you preload doctypes into bootinfo for universal buttons, keep your boot_session hook as you already had it.
# boot_session = "qr_foundry.boot.boot_session"


Make sure the files exist at apps/qr_foundry/qr_foundry/public/js/qr_foundry/...

Then:

export SITE=<SITE>
bench --site $SITE clear-cache
bench build
bench --site $SITE restart


Quick check in your browser console on a QR List form (saved doc):

// Buttons script loaded?
frappe.modules["qr_foundry"] || true

6) Sanity tests (quick, targeted)

A. Tokenization on a document (e.g., Item/prod01)

bench --site $SITE console

import frappe
from qr_foundry import api

# 1) Ensure fresh start
for n in frappe.get_all("QR List", filters={"target_doctype":"Item","target_name":"prod01"}, pluck="name"):
    frappe.delete_doc("QR List", n, ignore_permissions=True)

# 2) Click path equivalent: preview_for_doc
out = api.preview_for_doc("Item", "prod01")
print(out.keys(), out["qr_list"][:10])

# 3) Inspect the row
qr = frappe.get_doc("QR List", out["qr_list"])
qr.link_type, qr.encoded_url
# Expect: ("Token", "https://<site>/qr?token=...")

# 4) PNG on the doc (attach)
api.attach_qr_to_doc("Item", "prod01")
exit()


B. QR List form renderers

Open any saved QR List row in Desk:

Click QR Foundry → Preview QR → see a modal with the PNG.

Click QR Foundry → Regenerate & Attach → image attaches to image and file_url/absolute_file_url populate.

7) Why this fixes both of your issues

“No way to render on QR List” — You now have:

qr_foundry.api.preview_qr_list and qr_foundry.api.attach_qr_list

Client buttons on QR List to call them.

Both use the same compute_and_persist_encoded single source of truth.

“Docs set to Token still produce Direct” — Every render path calls compute_and_persist_encoded first:

If Token, it JIT-ensures a token and sets encoded_url = /qr?token=... (absolute).

There is no code path that falls back to Direct anymore.

Circular import — Gone. tokens.py is independent; qr_ops.py imports ensure_active_token_for_qr_list one-way.

8) Make it easier to maintain/debug (small, high-impact tweaks)

Guardrails: in compute_and_persist_encoded, if link_type=="Token" and token issuance fails, frappe.throw("No active token…") with a friendly message. That’s fail-closed and obvious.

Debug breadcrumbs: add frappe.logger("qr_foundry").info("compute", {...}) at the start/end of compute_and_persist_encoded (mask the token string!).

Naming: keep all public entrypoints verb-first and consistent: preview_*, attach_*, generate_*.

One-way imports only: api.py → services; services/qr_ops.py → services/tokens.py; services/tokens.py → nothing app-local.

Tests: add one doctest-style check that preview_for_doc returns a data URI containing ";base64," and that the corresponding QR List.encoded_url starts with /qr?token= (or absolute form). That catches regressions fast.

If you apply the snippets above as-is, you’ll (a) have QR rendering directly on the QR List form, and (b) guarantee Token is respected everywhere with no “Direct” leaks — and (c) no more circular import crash.