# bench console — QR Foundry cleanup (test users, QR lists/tokens/logs)
import frappe
from frappe import _

# ------------- CONFIG -------------
DRY_RUN = True  # set to False to actually delete
TEST_USERS = [
    "qr.manager@example.com",
    "qr.user@example.com",
    "qr.other@example.com",
]
# (doctype, name) pairs to clean QR artifacts for:
TARGETS = [
    ("Item", "prod01"),
    # add more here, e.g. ("Warehouse", "Roller - VP"),
]
# ----------------------------------

def info(msg): print("•", msg)
def hdr(title): print("\n=== " + title + " ===")
def can_delete_dt(dt):
    return bool(frappe.db.exists("DocType", dt))

def delete_qr_artifacts_for(dt, dn, dry=True):
    out = {"qr_lists": [], "qr_tokens": [], "qr_scan_logs": []}

    if not frappe.db.exists(dt, dn):
        info(f"[skip] {dt} {dn} does not exist")
        return out

    # find QR Lists for this doc
    qr_lists = frappe.get_all("QR List",
        filters={"target_doctype": dt, "target_name": dn},
        pluck="name")
    out["qr_lists"] = qr_lists[:]

    # tokens for those lists
    token_names = []
    if qr_lists and can_delete_dt("QR Token"):
        token_names = frappe.get_all("QR Token",
            filters={"qr_list": ["in", qr_lists]}, pluck="name")
    out["qr_tokens"] = token_names[:]

    # scan logs tied to those tokens (if "token" field exists)
    scan_log_names = []
    if token_names and can_delete_dt("QR Scan Log"):
        meta = frappe.get_meta("QR Scan Log")
        if meta.has_field("token"):
            scan_log_names = frappe.get_all("QR Scan Log",
                filters={"token": ["in", token_names]}, pluck="name")
        out["qr_scan_logs"] = scan_log_names[:]

    # print plan
    info(f"{dt} {dn}: found {len(qr_lists)} QR List, {len(token_names)} QR Token, {len(scan_log_names)} QR Scan Log")

    if dry:
        return out

    # delete in safe order: logs -> tokens -> lists
    for n in scan_log_names:
        try:
            frappe.delete_doc("QR Scan Log", n, ignore_permissions=True, delete_permanently=True)
        except Exception as e:
            info(f"[warn] could not delete QR Scan Log {n}: {e}")

    for n in token_names:
        try:
            frappe.delete_doc("QR Token", n, ignore_permissions=True, delete_permanently=True)
        except Exception as e:
            info(f"[warn] could not delete QR Token {n}: {e}")

    for n in qr_lists:
        try:
            frappe.delete_doc("QR List", n, ignore_permissions=True, delete_permanently=True)
        except Exception as e:
            info(f"[warn] could not delete QR List {n}: {e}")

    return out

def delete_or_disable_user(email, dry=True):
    if not frappe.db.exists("User", email):
        info(f"[skip] user not found: {email}")
        return {"deleted": False, "disabled": False}

    # try a hard delete
    if not dry:
        try:
            frappe.delete_doc("User", email, ignore_permissions=True, delete_permanently=True)
            info(f"[ok] deleted user: {email}")
            return {"deleted": True, "disabled": False}
        except Exception as e:
            info(f"[info] could not delete {email} (likely linked): {e}. Disabling instead…")
            try:
                u = frappe.get_doc("User", email)
                u.enabled = 0
                u.save(ignore_permissions=True)
                info(f"[ok] disabled user: {email}")
                return {"deleted": False, "disabled": True}
            except Exception as e2:
                info(f"[warn] could not disable {email}: {e2}")
                return {"deleted": False, "disabled": False}
    else:
        info(f"[plan] would delete (or disable if linked): {email}")
        return {"deleted": False, "disabled": False}

# ensure we're not in a permissive console state
frappe.local.flags = getattr(frappe.local, "flags", frappe._dict())
frappe.local.flags.ignore_permissions = False

hdr("PLAN")
print("DRY_RUN =", DRY_RUN)
print("TEST_USERS =", TEST_USERS)
print("TARGETS =", TARGETS)

# preview pass (and/or delete)
summary = {"targets": [], "users": {}}

hdr("CLEAN QR ARTIFACTS")
for dt, dn in TARGETS:
    res = delete_qr_artifacts_for(dt, dn, dry=DRY_RUN)
    summary["targets"].append({"doctype": dt, "name": dn, **res})

hdr("CLEAN TEST USERS")
for email in TEST_USERS:
    res = delete_or_disable_user(email, dry=DRY_RUN)
    summary["users"][email] = res

print("\n=== SUMMARY ===")
print(f"- dry_run: {DRY_RUN}")
print(f"- cleaned targets: {len(summary['targets'])}")
for t in summary["targets"]:
    print(f"  {t['doctype']} {t['name']}: QR Lists={len(t['qr_lists'])}, Tokens={len(t['qr_tokens'])}, Logs={len(t['qr_scan_logs'])}")
print(f"- users processed: {len(summary['users'])}")
for u, res in summary["users"].items():
    print(f"  {u}: deleted={res['deleted']} disabled={res['disabled']}")

if not DRY_RUN:
    frappe.db.commit()
    print("\nCommitted deletes.")
else:
    print("\nDRY RUN ONLY — no changes committed. Set DRY_RUN=False to apply.")