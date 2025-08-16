from __future__ import annotations
import frappe
from frappe.model.document import Document


class QRList(Document):
	def on_trash(self):
		for t in frappe.get_all("QR Token", filters={"qr_list": self.name}, pluck="name"):
			frappe.delete_doc("QR Token", t, ignore_permissions=True, delete_permanently=True)

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
