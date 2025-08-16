# qr_foundry/utils/dev.py
import frappe

def nuke_qr_for(dt: str, dn: str):
    for qrl in frappe.get_all("QR List", filters={"target_doctype": dt, "target_name": dn}, pluck="name"):
        for tkn in frappe.get_all("QR Token", filters={"qr_list": qrl}, pluck="name"):
            frappe.delete_doc("QR Token", tkn, ignore_permissions=True, delete_permanently=True)
        frappe.delete_doc("QR List", qrl, ignore_permissions=True, delete_permanently=True)