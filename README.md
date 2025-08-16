# QR Foundry

A comprehensive QR code generation and management system for Frappe/ERPNext that provides secure, token-based QR codes with multiple encoding modes and extensive customization options.

## Features

- **Multiple QR Modes**: URL, Value, and Manual content encoding
- **Token Security**: Secure token-based access with expiry and usage limits
- **Template System**: Reusable QR templates for different actions
- **Audit Trail**: Complete scan logging with atomic operations
- **Dynamic Fields**: Smart field population based on DocType selection
- **Workspace Integration**: Dedicated workspace with shortcuts and reports

## Quick Start

### Installation

```bash
# 1. Get the app (skip assets to avoid build conflicts)
bench get-app https://github.com/BBbrighton/qr_foundry --skip-assets

# 2. Add to apps registry
echo "qr_foundry" >> ~/frappe-bench/sites/apps.txt

# 3. Install to your site
bench --site [your-site] install-app qr_foundry

# 4. Build assets (optional, if you need frontend features)
bench build --app qr_foundry
```

### Basic Usage

1. **Access QR Foundry**: Navigate to the QR Foundry workspace
2. **Create QR List**: Add new QR codes with your preferred mode
3. **Generate QR**: Use the "Generate / Refresh" button to create QR images
4. **Scan & Track**: All scans are automatically logged with full audit trail

## QR Modes

### URL Mode
Generate QR codes that redirect to specific documents or custom URLs.

**Use Cases:**
- Link to document views (`/app/sales-invoice/INV-001`)
- Direct to print formats with specific parameters
- Custom routes for special workflows
- External URLs with full domain

**Configuration:**
- **Target DocType & Document**: Automatic route generation
- **Custom Route**: Manual route specification (e.g., `/app/custom-page`)
- **Target URL**: External URLs (automatically prefixed with site URL if relative)
- **Action**: View, Edit, or Print behavior

### Value Mode
Encode field values directly in the QR code content.

**Use Cases:**
- Employee ID cards with employee codes
- Asset tags with serial numbers
- Contact cards with phone numbers or emails
- Product codes for inventory tracking

**Configuration:**
- **Value DocType**: Source document type
- **Value Document**: Specific document instance
- **Value Field**: Field containing the data to encode
- Dynamic field selection based on DocType

### Manual Mode
Direct content encoding for maximum flexibility.

**Use Cases:**
- WiFi connection strings
- Custom formatted data
- API endpoints or webhooks
- Structured data (JSON, XML, etc.)

**Configuration:**
- **Manual Content**: Direct text input
- Supports any text-based content up to QR code limits

## Core Components

### QR List DocType
Central management interface for QR code definitions.

**Key Fields:**
- `qr_mode`: Selection of URL/Value/Manual mode
- `label_text`: Optional label for QR display
- `target_doctype/target_name`: Document linking for URL mode
- `value_doctype/value_name/value_field`: Field value extraction for Value mode
- `manual_content`: Direct content for Manual mode
- `qr_token`: Associated security token
- `image`: Generated QR code attachment

### QR Token System
Secure token-based access control for QR codes.

**Features:**
- **Expiry Management**: Configurable expiration dates
- **Usage Limits**: Maximum scan count enforcement
- **Atomic Operations**: Race condition prevention
- **Status Tracking**: Active, Expired, Exhausted, Revoked states

### QR Scan Log DocType
Comprehensive audit trail for all QR code interactions.

**Tracked Data:**
- Scan timestamp and user
- IP address and user agent
- Token validation results
- Usage count at scan time
- Auto-generated naming series: `LOG-{YYYY}-{MM}-{#####}`

## Security Features

### Token-Based Access
All QR codes use secure tokens rather than direct document access, ensuring:
- Controlled access even for public QR codes
- Revocable access without changing QR content
- Usage tracking and limits
- Automatic expiry handling

### Atomic Operations
Critical operations use atomic updates to prevent race conditions:
- Token usage increment
- Status transitions
- Scan logging

### Permission Controls
- **QR Manager Role**: Full QR management access
- **System Manager**: Administrative oversight
- **User Permissions**: Controlled by Frappe's permission system

## API Reference

### Whitelisted Functions

#### QR Generation & Management

```python
@frappe.whitelist()
def preview_qr_list(name: str) -> dict
```
**Purpose**: Generate preview of QR code without saving
**Parameters**: `name` - QR List document name
**Returns**: `{"data_uri": "data:image/png;base64,..."}`

```python
@frappe.whitelist()
def generate_qr_list(name: str) -> dict
```
**Purpose**: Generate and attach QR image to QR List
**Parameters**: `name` - QR List document name  
**Returns**: `{"file_url": "/files/...", "absolute_file_url": "https://...", "name": "file-id"}`

#### Token Management

```python
@frappe.whitelist()
def create_qr_token(qr_list_name: str, expires_in_days: int = 365, max_uses: int = 0) -> dict
```
**Purpose**: Create secure token for QR List
**Parameters**: 
- `qr_list_name` - QR List document name
- `expires_in_days` - Expiry period (default: 365)
- `max_uses` - Usage limit (0 = unlimited)
**Returns**: `{"token": "secure-token-string", "expires_on": "2024-12-31"}`

```python
@frappe.whitelist()
def rotate_qr_token(qr_list_name: str) -> dict
```
**Purpose**: Generate new token and revoke old one
**Parameters**: `qr_list_name` - QR List document name
**Returns**: New token details

#### Field Utilities

```python
@frappe.whitelist()
def get_value_fields(doctype: str) -> list[dict]
```
**Purpose**: Get selectable fields for Value mode
**Parameters**: `doctype` - Target DocType name
**Returns**: `[{"label": "Field Label (Type)", "value": "fieldname"}, ...]`

#### Test Endpoints

```python
@frappe.whitelist()
def ping(name: str = None) -> dict
```
**Purpose**: Authentication test endpoint
**Parameters**: `name` - Optional name override
**Returns**: `{"ok": True, "name": "user", "site": "site", "now": "timestamp"}`

```python
@frappe.whitelist(allow_guest=True)
def ping_guest(name: str = "world") -> dict
```
**Purpose**: Guest access test endpoint
**Parameters**: `name` - Greeting name
**Returns**: `{"ok": True, "name": "name", "site": "site", "now": "timestamp", "guest": True}`

### Public Routes

#### QR Resolution
```
GET /qr?token={token}
```
**Purpose**: Resolve QR token to target content
**Parameters**: `token` - QR token string
**Behavior**: Validates token, logs scan, redirects to target or returns value

## Use Cases & Examples

### Document Sharing
**Scenario**: Share sales invoices with customers via QR codes
```
Mode: URL
Target DocType: Sales Invoice
Target Document: INV-2024-001
Action: view
```
**Result**: QR code links to read-only invoice view

### Asset Management
**Scenario**: Equipment tags with serial numbers
```
Mode: Value
Value DocType: Asset
Value Document: LAPTOP-001
Value Field: asset_serial_no
```
**Result**: QR contains serial number for scanning into inventory systems

### Event Check-in
**Scenario**: Event registration QR codes
```
Mode: Manual
Manual Content: {"event_id": "CONF2024", "ticket": "VIP-001", "name": "John Doe"}
```
**Result**: Structured data for event management system

### Print Integration
**Scenario**: Add QR codes to print formats
```html
<!-- In Print Format -->
<img src="{{ qr_list.absolute_file_url }}" style="width: 100px; height: 100px;">
```

## Configuration

### Required Dependencies
- `qrcode>=7.4` - QR code generation
- `Pillow>=10.0` - Image processing

### Frappe Integration
- **Hooks**: Automatic Frappe integration via `hooks.py`
- **Desktop**: QR Foundry workspace with shortcuts
- **Permissions**: Role-based access control

### Database Schema
The app creates these DocTypes:
- **QR List**: Main QR management interface
- **QR Token**: Security token storage
- **QR Scan Log**: Audit trail records

## Development

### Contributing

This app uses `pre-commit` for code formatting and linting. Please [install pre-commit](https://pre-commit.com/#installation) and enable it for this repository:

```bash
cd apps/qr_foundry
pre-commit install
```

Pre-commit is configured to use the following tools for checking and formatting your code:

- ruff
- eslint
- prettier
- pyupgrade

### Testing
```bash
# Test endpoints
curl -X POST "http://your-site/api/method/qr_foundry.utils.hello.ping_guest" \
  -H "Content-Type: application/json" \
  -d '{"name": "test"}'
```

### Extending
The modular design allows easy extension:
- Add new QR modes in `qr_ops.py`
- Custom token validation in `tokens.py`  
- Additional API endpoints in `api.py`

## Troubleshooting

### Common Issues

**QR codes not generating**
- Check QR Manager role assignment
- Verify PIL/Pillow installation
- Check file permission settings

**Token validation failing**
- Verify token hasn't expired
- Check usage limits not exceeded
- Ensure token status is "Active"

**Scans not logging**
- Check QR Scan Log DocType permissions
- Verify database connectivity
- Review error logs for cache issues

### Support
- Check Frappe logs for detailed error messages
- Use ping endpoints to verify API connectivity
- Review QR Scan Log for validation details

## Author

**X-DESK**  
Email: chotiputsilp.r@gmail.com  
GitHub: [BBbrighton](https://github.com/BBbrighton)

## Repository

- **GitHub**: [https://github.com/BBbrighton/qr_foundry](https://github.com/BBbrighton/qr_foundry)
- **Issues**: [Report bugs and feature requests](https://github.com/BBbrighton/qr_foundry/issues)
- **Contributions**: Pull requests welcome

## License

MIT
