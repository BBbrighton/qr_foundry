app_name = "qr_foundry"
app_title = "QR Foundry "
app_publisher = "X-Desk"
app_description = "QR Management APP"
app_email = "Chotiputsilp.r@gmail.com"
app_license = "mit"

# Apps
# ------------------

# required_apps = []

# Each item in the list will be shown as an app in the apps page
# add_to_apps_screen = [
# 	{
# 		"name": "qr_foundry",
# 		"logo": "/assets/qr_foundry/logo.png",
# 		"title": "QR Foundry ",
# 		"route": "/qr_foundry",
# 		"has_permission": "qr_foundry.api.permission.has_app_permission"
# 	}
# ]

# Includes in <head>
# ------------------

# REPLACE/SET app_include_js to the universal buttons file
app_include_js = [
	"/assets/qr_foundry/js/qr_foundry/buttons.js",  # universal doc buttons
]

# DO NOT include app_include_css unless the file actually exists

# include js, css files in header of web template
# web_include_css = "/assets/qr_foundry/css/qr_foundry.css"
# web_include_js = "/assets/qr_foundry/js/qr_foundry.js"

# include custom scss in every website theme (without file extension ".scss")
# website_theme_scss = "qr_foundry/public/scss/website"

# include js, css files in header of web form
# webform_include_js = {"doctype": "public/js/doctype.js"}
# webform_include_css = {"doctype": "public/css/doctype.css"}

# include js in page
# page_js = {"page" : "public/js/file.js"}

# include js in doctype views
doctype_js = {"QR List": "public/js/qr_foundry/qr_list_buttons.js"}
# doctype_list_js = {"doctype" : "public/js/doctype_list.js"}
# doctype_tree_js = {"doctype" : "public/js/doctype_tree.js"}
# doctype_calendar_js = {"doctype" : "public/js/doctype_calendar.js"}

# Svg Icons
# ------------------
# include app icons in desk
# app_include_icons = "qr_foundry/public/icons.svg"

# Home Pages
# ----------

# application home page (will override Website Settings)
# home_page = "login"

# website user home page (by Role)
# role_home_page = {
# 	"Role": "home_page"
# }

# Generators
# ----------

# automatically create page for each record of this doctype
# website_generators = ["Web Page"]

# Jinja
# ----------

# add methods and filters to jinja environment
jinja = {
	"methods": [
		"qr_foundry.print_helpers.qr_data_uri",
		"qr_foundry.print_helpers.embed_file",
	]
}

# Installation
# ------------

# before_install = "qr_foundry.install.before_install"
# after_install = "qr_foundry.install.after_install"

after_migrate = [
	"qr_foundry.patches.ensure_qr_manager_role.run",
	"qr_foundry.patches.cleanup_legacy_client_scripts.run",
]

# Boot Session
# ------------
boot_session = "qr_foundry.boot.boot_session"

# Uninstallation
# ------------

# before_uninstall = "qr_foundry.uninstall.before_uninstall"
# after_uninstall = "qr_foundry.uninstall.after_uninstall"

# Integration Setup
# ------------------
# To set up dependencies/integrations with other apps
# Name of the app being installed is passed as an argument

# before_app_install = "qr_foundry.utils.before_app_install"
# after_app_install = "qr_foundry.utils.after_app_install"

# Integration Cleanup
# -------------------
# To clean up dependencies/integrations with other apps
# Name of the app being uninstalled is passed as an argument

# before_app_uninstall = "qr_foundry.utils.before_app_uninstall"
# after_app_uninstall = "qr_foundry.utils.after_app_uninstall"

# Desk Notifications
# ------------------
# See frappe.core.notifications.get_notification_config

# notification_config = "qr_foundry.notifications.get_notification_config"

# Permissions
# -----------
# Permissions evaluated in scripted ways

# permission_query_conditions = {
# 	"Event": "frappe.desk.doctype.event.event.get_permission_query_conditions",
# }
#
# has_permission = {
# 	"Event": "frappe.desk.doctype.event.event.has_permission",
# }

# DocType Class
# ---------------
# Override standard doctype classes

# Jinja Methods for Print Formats
# ----------------------------------
jinja = {
	"methods": [
		"qr_foundry.print_helpers.qr_src",
		"qr_foundry.print_helpers.qr_data_uri",
	]
}

# override_doctype_class = {
# 	"ToDo": "custom_app.overrides.CustomToDo"
# }

# Document Events
# ---------------
# Hook on document methods and events

doc_events = {"*": {"after_insert": "qr_foundry.hooks_impl.after_insert_autogen"}}

# Scheduled Tasks
# ---------------

# scheduler_events = {
# 	"all": [
# 		"qr_foundry.tasks.all"
# 	],
# 	"daily": [
# 		"qr_foundry.tasks.daily"
# 	],
# 	"hourly": [
# 		"qr_foundry.tasks.hourly"
# 	],
# 	"weekly": [
# 		"qr_foundry.tasks.weekly"
# 	],
# 	"monthly": [
# 		"qr_foundry.tasks.monthly"
# 	],
# }

# Testing
# -------

# before_tests = "qr_foundry.install.before_tests"

# Overriding Methods
# ------------------------------
#
# override_whitelisted_methods = {
# 	"frappe.desk.doctype.event.event.get_events": "qr_foundry.event.get_events"
# }
#
# each overriding function accepts a `data` argument;
# generated from the base implementation of the doctype dashboard,
# along with any modifications made in other Frappe apps
# override_doctype_dashboards = {
# 	"Task": "qr_foundry.task.get_dashboard_data"
# }

# exempt linked doctypes from being automatically cancelled
#
# auto_cancel_exempted_doctypes = ["Auto Repeat"]

# Ignore links to specified DocTypes when deleting documents
# -----------------------------------------------------------

# ignore_links_on_delete = ["Communication", "ToDo"]

# Request Events
# ----------------
# before_request = ["qr_foundry.utils.before_request"]
# after_request = ["qr_foundry.utils.after_request"]

# Job Events
# ----------
# before_job = ["qr_foundry.utils.before_job"]
# after_job = ["qr_foundry.utils.after_job"]

# User Data Protection
# --------------------

# user_data_fields = [
# 	{
# 		"doctype": "{doctype_1}",
# 		"filter_by": "{filter_by}",
# 		"redact_fields": ["{field_1}", "{field_2}"],
# 		"partial": 1,
# 	},
# 	{
# 		"doctype": "{doctype_2}",
# 		"filter_by": "{filter_by}",
# 		"partial": 1,
# 	},
# 	{
# 		"doctype": "{doctype_3}",
# 		"strict": False,
# 	},
# 	{
# 		"doctype": "{doctype_4}"
# 	}
# ]

# Authentication and authorization
# --------------------------------

# auth_hooks = [
# 	"qr_foundry.auth.validate"
# ]

# Automatically update python controller files with type annotations for this app.
# export_python_type_annotations = True

# default_log_clearing_doctypes = {
# 	"Logging DocType Name": 30  # days to retain logs
# }
