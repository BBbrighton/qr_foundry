from __future__ import annotations
import secrets
import frappe
from frappe.utils import get_url, get_url_to_form, get_url_to_list

def build_token_resolver_url(raw_token: str) -> str:
    """Build the resolver URL for a token."""
    return get_url(f"/qr?token={raw_token}")

def _build_target_url_for_qr_list(qr) -> str:
    """Return a relative Desk URL for the QR List target (v15-safe)."""
    dt = qr.target_doctype
    dn = qr.target_name
    action = (getattr(qr, "action", None) or "view").lower()
    if action in ("view", "", None):
        return get_url_to_form(dt, dn)   # /app/<doctype-slug>/<name>
    if action == "list":
        return get_url_to_list(dt)       # /app/<doctype-slug>
    return get_url_to_form(dt, dn)

def issue_token_for_qr_list(qr_list_name: str):
    """
    Create an Active token for this QR List and set encoded_content to the FINAL URL
    (absolute Desk URL). DO NOT store /qr?token=... here.
    """
    qr = frappe.get_doc("QR List", qr_list_name)
    token = secrets.token_urlsafe(32)
    target_rel = _build_target_url_for_qr_list(qr)
    target_abs = get_url(target_rel)

    doc = frappe.get_doc({
        "doctype": "QR Token",
        "qr_list": qr_list_name,
        "token": token,
        "encoded_content": target_abs,   # <-- final destination
        "status": "Active",
    })
    doc.insert(ignore_permissions=True)
    return doc

def ensure_active_token_for_qr_list(qr_list_name: str) -> str:
    """
    Return an active token string; issue one if none exists.
    """
    tok = frappe.get_all(
        "QR Token",
        filters={"qr_list": qr_list_name, "status": "Active"},
        fields=["token"],
        order_by="creation desc",
        limit=1,
    )
    if tok:
        return tok[0]["token"]
    return issue_token_for_qr_list(qr_list_name).token