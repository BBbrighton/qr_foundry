import frappe

def boot_session(bootinfo):
    """Populate enabled doctypes once per session for the universal button."""
    try:
        doctypes = set()

        # QR Rule may store target as 'target_doctype' OR 'doctype_name'
        try:
            # try the modern field
            dt_modern = frappe.get_all("QR Rule", pluck="target_doctype")
            doctypes.update(d for d in (dt_modern or []) if d)
        except Exception:
            pass
        try:
            # fallback to legacy field (your sample uses this)
            dt_legacy = frappe.get_all("QR Rule", pluck="doctype_name")
            doctypes.update(d for d in (dt_legacy or []) if d)
        except Exception:
            pass

        # Also include enabled doctypes from QR Settings ▸ Rules (child table)
        try:
            settings = frappe.get_single("QR Settings")
            for r in (getattr(settings, "rules", []) or []):
                if getattr(r, "enabled", 0) and getattr(r, "target_doctype", None):
                    doctypes.add(r.target_doctype)
        except Exception:
            pass

        bootinfo.qr_foundry_rule_doctypes = sorted(doctypes)
    except Exception as e:
        frappe.log_error(f"QR Foundry boot error: {e}")
        bootinfo.qr_foundry_rule_doctypes = []