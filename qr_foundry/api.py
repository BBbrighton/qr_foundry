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

from qr_foundry.security import ensure_generator, ensure_manager, ensure_doctype_is_enabled




@frappe.whitelist()
def preview_qr_list(qr_list_name: str) -> dict:
    ensure_generator()
    qr = frappe.get_doc("QR List", qr_list_name)
    qr.check_permission("read")
    compute_and_persist_encoded(qr)                 # ensures/creates token for Token mode
    data_uri_result = preview_qr_for_qr_list(qr_list_name) # returns {"data_uri": ...}
    return {"data_uri": data_uri_result["data_uri"], "qr_list": qr_list_name}

@frappe.whitelist()
def attach_qr_list(qr_list_name: str) -> dict:
    ensure_generator()
    qr = frappe.get_doc("QR List", qr_list_name)
    qr.check_permission("write")
    out = attach_qr_image_to_qr_list(qr_list_name)  # this should call compute internally or compute already ran above
    out["qr_list"] = qr_list_name
    return out




@frappe.whitelist()
def generate_for_doc(doctype: str, name: str) -> dict:
    """Button from an enabled DocType: find-or-create QR List and generate.
    Stable, idempotent; **no** attachments to the source doc.
    """
    ensure_generator()
    ensure_doctype_is_enabled(doctype)
    if not frappe.db.exists(doctype, name):
        frappe.throw(_("Document not found"))

    # Defaults from QR Rule (if present)
    rule = frappe.get_all(
        "QR Rule", filters={"doctype_name": doctype}, fields=["default_link_type", "default_action"], limit=1
    )
    link_type = (rule[0]["default_link_type"] if rule else "Direct") or "Direct"
    action = (rule[0]["default_action"] if rule else "view") or "view"

    # Find or create QR List row
    existing = frappe.get_all(
        "QR List",
        filters={"qr_mode": "URL", "target_doctype": doctype, "target_name": name},
        fields=["name"],
        limit=1,
    )

    if existing:
        qr_name = existing[0]["name"]
        updates = {"link_type": link_type}
        if frappe.get_meta("QR List").has_field("action"):
            updates["action"] = action
        frappe.db.set_value("QR List", qr_name, updates, update_modified=False)
    else:
        qr = frappe.new_doc("QR List")
        qr.qr_mode = "URL"
        qr.link_type = link_type
        qr.target_doctype = doctype
        qr.target_name = name
        if frappe.get_meta("QR List").has_field("action"):
            qr.action = action
        qr.insert()
        qr_name = qr.name

    return {"qr_list": qr_name}


@frappe.whitelist()
def preview_for_doc(doctype: str, name: str) -> dict:
    ensure_generator()
    ensure_doctype_is_enabled(doctype)
    doc = frappe.get_doc(doctype, name)
    doc.check_permission("read")
    info = generate_for_doc(doctype, name)          # returns {"qr_list": "..."}
    qr = frappe.get_doc("QR List", info["qr_list"])
    compute_and_persist_encoded(qr)                 # <-- ensure token + encoded_url (no fallback)
    prev = preview_qr_list(info["qr_list"])         # existing fn that returns {'data_uri': ...}
    prev["qr_list"] = info["qr_list"]
    return prev


@frappe.whitelist()
def attach_qr_to_doc(doctype: str, name: str) -> dict:
    ensure_generator()
    ensure_doctype_is_enabled(doctype)
    doc = frappe.get_doc(doctype, name)
    doc.check_permission("write")
    info = generate_for_doc(doctype, name)
    qr = frappe.get_doc("QR List", info["qr_list"])
    compute_and_persist_encoded(qr)                 # <-- ensure token + encoded_url
    prev = preview_qr_list(info["qr_list"])
    b64 = prev["data_uri"].split(",", 1)[1]
    png_bytes = base64.b64decode(b64)
    f = save_file(f"QR-{doctype}-{name}.png", png_bytes, doctype, name, decode=False, is_private=1)
    return {"file_url": f.file_url, "file_name": f.name, "qr_list": info["qr_list"]}
