import frappe

def run():
    names = frappe.get_all("Client Script",
                           filters=[["name","like","QR Button:%"]],
                           pluck="name")
    for nm in names:
        try:
            frappe.delete_doc("Client Script", nm, ignore_permissions=True)
        except Exception:
            # Fallback: disable if deletion fails due to dependencies
            frappe.db.set_value("Client Script", nm, "enabled", 0)