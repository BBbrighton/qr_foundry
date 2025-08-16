# qr_foundry/patches/create_qr_list_rule.py
import frappe

def run():
    """Create QR Rule for QR List doctype so universal buttons appear"""
    if not frappe.db.exists("QR Rule", {"doctype_name": "QR List"}):
        rule = frappe.new_doc("QR Rule")
        rule.doctype_name = "QR List"
        rule.default_link_type = "Direct"
        rule.default_action = "view"
        rule.auto_generate_on_first_save = 0
        rule.save(ignore_permissions=True)
        frappe.log("Created QR Rule for QR List doctype")