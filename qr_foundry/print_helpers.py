from __future__ import annotations
import os
import base64
import frappe
from qr_foundry import api as _self
from qr_foundry.services.qr_ops import compute_and_persist_encoded

def qr_src(doctype: str, name: str) -> str:
    """Get QR image URL for print formats (uses attached image if available)"""
    try:
        # Find existing QR List
        existing = frappe.get_all(
            "QR List",
            filters={"qr_mode": "URL", "target_doctype": doctype, "target_name": name},
            fields=["name", "absolute_file_url"],
            limit=1,
        )
        
        if existing and existing[0].get("absolute_file_url"):
            # Use attached image if available
            return existing[0]["absolute_file_url"]
        
        # Fallback: generate on-demand
        return qr_data_uri(doctype, name)
    except Exception:
        # If anything fails, generate fresh QR
        return qr_data_uri(doctype, name)

def qr_data_uri(doctype: str, name: str) -> str:
    """Generate QR on-demand and return data URI (always fresh)"""
    info = _self.generate_for_doc(doctype, name)
    qr = frappe.get_doc("QR List", info["qr_list"])
    compute_and_persist_encoded(qr)                 # <-- ensure token + encoded_url
    prev = _self.preview_qr_list(info["qr_list"])
    return prev["data_uri"]

def _data_uri(content: bytes) -> str:
    """Convert binary content to data URI."""
    encoded = base64.b64encode(content).decode('utf-8')
    return f"data:image/png;base64,{encoded}"

def embed_file(file_name_or_url: str) -> str:
    """Embed any File (even private) as data-URI for prints. Validates path."""
    if file_name_or_url.startswith("/"):
        file_doc = frappe.get_doc("File", {"file_url": file_name_or_url})
    else:
        file_doc = frappe.get_doc("File", file_name_or_url)

    site_root = frappe.get_site_path()
    file_path = frappe.get_site_path(file_doc.get_full_path())
    # Path traversal guard
    if os.path.commonpath([site_root, file_path]) != site_root:
        frappe.throw("Invalid file path.", title="Security")

    with open(file_path, "rb") as f:
        return _data_uri(f.read())