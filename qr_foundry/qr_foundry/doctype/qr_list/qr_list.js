frappe.ui.form.on("QR List", {
  refresh(frm) {
    const roles = frappe.user_roles || [];
    const can = roles.includes("System Manager") || roles.includes("QR Manager");
    if (!can) return;

    if (!frm.doc.__islocal) {
      frm.add_custom_button(__("Preview"), async () => {
        try {
          frappe.dom.freeze(__("Rendering preview..."));
          const r = await frappe.call({
            method: "qr_foundry.api.preview_qr_list",
            args: { name: frm.doc.name }
          });
          if (r.message && r.message.data_uri) {
            const w = window.open("", "_blank");
            w.document.write(`<img src="${r.message.data_uri}" style="max-width:100%">`);
          }
        } finally {
          frappe.dom.unfreeze();
        }
      });

      frm.add_custom_button(__("Generate / Refresh"), async () => {
        try {
          frappe.dom.freeze(__("Generating..."));
          const r = await frappe.call({
            method: "qr_foundry.api.generate_qr_list",
            args: { name: frm.doc.name }
          });
          if (r.message && r.message.absolute_file_url) {
            frappe.show_alert({ message: __("QR ready"), indicator: "green" });
            frm.reload_doc();
            window.open(r.message.absolute_file_url, "_blank");
          }
        } finally {
          frappe.dom.unfreeze();
        }
      });
    } else {
      frm.add_custom_button(__("Save to Generate"), () => {
        frappe.show_alert({ message: __("Please save first"), indicator: "orange" });
      });
    }
  },

  // When value_doctype changes, populate value_field options
  value_doctype(frm) {
    if (frm.doc.value_doctype && frm.doc.qr_mode === "Value") {
      frappe.call({
        method: "qr_foundry.qr_foundry.doctype.qr_list.qr_list.get_value_fields",
        args: { doctype: frm.doc.value_doctype },
        callback: function(r) {
          if (r.message) {
            const field = frm.get_field("value_field");
            field.df.options = r.message.map(f => f.value).join("\n");
            field.refresh();
            
            // Clear current selection if it's not in new options
            if (frm.doc.value_field) {
              const valid_fields = r.message.map(f => f.value);
              if (!valid_fields.includes(frm.doc.value_field)) {
                frm.set_value("value_field", "");
              }
            }
          }
        }
      });
    } else {
      // Clear field options when not in Value mode
      const field = frm.get_field("value_field");
      field.df.options = "";
      field.refresh();
      frm.set_value("value_field", "");
    }
  },

  // Clear value_field when mode changes
  qr_mode(frm) {
    if (frm.doc.qr_mode !== "Value") {
      frm.set_value("value_field", "");
      const field = frm.get_field("value_field");
      field.df.options = "";
      field.refresh();
    }
  }
});
