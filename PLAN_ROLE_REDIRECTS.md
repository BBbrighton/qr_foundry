# Implementation Plan: Role-Based Token Redirects

## Overview

Add role-based redirect functionality so that when a token-based QR code is scanned, different users (based on their roles) can be redirected to different landing pages.

## Design Principles

1. **Backward Compatibility**: Existing installations continue to work without changes
2. **Opt-in**: Role-based redirects are optional - if not configured, default behavior applies
3. **Rule-Level Configuration**: Configured in QR Settings per-doctype (not per-token)
4. **Guest Fallback**: Guest users (unauthenticated) always get default behavior
5. **Smart Mode**: Show choice page only when user has 2+ matching roles

---

## Current Architecture

```
QR Settings (single)
  └── rules (child table: QR Settings Rule)
        ├── target_doctype
        ├── default_link_type (Direct/Token)
        ├── default_action (view/print/edit)
        └── auto_generate_on_first_save

        ↓ on_update()

QR Rule (cache table, one per doctype)
  ├── doctype_name
  ├── default_link_type
  ├── default_action
  └── auto_generate_on_first_save
```

---

## Proposed Architecture

```
QR Settings (single)
  └── rules (child table: QR Settings Rule)
        ├── target_doctype
        ├── default_link_type (Direct/Token)
        ├── default_action (view/print/edit)
        ├── auto_generate_on_first_save
        ├── enable_role_redirects (NEW - Check)
        └── role_redirects (NEW - Table: QR Role Redirect)

NEW: QR Role Redirect (child table)
  ├── role (Link to Role)
  ├── label (Data - button text for choice page)
  ├── redirect_type (Select: action/custom_url)
  ├── redirect_action (Select: view/print/edit/list)
  ├── custom_url (Data - supports placeholders)
  └── priority (Int - display order on choice page)

        ↓ on_update() syncs to

QR Rule (cache table, one per doctype)
  ├── doctype_name
  ├── default_link_type
  ├── default_action
  ├── auto_generate_on_first_save
  ├── enable_role_redirects (NEW)
  └── role_redirects_json (NEW - JSON blob for fast lookup)
```

---

## Smart Mode Behavior

| Scenario | Result |
|----------|--------|
| Guest user | Direct redirect → default `encoded_content` |
| User with 0 matching roles | Direct redirect → default `encoded_content` |
| User with 1 matching role | Direct redirect → that role's target |
| User with 2+ matching roles | **Show choice page** → user picks destination |

---

## QR Role Redirect Child Table

### Fields

| Field | Type | Options | Description |
|-------|------|---------|-------------|
| `role` | Link | Role | Which role this redirect applies to |
| `label` | Data | | Button text on choice page: "Edit Order", "Go to POS" |
| `redirect_type` | Select | `action` / `custom_url` | How to determine redirect URL |
| `redirect_action` | Select | `view` / `edit` / `print` / `list` | Frappe action (if redirect_type=action) |
| `custom_url` | Data | | URL with placeholders (if redirect_type=custom_url) |
| `priority` | Int | | Display order on choice page (0 = top) |

### Custom URL Placeholders

| Placeholder | Resolves To | Example |
|-------------|-------------|---------|
| `{name}` | Document name | `SO-001` |
| `{doctype}` | Target doctype | `Sales Order` |
| `{doctype_slug}` | URL-safe doctype | `sales-order` |
| `{field:FIELDNAME}` | Field value from target doc | `{field:customer}` → `CUST-001` |

### Example Custom URLs

```
/app/point-of-sale?sales_order={name}
/portal/orders/{name}
/app/Pick List?sales_order={name}
/warehouse/{field:warehouse}
```

---

## Choice Page Design

When user has 2+ matching roles, show a selection page:

```
┌─────────────────────────────────────────────┐
│  QR Code: Sales Order SO-001                │
│                                             │
│  Select destination:                        │
│                                             │
│  ┌─────────────────────────────────────┐   │
│  │ 📝 Edit Order                        │   │  ← label from role redirect
│  └─────────────────────────────────────┘   │
│  ┌─────────────────────────────────────┐   │
│  │ 👁️ View Order Details                │   │
│  └─────────────────────────────────────┘   │
│  ┌─────────────────────────────────────┐   │
│  │ 💰 Open in POS                       │   │
│  └─────────────────────────────────────┘   │
│                                             │
└─────────────────────────────────────────────┘
```

Buttons ordered by `priority` field (0 = top).

---

## Resolution Logic (Pseudocode)

```python
def resolve_target(tok, qr_list):
    # Default target (backward compatible)
    default_target = tok.get("encoded_content")

    # Check if role redirects enabled for this doctype
    rule = get_qr_rule(qr_list.target_doctype)
    if not rule or not rule.enable_role_redirects:
        return {"mode": "redirect", "target": default_target}

    # Guest users always get default
    if frappe.session.user == "Guest":
        return {"mode": "redirect", "target": default_target}

    # Get user's roles
    user_roles = set(frappe.get_roles())

    # Find all matching role redirects
    redirects = json.loads(rule.role_redirects_json or "[]")
    matching = [r for r in redirects if r["role"] in user_roles]
    matching.sort(key=lambda x: x.get("priority", 0))

    if len(matching) == 0:
        # No matching roles → default
        return {"mode": "redirect", "target": default_target}

    elif len(matching) == 1:
        # Exactly one match → direct redirect
        target = build_redirect_url(matching[0], qr_list)
        return {"mode": "redirect", "target": target}

    else:
        # Multiple matches → show choice page
        options = []
        for r in matching:
            options.append({
                "label": r["label"],
                "url": build_redirect_url(r, qr_list)
            })
        return {
            "mode": "choose",
            "options": options,
            "doctype": qr_list.target_doctype,
            "name": qr_list.target_name
        }


def build_redirect_url(redirect_config, qr_list):
    if redirect_config["redirect_type"] == "custom_url":
        url = redirect_config["custom_url"]
        # Replace placeholders
        url = url.replace("{name}", qr_list.target_name)
        url = url.replace("{doctype}", qr_list.target_doctype)
        url = url.replace("{doctype_slug}", slugify(qr_list.target_doctype))
        # Handle {field:FIELDNAME} placeholders
        url = replace_field_placeholders(url, qr_list)
        return get_url(url)
    else:
        # Action-based redirect
        action = redirect_config["redirect_action"]
        return build_action_url(qr_list.target_doctype, qr_list.target_name, action)
```

---

## Fallback Strategy (Option C)

**Principle**: If a role redirect fails, remove it from options. Never break the QR code.

| Failure | Behavior |
|---------|----------|
| `custom_url` placeholder fails | Remove that option from list |
| `redirect_action` invalid | Remove that option from list |
| Target doc doesn't exist | Remove that option from list |
| All options fail | Fall back to default `encoded_content` |
| Config missing/corrupt | Fall back to default `encoded_content` |

**Graceful Degradation Flow:**
```
matching = [r for r in redirects if r["role"] in user_roles]
valid = [r for r in matching if build_url_succeeds(r)]

len(valid) == 0  → default encoded_content
len(valid) == 1  → direct redirect
len(valid) >= 2  → choice page
```

---

## Backward Compatibility Guarantees

| Scenario | Behavior |
|----------|----------|
| Existing installation, no config changes | Works exactly as before |
| `enable_role_redirects` = 0 (default) | Works exactly as before |
| `enable_role_redirects` = 1, no role rules | Works exactly as before |
| `enable_role_redirects` = 1, user is Guest | Works exactly as before |
| `enable_role_redirects` = 1, user logged in, 0 matching roles | Uses default `encoded_content` |
| `enable_role_redirects` = 1, user logged in, 1 matching role | Direct redirect to role target |
| `enable_role_redirects` = 1, user logged in, 2+ matching roles | Shows choice page |

---

## Files to Create/Modify

| File | Action | Description |
|------|--------|-------------|
| `qr_foundry/qr_foundry/doctype/qr_role_redirect/` | **CREATE** | New child table doctype (4 files) |
| `qr_foundry/qr_foundry/doctype/qr_settings_rule/qr_settings_rule.json` | **MODIFY** | Add `enable_role_redirects` + `role_redirects` table |
| `qr_foundry/qr_foundry/doctype/qr_rule/qr_rule.json` | **MODIFY** | Add `enable_role_redirects` + `role_redirects_json` |
| `qr_foundry/qr_foundry/doctype/qr_settings/qr_settings.py` | **MODIFY** | Sync role config to QR Rule cache |
| `qr_foundry/www/qr/index.py` | **MODIFY** | Add role-based resolution logic |
| `qr_foundry/www/qr/index.html` | **MODIFY** | Add choice page template |
| `qr_foundry/patches/add_role_redirect_fields.py` | **CREATE** | Migration patch for existing installs |

---

## Implementation Phases

### Phase 1: Schema Changes (no behavioral change)
1. Create `QR Role Redirect` child table doctype
2. Add fields to `QR Settings Rule`
3. Add fields to `QR Rule`
4. Update `QR Settings.on_update()` to sync new fields
5. Create migration patch

### Phase 2: Resolver Logic
6. Add helper functions in resolver:
   - `_get_role_redirects()` - fetch matching redirects for user
   - `_build_redirect_url()` - build URL from config
   - `_replace_placeholders()` - handle `{name}`, `{field:X}` etc.
7. Integrate into `get_context()` with smart mode logic

### Phase 3: Choice Page UI
8. Update `index.html` template for choice page mode
9. Style the choice page buttons

### Phase 4: Testing
10. Test existing tokens still work (no role config)
11. Test guest users always get default
12. Test single role match → direct redirect
13. Test multiple role matches → choice page
14. Test custom URL placeholders

---

## Example Configuration

**QR Settings → Rules:**

| DocType | Link Type | Action | Enable Role Redirects |
|---------|-----------|--------|----------------------|
| Sales Order | Token | view | ✓ |

**Role Redirects for Sales Order:**

| Role | Label | Type | Action | Custom URL | Priority |
|------|-------|------|--------|------------|----------|
| Sales Manager | Edit Order | action | edit | | 0 |
| Sales User | View Order | action | view | | 1 |
| Accounts User | Print Invoice | action | print | | 2 |
| Cashier | Open in POS | custom_url | | /app/point-of-sale?sales_order={name} | 3 |
| Customer | My Orders | custom_url | | /portal/orders/{name} | 4 |

**Results:**

| User Has Roles | Result |
|----------------|--------|
| Guest | Default redirect |
| [Sales Manager] | Direct → Edit form |
| [Sales User] | Direct → View form |
| [Sales Manager, Sales User] | Choice page with 2 options |
| [Sales Manager, Cashier] | Choice page with 2 options |
| [HR Manager] (no match) | Default redirect |
