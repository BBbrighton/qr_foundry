import frappe

def run():
    if not frappe.db.exists("Role", "QR Manager"):
        role = frappe.new_doc("Role")
        role.role_name = "QR Manager"
        role.desk_access = 1
        role.save(ignore_permissions=True)