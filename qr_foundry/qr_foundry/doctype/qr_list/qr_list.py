from __future__ import annotations
import frappe
from frappe.model.document import Document


class QRList(Document):
	def on_trash(self):
		"""Cleanup when a QR List row is deleted:
		- If a linked QR Token exists:
		    - delete it if there are no scan logs
		    - else, set status = Revoked (preserve audit trail)
		"""
		self._cleanup_qr_token()

	# ---- helpers

	def _cleanup_qr_token(self):
		token_name = getattr(self, "qr_token", None)
		if not token_name:
			return

		if not frappe.db.exists("QR Token", token_name):
			return

		# Does this token have any scan logs?
		has_logs = frappe.db.exists("QR Scan Log", {"token": token_name})

		try:
			if has_logs:
				# Keep history, just revoke
				frappe.db.set_value("QR Token", token_name, "status", "Revoked", update_modified=False)
			else:
				# No history -> delete token record
				frappe.delete_doc("QR Token", token_name, ignore_permissions=True, force=1)
		except Exception:
			frappe.log_error(frappe.get_traceback(), "QR Foundry: token cleanup on QR List delete")

@frappe.whitelist()
def get_value_fields(doctype):
	"""Get list of fields that can be used for QR Value mode encoding."""
	if not doctype:
		return []
	
	try:
		meta = frappe.get_meta(doctype)
		# Include common field types suitable for QR encoding
		suitable_fieldtypes = [
			"Data", "Small Text", "Text", "Int", "Float", "Currency", 
			"Percent", "Phone", "Email", "URL", "Barcode", "Code"
		]
		
		fields = []
		for field in meta.fields:
			if field.fieldtype in suitable_fieldtypes and not field.hidden:
				fields.append({
					"label": f"{field.label or field.fieldname} ({field.fieldtype})",
					"value": field.fieldname
				})
		
		# Sort by label for better UX
		fields.sort(key=lambda x: x["label"])
		return fields
	except Exception:
		return []
