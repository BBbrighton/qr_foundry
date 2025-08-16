import frappe

def _rule_says_autogen(doctype: str) -> bool:
    return bool(frappe.db.get_value("QR Rule", {"doctype_name": doctype}, "auto_generate_on_first_save"))

def after_insert_autogen(doc, method=None):
    """Create QR on first save if rule enables it. Idempotent."""
    if not getattr(doc, "doctype", None) or not getattr(doc, "name", None):
        return
    if not _rule_says_autogen(doc.doctype):
        return
    try:
        frappe.get_attr("qr_foundry.api.generate_for_doc")(doc.doctype, doc.name)
    except Exception:
        frappe.log_error(frappe.get_traceback(), "QR Foundry: after_insert_autogen")