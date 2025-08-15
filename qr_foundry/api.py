from __future__ import annotations
import frappe
from frappe import _

from qr_foundry.services.qr_ops import (
	preview_qr_for_qr_list,
	generate_direct_qr_for_qr_list,
)
from qr_foundry.services.tokens import issue_token_for_qr_list

ALLOWED_GENERATOR_ROLES = {"System Manager", "QR Manager"}


def _ensure_can_generate():
	roles = set(frappe.get_roles() or [])
	if not (roles & ALLOWED_GENERATOR_ROLES):
		frappe.throw(_("Not permitted."))


def _ensure_saved(docname: str, doctype: str = "QR List"):
	if not frappe.db.exists(doctype, docname):
		frappe.throw(_("Please save the document first."))


@frappe.whitelist()
def preview_qr_list(name: str) -> dict:
	_ensure_can_generate()
	_ensure_saved(name, "QR List")
	return {"data_uri": preview_qr_for_qr_list(name)}


@frappe.whitelist()
def generate_qr_list(name: str) -> dict:
	"""Generate on a QR List row: if URL+Token -> tokenized; else direct/value/manual."""
	_ensure_can_generate()
	_ensure_saved(name, "QR List")

	row = frappe.get_doc("QR List", name)
	qr_mode = (row.qr_mode or "URL").strip()
	link_type = (getattr(row, "link_type", "Direct") or "Direct").strip()

	if qr_mode == "URL" and link_type == "Token":
		out = issue_token_for_qr_list(name)
	else:
		out = generate_direct_qr_for_qr_list(name)

	return {
		"qr_list": name,
		"file_url": out.get("file_url"),
		"absolute_file_url": out.get("absolute_file_url"),
		"encoded_url": out.get("encoded_url"),
		"token": out.get("token"),
		"qr_token": out.get("qr_token"),
	}


@frappe.whitelist()
def generate_for_doc(doctype: str, name: str) -> dict:
	"""Button from an enabled DocType: find-or-create QR List and generate.
	Stable, idempotent; **no** attachments to the source doc.
	"""
	_ensure_can_generate()
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
		qr.insert(ignore_permissions=True)
		qr_name = qr.name

	# Generate on QR List
	if link_type == "Token":
		out = issue_token_for_qr_list(qr_name)
	else:
		out = generate_direct_qr_for_qr_list(qr_name)

	out["qr_list"] = qr_name
	return out
