frappe.ui.form.on("QR List", {
  refresh(frm) {
    // QR buttons are now handled by the universal button system
    // No custom buttons needed here - they appear automatically via QR Rule
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
