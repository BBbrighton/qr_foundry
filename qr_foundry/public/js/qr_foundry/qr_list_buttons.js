frappe.ui.form.on("QR List", {
  refresh(frm) {
    if (frm.is_new()) return;

    // Preview
    frm.add_custom_button("Preview QR", async () => {
      try {
        const r = await frappe.call({
          method: "qr_foundry.api.preview_qr_list",
          args: { qr_list_name: frm.doc.name },
        });
        const data_uri = r.message && r.message.data_uri;
        if (!data_uri) return;
        const d = new frappe.ui.Dialog({
          title: "QR Preview",
          size: "large",
          primary_action_label: "Close",
          primary_action() { d.hide(); }
        });
        d.$body.append(`<div style="text-align:center"><img src="${data_uri}" style="max-width: 100%; height:auto"/></div>`);
        d.show();
      } catch (e) {
        frappe.msgprint({ title: __("QR Preview Failed"), message: e.message || e, indicator: "red" });
      }
    }, __("QR Foundry"));

    // (Re)Generate + attach PNG to QR List.image
    frm.add_custom_button("Regenerate & Attach", async () => {
      try {
        const r = await frappe.call({
          method: "qr_foundry.api.attach_qr_list",
          args: { qr_list_name: frm.doc.name },
        });
        if (r.message && r.message.file_url) {
          await frm.reload_doc();
          frappe.show_alert({ message: __("QR image attached"), indicator: "green" });
        }
      } catch (e) {
        frappe.msgprint({ title: __("Attach Failed"), message: e.message || e, indicator: "red" });
      }
    }, __("QR Foundry"));

    // View Tokens button - only show for URL mode with Token link type and for managers
    const roles = frappe.boot.user.roles || [];
    console.log("QR List refresh - qr_mode:", frm.doc.qr_mode, "link_type:", frm.doc.link_type, "roles:", roles);
    
    if (frm.doc.qr_mode === "URL" && frm.doc.link_type === "Token" && 
        (roles.includes("System Manager") || roles.includes("QR Manager"))) {
      frm.add_custom_button("View Tokens", () => {
        frappe.set_route("List", "QR Token", {
          "qr_list": frm.doc.name
        });
      }, __("QR Foundry"));
      
      // Also show token count in the form
      frappe.call({
        method: "frappe.client.get_count",
        args: {
          doctype: "QR Token",
          filters: { qr_list: frm.doc.name }
        },
        callback: function(r) {
          if (r.message) {
            const active_count = frappe.call({
              method: "frappe.client.get_count",
              args: {
                doctype: "QR Token",
                filters: { qr_list: frm.doc.name, status: "Active" }
              },
              callback: function(r2) {
                const active = r2.message || 0;
                const total = r.message || 0;
                frm.set_intro(
                  __("Tokens: {0} active / {1} total", [active, total]),
                  active > 0 ? "green" : "orange"
                );
              }
            });
          }
        }
      });
    }
  },
});