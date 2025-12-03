# qr_foundry/qr_foundry/www/qr/index.py
# Minimal, production-ready resolver with your guardrails kept intact.

from __future__ import annotations
import datetime as dt
import json
import re
from urllib.parse import urlparse

import frappe
from frappe.utils import now_datetime, cint, get_url

no_cache = 1  # ensure no caching

LOG_NS = "QR Foundry"
UA_MAX = 500
REF_MAX = 2048


# -------------------------------
# Small helpers
# -------------------------------


def _sec_headers():
	"""Security headers on every response (avoid duplicates)."""
	hdrs = frappe.local.response.setdefault("headers", [])
	existing = {k.lower(): v for k, v in hdrs}
	if "referrer-policy" not in existing:
		hdrs.append(("Referrer-Policy", "no-referrer"))
	if "cache-control" not in existing:
		hdrs.append(("Cache-Control", "no-store"))
	if "x-robots-tag" not in existing:
		hdrs.append(("X-Robots-Tag", "noindex, nofollow"))


def _header(key: str, *, maxlen: int | None = None) -> str | None:
	val = None
	try:
		val = frappe.get_request_header(key)
	except Exception:
		pass
	if not val:
		try:
			req = getattr(frappe.local, "request", None)
			if req and getattr(req, "headers", None):
				val = req.headers.get(key)
		except Exception:
			pass
	if val and maxlen and len(val) > maxlen:
		val = val[:maxlen]
	return val


def _sanitize_url(url: str | None) -> str | None:
	"""Keep scheme://host/path only (no query/fragment)."""
	if not url:
		return None
	try:
		p = urlparse(url)
		if not p.scheme or not p.netloc:
			return None
		return f"{p.scheme}://{p.netloc}{p.path}"
	except Exception:
		return None


def _doc_exists_cached(doctype: str) -> bool:
	"""Cache DocType existence; short TTL for negatives."""
	key = f"qrf:exists:{doctype}"
	cache = frappe.cache()
	val = cache.get_value(key)
	if val is None:
		ok = bool(frappe.db.exists("DocType", doctype))
		# Frappe cache API uses expires_in_sec
		try:
			cache.set_value(key, 1 if ok else 0, expires_in_sec=300 if ok else 5)
		except TypeError:
			cache.set_value(key, 1 if ok else 0)  # fallback, no TTL
		return ok
	return bool(int(val))


def _settings():
	out = {"allowed_domains": [], "default_rate_limit_per_min": None, "require_login": 0}
	try:
		s = frappe.get_cached_doc("QR Settings")
		out["allowed_domains"] = [l.strip() for l in (s.allowed_domains or "").splitlines() if l.strip()]
		out["default_rate_limit_per_min"] = cint(getattr(s, "default_rate_limit_per_min", 0)) or None
		out["require_login"] = cint(getattr(s, "require_login", 0))
	except Exception:
		pass
	return out


def _is_allowed_url(url: str, allow: list[str]) -> bool:
	try:
		p = urlparse(url)
		if p.scheme not in ("http", "https"):
			return False
		if not allow:
			return True
		host = (p.netloc or "").lower()
		return any(host == d.lower() or host.endswith("." + d.lower()) for d in allow)
	except Exception:
		return False


def _rate_limited(bucket_id: str, per_min: int | None) -> bool:
	if not per_min:
		return False
	cache = frappe.cache()
	key = f"qr:rl:{bucket_id}:{dt.datetime.utcnow():%Y%m%d%H%M}"
	n = cache.incr(key)
	cache.expire(key, 70)  # ~1 min window
	return cint(n) > cint(per_min)


def _atomic_use(token_name: str, has_max_uses: bool, has_expires_on: bool) -> bool:
	"""
	Atomically increment use_count if allowed. Uses ROW_COUNT() for reliable detection.
	"""
	where = ["name=%s", "status='Active'"]
	if has_max_uses:
		where.append("(COALESCE(max_uses,0)=0 OR COALESCE(use_count,0) < max_uses)")
	if has_expires_on:
		where.append("(expires_on IS NULL OR expires_on > NOW())")
	where_clause = " AND ".join(where)

	q = f"""
        UPDATE `tabQR Token`
        SET use_count = COALESCE(use_count, 0) + 1,
            last_used_on = NOW()
        WHERE {where_clause}
    """
	try:
		frappe.db.sql(q, (token_name,))
		rc = frappe.db.sql("SELECT ROW_COUNT()")[0][0]
		return int(rc) == 1
	except Exception:
		frappe.log_error(frappe.get_traceback(), title="QR Foundry: atomic_use failed")
		return False


# -------------------------------
# Role-based redirect helpers
# -------------------------------


def _get_qr_rule(doctype_name: str) -> dict | None:
	"""Get QR Rule for a doctype, with role redirect config."""
	try:
		rules = frappe.get_all(
			"QR Rule",
			filters={"doctype_name": doctype_name},
			fields=["enable_role_redirects", "role_redirects_json"],
			limit=1,
		)
		return rules[0] if rules else None
	except Exception:
		return None


def _slugify(text: str) -> str:
	"""Convert 'Sales Order' to 'sales-order'."""
	return re.sub(r"[^a-z0-9]+", "-", text.lower()).strip("-")


def _replace_field_placeholders(url: str, target_doctype: str, target_name: str) -> str | None:
	"""
	Replace {field:FIELDNAME} placeholders with actual field values.
	Returns None if any placeholder fails (Option C: fail that option).
	"""
	pattern = r"\{field:(\w+)\}"
	matches = re.findall(pattern, url)
	if not matches:
		return url

	try:
		# Fetch the target document to get field values
		doc = frappe.get_doc(target_doctype, target_name)
		for fieldname in matches:
			value = getattr(doc, fieldname, None)
			if value is None:
				# Field doesn't exist or is empty - fail this option
				return None
			url = url.replace(f"{{field:{fieldname}}}", str(value))
		return url
	except Exception:
		return None


def _build_redirect_url(redirect_config: dict, target_doctype: str, target_name: str) -> str | None:
	"""
	Build redirect URL from config.
	Returns None if URL cannot be built (Option C: fail that option).
	"""
	try:
		redirect_type = redirect_config.get("redirect_type", "action")

		if redirect_type == "custom_url":
			url = redirect_config.get("custom_url", "")
			if not url:
				return None

			# Replace standard placeholders
			url = url.replace("{name}", target_name or "")
			url = url.replace("{doctype}", target_doctype or "")
			url = url.replace("{doctype_slug}", _slugify(target_doctype or ""))

			# Replace field placeholders
			url = _replace_field_placeholders(url, target_doctype, target_name)
			if url is None:
				return None

			# Normalize to absolute URL
			if not url.startswith(("http://", "https://")):
				url = get_url(url)

			return url
		else:
			# Action-based redirect
			action = redirect_config.get("redirect_action", "view")
			from frappe.utils import get_url_to_form, get_url_to_list

			if action == "list":
				rel_url = get_url_to_list(target_doctype)
			elif action == "print":
				rel_url = f"/printview?doctype={target_doctype}&name={target_name}"
			elif action == "edit":
				rel_url = get_url_to_form(target_doctype, target_name)
			else:  # view
				rel_url = get_url_to_form(target_doctype, target_name)

			return get_url(rel_url)
	except Exception:
		return None


def _get_role_based_resolution(tok: dict, default_target: str) -> dict:
	"""
	Determine redirect target(s) based on user roles.
	Returns dict with mode and target/options.

	Smart Mode:
	- 0 valid matches → default target
	- 1 valid match → direct redirect to that target
	- 2+ valid matches → show choice page
	"""
	result = {"mode": "redirect", "target": default_target}

	# Get QR List to find target doctype
	qr_list_name = tok.get("qr_list")
	if not qr_list_name:
		return result

	try:
		qr_list = frappe.get_doc("QR List", qr_list_name)
		target_doctype = qr_list.target_doctype
		target_name = qr_list.target_name

		if not target_doctype:
			return result

		# Check if role redirects are enabled for this doctype
		rule = _get_qr_rule(target_doctype)
		if not rule or not rule.get("enable_role_redirects"):
			return result

		# Guest users always get default
		current_user = getattr(getattr(frappe, "session", None), "user", None)
		if not current_user or current_user == "Guest":
			return result

		# Get user's roles
		user_roles = set(frappe.get_roles(current_user))

		# Parse role redirects
		redirects_json = rule.get("role_redirects_json") or "[]"
		try:
			redirects = json.loads(redirects_json)
		except (json.JSONDecodeError, TypeError):
			return result

		if not redirects:
			return result

		# Find matching redirects and validate URLs (Option C: graceful degradation)
		valid_options = []
		for r in redirects:
			if r.get("role") not in user_roles:
				continue

			# Try to build the URL - if it fails, skip this option
			url = _build_redirect_url(r, target_doctype, target_name)
			if url:
				valid_options.append({
					"label": r.get("label", r.get("role", "Go")),
					"url": url,
					"priority": r.get("priority", 0),
				})

		# Sort by priority
		valid_options.sort(key=lambda x: x.get("priority", 0))

		# Smart mode decision
		if len(valid_options) == 0:
			# No valid matches → default
			return result
		elif len(valid_options) == 1:
			# Exactly one valid match → direct redirect
			return {"mode": "redirect", "target": valid_options[0]["url"]}
		else:
			# Multiple valid matches → choice page
			return {
				"mode": "choose",
				"options": valid_options,
				"doctype": target_doctype,
				"name": target_name,
			}

	except Exception:
		# Any error → fall back to default
		return result


# -------------------------------
# Logging (minimal, schema-aware)
# -------------------------------


def _log(result: str, token_name: str | None, url_for_log: str | None = None):
	try:
		if not _doc_exists_cached("QR Scan Log"):
			return

		meta = frappe.get_meta("QR Scan Log")
		now = now_datetime()

		# common fields
		user = getattr(getattr(frappe, "session", None), "user", None)
		if user == "Guest":
			user = None
		ip = getattr(frappe.local, "request_ip", None)
		ua = _header("User-Agent", maxlen=UA_MAX)
		ref = _header("Referer", maxlen=REF_MAX)
		safe_url = _sanitize_url(url_for_log)

		doc = {"doctype": "QR Scan Log"}

		if meta.has_field("token"):
			doc["token"] = token_name

		# timestamp
		if meta.has_field("ts"):
			doc["ts"] = now
		elif meta.has_field("scan_on"):
			doc["scan_on"] = now

		# ip
		if meta.has_field("ip_address"):
			doc["ip_address"] = ip
		elif meta.has_field("ip"):
			doc["ip"] = ip

		# user
		if meta.has_field("client_user"):
			doc["client_user"] = user
		elif meta.has_field("user"):
			doc["user"] = user

		# UA / Referer
		if meta.has_field("user_agent"):
			doc["user_agent"] = ua
		if meta.has_field("referer"):
			doc["referer"] = ref

		# URL
		if meta.has_field("redirect_url"):
			doc["redirect_url"] = safe_url
		elif meta.has_field("resolved_url"):
			doc["resolved_url"] = safe_url

		# result (map "ok" -> "success" if that's the Select option)
		if meta.has_field("result"):
			field = meta.get_field("result")
			opts = [o.strip() for o in (getattr(field, "options", "") or "").splitlines() if o.strip()]
			if result == "ok" and "success" in opts:
				mapped = "success"
			elif not opts or result in opts:
				mapped = result
			else:
				mapped = opts[0]
			doc["result"] = mapped

		frappe.get_doc(doc).insert(ignore_permissions=True, ignore_mandatory=True)
		frappe.db.commit()
	except Exception:
		frappe.log_error(message=frappe.get_traceback(), title=f"{LOG_NS}: scan log failed")


# -------------------------------
# Main resolver
# -------------------------------


def get_context(context):
	frappe.local.flags.ignore_permissions = True
	_sec_headers()

	tok_str = (frappe.form_dict.get("token") or "").strip()[:256]
	if not tok_str:
		_log("invalid", None, None)
		context.update(
			{
				"mode": "message",
				"title": "Missing token",
				"message": "No token was provided.",
				"code": "invalid",
			}
		)
		frappe.local.response["http_status_code"] = 400
		return context

	# Read only columns that exist
	base = ["name", "status", "encoded_content", "qr_list"]
	optional = ["expires_on", "max_uses", "use_count", "rate_limit_per_min", "last_used_on"]
	try:
		meta = frappe.get_meta("QR Token")
		fields = base + [f for f in optional if meta.has_field(f)]
	except Exception:
		fields = base

	tok_rows = frappe.get_all("QR Token", filters={"token": tok_str}, fields=fields, limit=1)
	if not tok_rows:
		_log("not_found", None, None)
		context.update(
			{
				"mode": "message",
				"title": "Not found",
				"message": "This token does not exist.",
				"code": "not_found",
			}
		)
		frappe.local.response["http_status_code"] = 404
		return context

	tok = tok_rows[0]
	if (tok.get("status") or "").lower() != "active":
		_log("revoked", tok["name"], None)
		context.update(
			{
				"mode": "message",
				"title": "Revoked",
				"message": "This code has been revoked.",
				"code": "revoked",
			}
		)
		frappe.local.response["http_status_code"] = 410
		return context

	# --- Resolve default target (backward compatible) ---
	default_target = (tok.get("encoded_content") or "").strip()

	# Normalize to absolute if relative
	if default_target and not default_target.startswith(("http://", "https://")):
		default_target = get_url(default_target)

	# Self-heal if encoded_content accidentally points back to the resolver
	if default_target and (default_target.startswith("/qr?token=") or default_target.endswith(f"token={tok_str}")):
		try:
			qr = frappe.get_doc("QR List", tok["qr_list"])
			from frappe.utils import get_url_to_form, get_url_to_list
			doctype, docname = qr.target_doctype, qr.target_name
			action = (getattr(qr, "action", None) or "view").lower()
			if action in ("view", "", None):
				rebuilt_rel = get_url_to_form(doctype, docname)
			elif action == "list":
				rebuilt_rel = get_url_to_list(doctype)
			else:
				rebuilt_rel = get_url_to_form(doctype, docname)
			default_target = get_url(rebuilt_rel)
		except Exception:
			# keep target as-is or None; logging can handle None
			pass

	st = _settings()
	if st.get("require_login") and frappe.session.user == "Guest":
		# target is now defined (may be None); safe for logging
		_log("login_required", tok["name"], default_target)

		from urllib.parse import quote
		# Redirect to login, then back to the resolver so we can consume token and log "ok" post-login
		resolver_url = get_url(f"/qr?token={tok_str}")
		login_url = f"/login?redirect-to={quote(resolver_url, safe='')}"
		_sec_headers()
		frappe.local.flags.redirect_location = login_url
		raise frappe.Redirect

	# Hard expiry check (no consumption)
	if "expires_on" in fields and tok.get("expires_on") and now_datetime() > tok.get("expires_on"):
		_log("expired", tok["name"], None)
		context.update(
			{"mode": "message", "title": "Expired", "message": "This code has expired.", "code": "expired"}
		)
		frappe.local.response["http_status_code"] = 410
		return context

	# Rate limit (bucket by token name if available)
	per_min = tok.get("rate_limit_per_min") if "rate_limit_per_min" in fields else None
	per_min = per_min or st["default_rate_limit_per_min"]
	bucket = tok.get("name") or tok_str
	if _rate_limited(bucket, per_min):
		_log("rate_limited", tok["name"], None)
		context.update(
			{
				"mode": "message",
				"title": "Too many scans",
				"message": "Please try again in a moment.",
				"code": "rate_limited",
			}
		)
		frappe.local.response["http_status_code"] = 429
		return context

	# --- Role-based redirect resolution (Smart Mode) ---
	resolution = _get_role_based_resolution(tok, default_target)

	if resolution["mode"] == "choose":
		# Multiple valid options → show choice page (no consumption yet)
		# We'll consume when user clicks a choice
		context.update({
			"mode": "choose",
			"title": "Select Destination",
			"options": resolution["options"],
			"doctype": resolution.get("doctype", ""),
			"name": resolution.get("name", ""),
			"token": tok_str,
		})
		return context

	# Single target (either from role redirect or default)
	target = resolution.get("target", default_target)

	# Allowed domain check BEFORE consumption
	site_root = get_url("/")
	is_same_site = target and target.startswith(site_root)
	is_allowed = is_same_site or _is_allowed_url(target, st["allowed_domains"])
	if not (target and is_allowed):
		_log("forbidden", tok["name"], target)  # Log the blocked target for audit
		context.update(
			{
				"mode": "message",
				"title": "Access Denied",
				"message": "The requested resource is not available through this service.",
				"code": "forbidden",
			}
		)
		frappe.local.response["http_status_code"] = 403
		return context

	# Atomic consumption (enforces max_uses/expiry)
	has_max = "max_uses" in fields and "use_count" in fields
	has_exp = "expires_on" in fields
	if not _atomic_use(tok["name"], has_max, has_exp):
		# Decide reason (expired vs limit vs inactive)
		fresh = frappe.get_all(
			"QR Token",
			filters={"name": tok["name"]},
			fields=["expires_on", "use_count", "max_uses", "status"],
			limit=1,
		)
		title, msg, code, res = "Limit reached", "Usage limit reached.", 410, "max_used"
		now = now_datetime()
		if fresh:
			f = fresh[0]
			if has_exp and f.get("expires_on") and now > f.get("expires_on"):
				title, msg, res = "Expired", "This code has expired.", "expired"
			elif (
				has_max
				and cint(f.get("max_uses") or 0) > 0
				and cint(f.get("use_count") or 0) >= cint(f.get("max_uses") or 0)
			):
				title, msg, res = "Limit reached", "Usage limit reached.", "max_used"
			elif (f.get("status") or "").lower() != "active":
				title, msg, res = "Unavailable", "This code is not active.", "revoked"
		_log(res, tok["name"], None)
		context.update({"mode": "message", "title": title, "message": msg, "code": res})
		frappe.local.response["http_status_code"] = 410
		return context

	# Success → redirect (now we consume a use)
	_log("ok", tok["name"], target)
	_sec_headers()
	frappe.local.flags.redirect_location = target
	raise frappe.Redirect
