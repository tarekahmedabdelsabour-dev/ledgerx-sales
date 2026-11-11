from ledgerx_sales import __version__ as app_version  # noqa: F401

app_name = "ledgerx_sales"
app_title = "LedgerX Sales"
app_publisher = "LedgerX"
app_description = "Field sales for ERPNext: a mobile screen for the salesman with van stock, routes, collections, cash handover and day close"
app_email = "hello@ledgerx.local"
app_license = "mit"

required_apps = ["erpnext"]

app_include_icons = ["/assets/ledgerx_sales/icons/module-icons.svg"]

add_to_apps_screen = [
	{
		"name": "ledgerx_sales",
		"logo": "/assets/ledgerx_sales/images/sales.svg",
		"title": "Field Sales",
		"route": "/desk/field-sales",
		"has_permission": "ledgerx_sales.install.check_app_permission",
	}
]

# Customer form: shortcuts to the salesman's data
doctype_js = {"Customer": "public/js/customer.js"}

after_install = "ledgerx_sales.install.after_install"
after_migrate = "ledgerx_sales.install.after_migrate"
