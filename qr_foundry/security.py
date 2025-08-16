from __future__ import annotations
import frappe

# Include all three: SysMgr, QR Manager, QR User
ALLOWED_GENERATOR_ROLES = {"System Manager", "QR Manager", "QR User"}

def _is_sysmgr() -> bool:
    return "System Manager" in set(frappe.get_roles() or [])

def ensure_generator():
    """Allow generate/preview for SysMgr, QR Manager, or QR User."""
    if _is_sysmgr():
        return
    roles = set(frappe.get_roles() or [])
    if not (roles & {"QR Manager", "QR User"}):
        frappe.throw(frappe._("Not allowed to generate QR codes."), frappe.PermissionError)

def ensure_manager():
    """Admin ops reserved for QR Manager; SysMgr always allowed."""
    if _is_sysmgr():
        return
    if "QR Manager" not in set(frappe.get_roles() or []):
        frappe.throw(frappe._("Only QR Manager may perform this action."), frappe.PermissionError)

def ensure_doctype_is_enabled(doctype: str):
    """Only doctypes enabled in QR Settings → Rules are allowed (SysMgr bypass)."""
    if _is_sysmgr():
        return
    s = frappe.get_cached_doc("QR Settings")
    enabled = [r.target_doctype for r in (s.rules or []) if getattr(r, "enabled", 0)]
    if doctype not in enabled:
        frappe.throw(
            frappe._("{0} is not enabled for QR Foundry.").format(frappe._(doctype)),
            frappe.PermissionError,
        )

# Legacy helpers for backward compatibility
def user_has_role(user=None, roles=ALLOWED_GENERATOR_ROLES) -> bool:
    user = user or frappe.session.user
    user_roles = set(frappe.get_roles(user))
    return bool(user_roles & roles)

def check_can_generate(doctype: str, name: str):
    """Allow System Manager / QR Manager; otherwise require Write on target doc."""
    if user_has_role():
        return
    doc = frappe.get_doc(doctype, name)
    doc.check_permission("write")

def mask_token(raw: str) -> str:
    if not raw: return ""
    return raw[:4] + "…" + raw[-4:]

def rate_limit_generation(max_per_user_per_day: int | None = None):
    """Optional per-user daily limiter; never enforced for managers."""
    if not max_per_user_per_day:
        return
    if user_has_role():  # exempt managers
        return
    user = frappe.session.user
    key = f"qr_gen_limit:{user}:{frappe.utils.nowdate()}"
    count = frappe.cache().incr(key)
    if count == 1:
        frappe.cache().expire(key, 86400)
    if count > max_per_user_per_day:
        frappe.throw("Generation rate limit exceeded for today.", title="Rate Limited")