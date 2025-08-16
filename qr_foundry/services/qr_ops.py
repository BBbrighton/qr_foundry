from __future__ import annotations
import re
from urllib.parse import quote, urlparse
import urllib.parse as urlparse
from typing import Optional

import frappe
from frappe import _
from frappe.utils import get_url

logger = frappe.logger("qr_foundry")
from frappe.utils.file_manager import save_file

# Guard import to avoid circulars during partial deploys
try:
    from qr_foundry.services.tokens import ensure_active_token_for_qr_list, build_token_resolver_url
except Exception:
    # tokens module may not be imported yet in your current state
    ensure_active_token_for_qr_list = None
    build_token_resolver_url = None

from qr_foundry.utils.qr import generate_qr_png, make_data_uri

# ---------- helpers

_ALLOWED_SCHEMES = {"http", "https"}

def _is_safe_route(route: str) -> bool:
	"""Allow only absolute http/https or site-relative ('/...') paths for Direct mode."""
	if not route:
		return False
	if route.startswith("/"):
		return True
	parsed = urlparse.urlparse(route)
	return parsed.scheme in _ALLOWED_SCHEMES and bool(parsed.netloc)


def _first_non_empty(*vals: Optional[str]) -> Optional[str]:
	for v in vals:
		if isinstance(v, str) and v.strip():
			return v.strip()
	return None

def _get_manual_value(qr_list_doc) -> str:
	"""
	For Manual/Value modes, pull the content from any of these common fields.
	We do NOT enforce URL scheme here; QR content can be any text.
	"""
	val = _first_non_empty(
		getattr(qr_list_doc, "value", None),
		getattr(qr_list_doc, "manual_value", None),
		getattr(qr_list_doc, "manual_content", None),
		getattr(qr_list_doc, "static_value", None),
		getattr(qr_list_doc, "encoded_value", None),
		getattr(qr_list_doc, "content", None),
	)
	if not val:
		frappe.throw("Manual/Value QR requires a non-empty value.", title="QR Foundry")
	return val

def _slug(s: str) -> str:
	s = (s or "").strip()
	s = re.sub(r"[^\w\-.]+", "_", s)
	return s[:140] or "qr"

def _build_route(doctype: Optional[str], name: Optional[str],
                 action: Optional[str] = None, report: Optional[str] = None,
                 custom_route: Optional[str] = None) -> str:
	"""
	Build a Direct route. Prefer a vetted custom_route if provided.
	Return a site-relative path ('/...') or absolute http(s) URL.
	"""
	# 1) Prefer custom_route when present
	if custom_route:
		if not _is_safe_route(custom_route):
			frappe.throw("Unsafe custom route.", title="QR Foundry")
		# Normalize to absolute if site-relative
		return get_url(custom_route) if custom_route.startswith("/") else custom_route

	# 2) Otherwise require doctype + name
	if not doctype or not name:
		frappe.throw("Direct mode requires target Doctype and Name (or a custom route).", title="QR Foundry")

	# Example builder — keep your existing mapping if different:
	if action == "print" and report:
		return f"/printview?doctype={urlparse.quote(doctype)}&name={urlparse.quote(name)}&format={urlparse.quote(report)}"

	# Default: open the document in Desk
	return f"/app/{urlparse.quote(doctype)}/{urlparse.quote(name)}"


def compute_and_persist_encoded(qr_list_doc) -> str:
    """
    SINGLE SOURCE OF TRUTH:
    - Token  -> ensure/issue token, set absolute '/qr?token=...'
    - Direct -> use custom_route if given, else build from (doctype,name,action,report) and validate
    - Manual/Value -> use the provided value as-is (text), no URL validation
    Never fallback Token→Direct.
    """
    try:
        qr_mode = (getattr(qr_list_doc, "qr_mode", None) or "URL").strip()
        link_type = (getattr(qr_list_doc, "link_type", None) or "Direct").strip()

        # TOKEN (for URL mode with Token link type)
        if qr_mode == "URL" and link_type == "Token":
            if ensure_active_token_for_qr_list is None or build_token_resolver_url is None:
                frappe.throw("Token utilities not available.", title="QR Foundry")
            raw = ensure_active_token_for_qr_list(qr_list_doc.name)
            # Use build_token_resolver_url if available, otherwise construct manually
            if build_token_resolver_url:
                encoded = build_token_resolver_url(raw)
            else:
                encoded = get_url(f"/qr?token={raw}")

        # DIRECT (URL mode with Direct link type)
        elif qr_mode == "URL" and link_type == "Direct":
            encoded = _build_route(
                getattr(qr_list_doc, "target_doctype", None),
                getattr(qr_list_doc, "target_name", None),
                getattr(qr_list_doc, "action", None),
                getattr(qr_list_doc, "print_format", None),
                getattr(qr_list_doc, "custom_route", None),
            )
            # Normalize to absolute if site-relative
            if encoded.startswith("/"):
                encoded = get_url(encoded)

        # MANUAL / VALUE (arbitrary text)
        elif qr_mode in {"Manual", "Value"}:
            encoded = _get_manual_value(qr_list_doc)

        else:
            # Be explicit — if a new mode is added later, you want a clear error, not a silent wrong QR.
            frappe.throw(f"Unsupported qr_mode '{qr_mode}' or link_type '{link_type}'.", title="QR Foundry")

        qr_list_doc.db_set("encoded_url", encoded, update_modified=False)
        logger.info({
            "event": "computed_encoded",
            "qr_list": qr_list_doc.name,
            "qr_mode": qr_mode,
            "link_type": link_type,
            "encoded_kind": "token" if "/qr?token=" in encoded else "direct",
        })
        return encoded
    except Exception as e:
        logger.error({
            "event": "compute_failed",
            "qr_list": qr_list_doc.name,
            "qr_mode": getattr(qr_list_doc, "qr_mode", None),
            "link_type": getattr(qr_list_doc, "link_type", None),
            "error": str(e),
        })
        raise


def _get_field_value(dt: str, dn: str, fieldname: str) -> str:
	try:
		value = frappe.db.get_value(dt, dn, fieldname) or ""
		value = str(value).strip()
		if not value:
			frappe.throw(_("Selected field '{0}' resolved to empty. Please choose a field with a value before generating a QR.").format(fieldname), title=_("Empty Value"))
		return value
	except Exception as e:
		if "Empty Value" in str(e):
			raise  # Re-raise our custom error
		frappe.throw(_("Error reading field '{0}' from {1}: {2}").format(fieldname, dt, str(e)))


# ---------- core computation


def _compute_encoded(row) -> tuple[str, str]:
	mode = (row.qr_mode or "URL").strip()
	label = getattr(row, "label_text", None) or ""

	if mode == "URL":
		custom_route = (getattr(row, "custom_route", "") or "").strip()
		dt = getattr(row, "target_doctype", None)
		dn = getattr(row, "target_name", None)
		action = (getattr(row, "action", None) or getattr(row, "target_action", None) or "view").strip()
		print_format = getattr(row, "print_format", None)
		if custom_route:
			if not _is_safe_route(custom_route):
				frappe.throw("Invalid custom route.", title="Security")
			encoded = custom_route
		elif dt and dn:
			encoded = _build_route(dt, dn, action, print_format)
		else:
			frappe.throw(_("URL mode needs a Target DocType & Document or a Custom URL."))
		if not encoded.startswith(("http://", "https://")):
			encoded = get_url(encoded)
		return encoded, label

	if mode == "Value":
		dt = getattr(row, "value_doctype", None)
		dn = getattr(row, "value_name", None)
		fieldname = getattr(row, "value_field", None)
		if not (dt and dn and fieldname):
			frappe.throw(_("Value mode requires DocType, Document and Field."))
		return str(_get_field_value(dt, dn, fieldname)), label

	if mode == "Manual":
		content = (getattr(row, "manual_content", "") or "").strip()
		if not content:
			frappe.throw(_("Manual mode requires some content."))
		return content, label

	frappe.throw(_("Unsupported mode: {0}").format(mode))


# ---------- attach to QR List only


def attach_qr_image_to_qr_list(qr_list_name: str, *, file_basename: str | None = None) -> dict:
    """
    Render a PNG for this QR List and attach it to QR List.image (private).
    Returns {file_url, absolute_file_url, encoded_url}.
    """
    row = frappe.get_doc("QR List", qr_list_name)
    encoded = compute_and_persist_encoded(row)
    label = getattr(row, "label_text", None)
    png = generate_qr_png(encoded, label=label)

    # Use a stable filename
    if not file_basename:
        file_basename = f"{row.name}.png"

    # Frappe 15 signature (positional args)
    f = save_file(
        file_basename,  # fname
        png,            # content (bytes)
        "QR List",      # dt
        row.name,       # dn
        decode=False,
        is_private=1,
        df="image",     # attach into the Attach Image field on QR List
    )

    absolute = get_url(f.file_url) if f.file_url else None
    row.db_set("file_url", f.file_url, update_modified=False)
    row.db_set("absolute_file_url", absolute, update_modified=False)

    return {
        "file_url": f.file_url,
        "absolute_file_url": absolute,
        "encoded_url": encoded,
    }


# ---------- public services


def preview_qr_for_qr_list(qr_list_name: str) -> dict:
    row = frappe.get_doc("QR List", qr_list_name)
    encoded = compute_and_persist_encoded(row)
    label = getattr(row, "label_text", None)
    png = generate_qr_png(encoded, label=label)
    return {"data_uri": make_data_uri(png)}


def generate_qr_image_for_qr_list(qr_list_name: str) -> dict:
    """Convenience wrapper: compute+render+attach."""
    return attach_qr_image_to_qr_list(qr_list_name)


__all__ = ["_build_route", "attach_qr_image_to_qr_list"]
