window.qr_foundry = window.qr_foundry || {};

window.qr_foundry.user_has_qr_role = function () {
  const roles = (frappe.boot && frappe.boot.user && frappe.boot.user.roles) || [];
  return roles.includes("System Manager") || roles.includes("QR Manager") || roles.includes("QR User");
};

window.qr_foundry.user_is_sysmgr = function () {
  const roles = (frappe.boot && frappe.boot.user && frappe.boot.user.roles) || [];
  return roles.includes("System Manager");
};

window.qr_foundry.add_qr_buttons = function(frm) {
  // Preview button
  frm.add_custom_button("Preview QR", () => {
    frappe.call({
      method: "qr_foundry.api.preview_for_doc",
      args: { doctype: frm.doc.doctype, name: frm.doc.name },
      callback: function(r) {
        if (r.message && r.message.data_uri) {
          let d = new frappe.ui.Dialog({
            title: __("QR Preview"),
            size: "large",
            primary_action_label: __("Close"),
            primary_action() { d.hide(); }
          });
          d.$body.append(`<div style="text-align:center"><img src="${r.message.data_uri}" style="max-width: 100%; height:auto"/></div>`);
          d.show();
        }
      }
    });
  }, __("QR Foundry"));

  // Attach button  
  frm.add_custom_button("Attach QR (private)", () => {
    frappe.call({
      method: "qr_foundry.api.attach_qr_to_doc",
      args: { doctype: frm.doc.doctype, name: frm.doc.name },
      callback: function(r) {
        if (r.message && r.message.file_url) {
          frappe.show_alert({
            message: __("QR attached as private file"), 
            indicator: "green"
          });
        }
      }
    });
  }, __("QR Foundry"));
};

window.qr_foundry.add_qr_buttons_if_needed = async function (frm) {
  if (!frm || !frm.doc || frm.doc.__islocal) return;
  if (!window.qr_foundry.user_has_qr_role()) return;

  // SysMgr bypasses rule gating; others must be an enabled doctype
  const enabled = (frappe.boot.qr_foundry_rule_doctypes || []);
  const allowed = window.qr_foundry.user_is_sysmgr() ? true : enabled.includes(frm.doctype);
  if (!allowed) return;

  if (frm.custom_buttons && frm.custom_buttons["QR Foundry"]) return;
  window.qr_foundry.add_qr_buttons(frm);
};

// Universal form event binding
const DOCTYPES = (frappe.boot && frappe.boot.qr_foundry_rule_doctypes) || [];

if (frappe.ui && frappe.ui.form && frappe.ui.form.on) {
  DOCTYPES.forEach(dt => {
    if (dt && typeof dt === "string") {
      frappe.ui.form.on(dt, {
        refresh(frm) { 
          window.qr_foundry.add_qr_buttons_if_needed(frm);
        }
      });
    }
  });
}