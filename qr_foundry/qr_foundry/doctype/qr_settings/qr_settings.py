from __future__ import annotations
import frappe
from frappe.model.document import Document

BTN_NS = "QR Button"

CLIENT_SCRIPT_TEMPLATE = r"""
frappe.ui.form.on("__DT__", {
  refresh: function(frm) {
    const roles = frappe.user_roles || [];
    const can = roles.includes("System Manager") || roles.includes("QR Manager");
    if (!can) return;
    if (frm.is_new()) return;

    frm.add_custom_button(__("__LABEL__"), async () => {
      try {
        frappe.dom.freeze(__("Generating QR..."));
        const r = await frappe.call({
          method: "qr_foundry.api.generate_for_doc",
          args: { doctype: frm.doctype, name: frm.doc.name },
        });
        frappe.show_alert({ message: __("QR ready"), indicator: "green" });
        if (r.message && r.message.absolute_file_url) {
          window.open(r.message.absolute_file_url, "_blank");
        }
      } finally {
        frappe.dom.unfreeze();
      }
    }, __("Actions"));
  }
});
""".strip()


def _client_script_name(dt: str) -> str:
	return f"{BTN_NS}: {dt}"


def _client_script_body(dt: str, label: str) -> str:
	safe_label = (label or "QR").replace('"', '\\"')
	return CLIENT_SCRIPT_TEMPLATE.replace("__DT__", dt).replace("__LABEL__", safe_label)


class QRSettings(Document):
	def on_update(self):
		desired: dict[str, dict] = {}
		for row in self.rules or []:
			dt = getattr(row, "target_doctype", None) or getattr(row, "doctype", None)
			if not row.enabled or not dt:
				continue
			desired[dt] = {
				"label": row.button_label or "QR",
				"link_type": (row.default_link_type or "Direct").strip(),
				"action": (row.default_action or "view").strip(),
				"auto": bool(getattr(row, "auto_generate_on_first_save", 0)),
			}

		for dt, cfg in desired.items():
			name = _client_script_name(dt)
			code = _client_script_body(dt, cfg["label"])

			if frappe.db.exists("Client Script", name):
				cs = frappe.get_doc("Client Script", name)
				cs.enabled = 1
				cs.dt = dt
				cs.view = "Form"
				cs.script = code
				cs.save(ignore_permissions=True)
			else:
				frappe.get_doc(
					{
						"doctype": "Client Script",
						"name": name,
						"dt": dt,
						"view": "Form",
						"enabled": 1,
						"script": code,
					}
				).insert(ignore_permissions=True)

			# server-side defaults cache (QR Rule)
			rule = (
				frappe.get_doc("QR Rule", {"doctype_name": dt})
				if frappe.db.exists("QR Rule", {"doctype_name": dt})
				else frappe.new_doc("QR Rule")
			)
			rule.doctype_name = dt
			rule.default_link_type = cfg["link_type"]
			rule.default_action = cfg["action"]
			rule.auto_generate_on_first_save = 1 if cfg["auto"] else 0
			(rule.save if not rule.is_new() else rule.insert)(ignore_permissions=True)

		# cleanup
		existing = frappe.get_all("Client Script", filters={"name": ["like", f"{BTN_NS}:%"]}, pluck="name")
		for name in existing:
			dt = name.split(": ", 1)[1] if ": " in name else None
			if dt and dt not in desired:
				try:
					frappe.delete_doc("Client Script", name, ignore_permissions=True, ignore_missing=True)
				except Exception:
					frappe.db.set_value("Client Script", name, "enabled", 0)

		stale = frappe.get_all("QR Rule", pluck="doctype_name")
		for dt in stale:
			if dt not in desired:
				try:
					names = frappe.get_all("QR Rule", filters={"doctype_name": dt}, pluck="name")
					for nm in names:
						frappe.delete_doc("QR Rule", nm, ignore_permissions=True, ignore_missing=True)
				except Exception:
					pass
