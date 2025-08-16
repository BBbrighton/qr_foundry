import frappe


# call requires login
@frappe.whitelist()
def ping(name: str | None = None) -> dict:
	"""Minimal test endpoint. Returns who you are, site url, and server time."""
	return {
		"ok": True,
		"name": name or frappe.session.user,
		"site": frappe.local.site,
		"now": frappe.utils.now(),
	}


# call works without login (guest)
@frappe.whitelist(allow_guest=True)
def ping_guest(name: str = "world") -> dict:
	return {
		"ok": True,
		"name": name,
		"site": frappe.local.site,
		"now": frappe.utils.now(),
		"guest": True,
	}
