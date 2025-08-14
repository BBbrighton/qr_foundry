# Claude Memory - QR Foundry Project

## Project Overview
Building a clean, extensible QR code generation and management system for Frappe/ERPNext based on the comprehensive skeleton in `/skeleton/qr_foundry_a_clean_extensible_qr_app_skeleton_for_frappe_erpnext.md`

## Current Status
- Working Directory: `/home/brighton/frappe-bench/apps/qr_foundry`
- Framework: Frappe/ERPNext v15
- Purpose: QR code generation with token management, templates, and multiple action types

## Todo List

### Completed ✅
1. ✅ Update requirements.txt with QR dependencies
2. ✅ Create MANIFEST.in for package distribution

### In Progress 🔄
3. 🔄 Create setup.py for package installation

### Pending ⏳
4. ⏳ Create qr_foundry/__init__.py with version
5. ⏳ Create hooks.py for Frappe integration
6. ⏳ Create config/desktop.py for UI menu
7. ⏳ Create utils/qr.py for QR generation
8. ⏳ Create utils/tokens.py for token management
9. ⏳ Create api.py for API endpoints
10. ⏳ Create www/qr/index.py for web routes
11. ⏳ Create templates/includes/print/qr_macros.html
12. ⏳ Create public/js/qr_button.js for client-side
13. ⏳ Create public/css/qr.css for styling
14. ⏳ Create patches.txt for migrations
15. ⏳ Create patches/post/seed_default_templates.py
16. ⏳ Create tests/test_tokens.py
17. ⏳ Create QR Settings DocType
18. ⏳ Create QR Template DocType
19. ⏳ Create QR Token DocType
20. ⏳ Create README.md

## Key Features to Implement
- **QR Generation**: Using qrcode library with PIL for image manipulation
- **Token System**: Secure token generation with expiry and max-use limits
- **Templates**: Configurable QR templates for different actions (View, Edit, Print, etc.)
- **Action Types**: 
  - View Doc
  - Edit Doc
  - Print Doc
  - New Doc
  - Report
  - Route
  - Server Method
  - URL
- **Security**: Token-based access control with atomic usage tracking
- **Integration**: Global QR button added to all Frappe forms via client-side JS

## Directory Structure Required
```
qr_foundry/
├── qr_foundry/
│   ├── __init__.py
│   ├── hooks.py
│   ├── api.py
│   ├── config/
│   │   └── desktop.py
│   ├── utils/
│   │   ├── qr.py
│   │   └── tokens.py
│   ├── doctype/
│   │   ├── qr_settings/
│   │   │   ├── qr_settings.json
│   │   │   └── qr_settings.py
│   │   ├── qr_settings_doctype_row/
│   │   │   ├── qr_settings_doctype_row.json
│   │   │   └── qr_settings_doctype_row.py
│   │   ├── qr_template/
│   │   │   ├── qr_template.json
│   │   │   └── qr_template.py
│   │   └── qr_token/
│   │       ├── qr_token.json
│   │       └── qr_token.py
│   ├── patches/
│   │   └── post/
│   │       └── seed_default_templates.py
│   ├── public/
│   │   ├── js/
│   │   │   └── qr_button.js
│   │   └── css/
│   │       └── qr.css
│   ├── templates/
│   │   └── includes/
│   │       └── print/
│   │           └── qr_macros.html
│   ├── www/
│   │   └── qr/
│   │       └── index.py
│   └── tests/
│       └── test_tokens.py
├── requirements.txt
├── MANIFEST.in
├── setup.py
├── patches.txt
└── README.md
```

## Installation Commands (After Setup)
```bash
# Install & migrate
bench --site <yoursite> install-app qr_foundry
bench --site <yoursite> migrate
bench build

# Seed sample templates
bench --site <yoursite> reload-doc qr_foundry qr_foundry doctype qr_settings
bench --site <yoursite> reload-doc qr_foundry qr_foundry doctype qr_template
bench --site <yoursite> reload-doc qr_foundry qr_foundry doctype qr_token
bench --site <yoursite> run-patch qr_foundry.patches.post.seed_default_templates
```

## Important Notes
- Focus on clarity, minimalism, and safe defaults
- The app requires adding an "qr_image" (Attach Image) field to target DocTypes
- Token system includes expiry tracking and atomic usage counting
- All QR images can be saved as public or private files
- Template system supports Jinja2 templating for dynamic content

## Next Steps
Continue creating the remaining files following the skeleton structure, starting with:
1. Complete setup.py
2. Create the core Python package structure
3. Implement utility modules
4. Set up DocTypes
5. Add client-side functionality