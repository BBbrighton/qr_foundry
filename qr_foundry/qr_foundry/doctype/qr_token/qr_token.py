import base64, secrets
import frappe
from frappe.model.document import Document
from frappe import _
from frappe.utils import now_datetime

TOKEN_BYTES = 24  # 24 bytes -> ~32 chars base64url


class QRToken(Document):
	def before_insert(self):
		# default status
		if not self.status:
			self.status = "Active"

		# generate token if not provided
		if not self.token:
			raw = secrets.token_bytes(TOKEN_BYTES)
			self.token = base64.urlsafe_b64encode(raw).decode("ascii").rstrip("=")

		# basic validation
		if not self.encoded_content:
			frappe.throw(_("encoded_content is required"))

	def validate(self):
		# immutable encoded_content & qr_list after creation
		if not self.is_new():
			prev = frappe.db.get_value(self.doctype, self.name, ["encoded_content", "qr_list"], as_dict=True)
			if prev:
				if self.encoded_content != prev.encoded_content:
					frappe.throw(
						_("encoded_content is immutable once set. Create a new token to change target.")
					)
				if self.qr_list != prev.qr_list:
					frappe.throw(_("qr_list link is immutable once set."))

		# normalize status if expired or exceeded
		now = now_datetime()
		if self.expires_on and now >= self.expires_on:
			self.status = "Expired"
		if (self.max_uses or 0) > 0 and (self.use_count or 0) >= self.max_uses:
			self.status = "Expired"
