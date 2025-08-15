from __future__ import annotations
import re
from urllib.parse import quote

import frappe
from frappe import _
from frappe.utils import get_url
from frappe.utils.file_manager import save_file

from qr_foundry.utils.qr import generate_qr_png, make_data_uri

# ---------- helpers


def _slug(s: str) -> str:
	s = (s or "").strip()
	s = re.sub(r"[^\w\-.]+", "_", s)
	return s[:140] or "qr"


def _build_route(doctype: str, name: str, action: str, report_name: str | None = None) -> str:
	doctype_slug = quote(doctype.lower())
	name_slug = quote(name)
	action = (action or "view").strip().lower()
	base = f"/app/{doctype_slug}/{name_slug}"
	if action == "print":
		return f"{base}?format=Standard&no_letterhead=0"
	return base  # view/edit → base


def _get_field_value(dt: str, dn: str, fieldname: str) -> str:
	try:
		return frappe.db.get_value(dt, dn, fieldname) or ""
	except Exception:
		return ""


# ---------- core computation


def _compute_encoded(row) -> tuple[str, str]:
	mode = (row.qr_mode or "URL").strip()
	label = getattr(row, "label_text", None) or ""

	if mode == "URL":
		custom_route = (getattr(row, "custom_route", "") or "").strip()
		target_url = (getattr(row, "target_url", "") or "").strip()
		dt = getattr(row, "target_doctype", None)
		dn = getattr(row, "target_name", None)
		action = (getattr(row, "action", None) or getattr(row, "target_action", None) or "view").strip()
		if custom_route:
			encoded = custom_route
		elif target_url:
			encoded = target_url
		elif dt and dn:
			encoded = _build_route(dt, dn, action, None)
		else:
			frappe.throw(_("URL mode needs a Target DocType & Document or a Custom URL."))
		if not encoded.startswith(("http://", "https://")):
			encoded = get_url(encoded)
		return encoded, label

	if mode == "Value":
		dt = getattr(row, "value_doctype", None)
		dn = getattr(row, "value_name", None)
		fieldname = getattr(row, "value_field", None)
		if not (dt and dn and fieldname):
			frappe.throw(_("Value mode requires DocType, Document and Field."))
		return str(_get_field_value(dt, dn, fieldname)), label

	if mode == "Manual":
		content = (getattr(row, "manual_content", "") or "").strip()
		if not content:
			frappe.throw(_("Manual mode requires some content."))
		return content, label

	frappe.throw(_("Unsupported mode: {0}").format(mode))


# ---------- attach to QR List only


def attach_qr_image_to_qr_list(qr_list_name: str, encoded: str, label: str | None = None) -> dict:
	row = frappe.get_doc("QR List", qr_list_name)
	png = generate_qr_png(encoded, label=label)
	base = f"{_slug(qr_list_name)}.png"
	f = save_file(base, png, "QR List", qr_list_name, is_private=0, df="image", decode=False)
	updates = {
		"file_url": f.file_url,
		"absolute_file_url": get_url(f.file_url),
		"encoded_url": encoded,
	}
	for k, v in updates.items():
		if frappe.get_meta("QR List").has_field(k):
			row.db_set(k, v, update_modified=False)
	return updates | {"name": f.name}


# ---------- public services


def preview_qr_for_qr_list(qr_list_name: str) -> str:
	row = frappe.get_doc("QR List", qr_list_name)
	encoded, label = _compute_encoded(row)
	png = generate_qr_png(encoded, label=label)
	return make_data_uri(png)


def generate_direct_qr_for_qr_list(qr_list_name: str) -> dict:
	row = frappe.get_doc("QR List", qr_list_name)
	encoded, label = _compute_encoded(row)
	return attach_qr_image_to_qr_list(qr_list_name, encoded, label)


__all__ = ["_build_route", "attach_qr_image_to_qr_list"]
