from __future__ import annotations
import json
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


def _build_role_redirects_by_doctype(role_redirects) -> dict[str, list]:
	"""
	Group role_redirects by target_doctype.
	Returns: { "Sales Order": [...], "Item": [...] }
	"""
	by_doctype: dict[str, list] = {}
	for r in role_redirects or []:
		dt = getattr(r, "target_doctype", None)
		if not dt:
			continue
		if dt not in by_doctype:
			by_doctype[dt] = []
		by_doctype[dt].append({
			"role": r.role,
			"label": r.label,
			"redirect_type": r.redirect_type,
			"redirect_action": getattr(r, "redirect_action", None),
			"custom_url": getattr(r, "custom_url", None),
			"priority": r.priority or 0,
		})

	# Sort each doctype's redirects by priority
	for dt in by_doctype:
		by_doctype[dt].sort(key=lambda x: x.get("priority", 0))

	return by_doctype


class QRSettings(Document):
	def on_update(self):
		# Build role redirects grouped by doctype
		role_redirects_by_dt = _build_role_redirects_by_doctype(self.role_redirects)

		desired: dict[str, dict] = {}
		for row in self.rules or []:
			dt = getattr(row, "target_doctype", None) or getattr(row, "doctype", None)
			if not row.enabled or not dt:
				continue

			# Check if this doctype has role redirects configured
			dt_role_redirects = role_redirects_by_dt.get(dt, [])
			enable_role_redirects = len(dt_role_redirects) > 0

			desired[dt] = {
				"link_type": (row.default_link_type or "Direct").strip(),
				"action": (row.default_action or "view").strip(),
				"auto": bool(getattr(row, "auto_generate_on_first_save", 0)),
				"enable_role_redirects": enable_role_redirects,
				"role_redirects_json": json.dumps(dt_role_redirects) if dt_role_redirects else "[]",
			}

		for dt, cfg in desired.items():
			# Only create/update QR Rules (server-side defaults cache)
			rule = (
				frappe.get_doc("QR Rule", {"doctype_name": dt})
				if frappe.db.exists("QR Rule", {"doctype_name": dt})
				else frappe.new_doc("QR Rule")
			)
			rule.doctype_name = dt
			rule.default_link_type = cfg["link_type"]
			rule.default_action = cfg["action"]
			rule.auto_generate_on_first_save = 1 if cfg["auto"] else 0
			rule.enable_role_redirects = 1 if cfg["enable_role_redirects"] else 0
			rule.role_redirects_json = cfg["role_redirects_json"]
			(rule.save if not rule.is_new() else rule.insert)()

		stale = frappe.get_all("QR Rule", pluck="doctype_name")
		for dt in stale:
			if dt not in desired:
				try:
					names = frappe.get_all("QR Rule", filters={"doctype_name": dt}, pluck="name")
					for nm in names:
						frappe.delete_doc("QR Rule", nm, ignore_missing=True)
				except Exception:
					pass
