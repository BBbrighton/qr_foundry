from __future__ import annotations
import frappe
from frappe import _
from frappe.utils import get_url

from qr_foundry.services.qr_ops import attach_qr_image_to_qr_list, _build_route


def _assert_qr_token_present():
	if not frappe.db.exists("DocType", "QR Token"):
		frappe.throw(_("QR Token doctype is not installed."))


def _to_absolute(url_or_route: str) -> str:
	s = (url_or_route or "").strip()
	return s if s.startswith(("http://", "https://")) else get_url(s)


def issue_token_for_qr_list(qr_list_name: str) -> dict:
	_assert_qr_token_present()
	row = frappe.get_doc("QR List", qr_list_name)
	if (row.qr_mode or "URL").strip() != "URL":
		frappe.throw(_("Token link type is available only for URL mode."))

	custom_route = (getattr(row, "custom_route", "") or "").strip()
	target_url = (getattr(row, "target_url", "") or "").strip()
	dt, dn = getattr(row, "target_doctype", None), getattr(row, "target_name", None)
	action = (getattr(row, "action", None) or getattr(row, "target_action", None) or "view").strip()

	if custom_route:
		encoded = custom_route
	elif target_url:
		encoded = target_url
	elif dt and dn:
		encoded = _build_route(dt, dn, action, None)
	else:
		frappe.throw(_("Please select a target (DocType + Document) or provide a Custom URL."))
	encoded = _to_absolute(encoded)

	tok = frappe.get_doc("QR Token", row.qr_token) if getattr(row, "qr_token", None) else None
	if not tok:
		tok = frappe.new_doc("QR Token")
		tok.encoded_content = encoded  # immutable after first issue
		tok.status = "Active"
		tok.insert(ignore_permissions=True)
		row.db_set("qr_token", tok.name, update_modified=False)
	else:
		if (tok.encoded_content or "").strip() != encoded:
			frappe.throw(
				_("This QR already has a token bound to a target. To change the target, rotate the token."),
				title=_("Immutable Target"),
			)
		if (tok.status or "Active") != "Active":
			tok.db_set("status", "Active", update_modified=False)

	resolver_url = f"{get_url('/qr')}?token={tok.token}"
	out = attach_qr_image_to_qr_list(
		row.name, resolver_url, label=(getattr(row, "label_text", None) or tok.token)
	)
	return {
		"qr_token": tok.name,
		"token": tok.token,
		"resolver_url": resolver_url,
		"file_url": out.get("file_url"),
		"absolute_file_url": out.get("absolute_file_url"),
		"encoded_url": out.get("encoded_url"),
	}


def rotate_token_for_qr_list(qr_list_name: str) -> dict:
	_assert_qr_token_present()
	row = frappe.get_doc("QR List", qr_list_name)

	encoded = None
	if getattr(row, "qr_token", None):
		try:
			tok = frappe.get_doc("QR Token", row.qr_token)
			encoded = (tok.encoded_content or "").strip()
		except Exception:
			encoded = None

	if not encoded:
		custom_route = (getattr(row, "custom_route", "") or "").strip()
		target_url = (getattr(row, "target_url", "") or "").strip()
		dt, dn = getattr(row, "target_doctype", None), getattr(row, "target_name", None)
		action = (getattr(row, "action", None) or getattr(row, "target_action", None) or "view").strip()
		if custom_route:
			encoded = custom_route
		elif target_url:
			encoded = target_url
		elif dt and dn:
			encoded = _build_route(dt, dn, action, None)
		else:
			frappe.throw(_("No target to rotate"))
		encoded = _to_absolute(encoded)

	new_tok = frappe.new_doc("QR Token")
	new_tok.encoded_content = encoded
	new_tok.status = "Active"
	new_tok.insert(ignore_permissions=True)

	old = getattr(row, "qr_token", None)
	row.db_set("qr_token", new_tok.name, update_modified=False)
	if old and frappe.db.exists("QR Token", old):
		frappe.db.set_value("QR Token", old, "status", "Revoked", update_modified=False)

	resolver_url = f"{get_url('/qr')}?token={new_tok.token}"
	out = attach_qr_image_to_qr_list(
		row.name, resolver_url, label=(getattr(row, "label_text", None) or new_tok.token)
	)
	return {
		"qr_token": new_tok.name,
		"token": new_tok.token,
		"resolver_url": resolver_url,
		"file_url": out.get("file_url"),
		"absolute_file_url": out.get("absolute_file_url"),
		"encoded_url": out.get("encoded_url"),
	}
