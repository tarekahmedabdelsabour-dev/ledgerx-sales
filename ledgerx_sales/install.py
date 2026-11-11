import frappe
from frappe.custom.doctype.custom_field.custom_field import create_custom_fields

MODULE = "Field Sales"
ROLES = ("Field Salesman",)

TRACE = [
	dict(fieldname="fs_section", fieldtype="Section Break", label="Field Sales", insert_after="project", collapsible=1),
	dict(fieldname="salesman", fieldtype="Link", options="Salesman", label="Salesman", insert_after="fs_section",
		in_standard_filter=1, read_only=1, search_index=1),
	dict(fieldname="route_visit", fieldtype="Link", options="Route Visit", label="Route Visit", insert_after="salesman",
		read_only=1, no_copy=1),
	dict(fieldname="fs_request_id", fieldtype="Data", label="Request ID", insert_after="route_visit", hidden=1,
		read_only=1, no_copy=1, search_index=1),
]

CUSTOM_FIELDS = {
	"Sales Invoice": TRACE,
	"Payment Entry": TRACE,
	"Customer": [
		dict(fieldname="fs_section", fieldtype="Section Break", label="Field Sales", insert_after="territory", collapsible=1),
		dict(fieldname="default_salesman", fieldtype="Link", options="Salesman", label="Default Salesman",
			insert_after="fs_section", in_standard_filter=1),
		dict(fieldname="fs_col", fieldtype="Column Break", insert_after="default_salesman"),
		dict(fieldname="fs_latitude", fieldtype="Float", label="Shop Latitude", precision="6", insert_after="fs_col"),
		dict(fieldname="fs_longitude", fieldtype="Float", label="Shop Longitude", precision="6", insert_after="fs_latitude"),
	],
}


def check_app_permission():
	if frappe.session.user == "Administrator":
		return True
	return bool(set(frappe.get_roles()) & {"Sales Manager", "Sales User", "Accounts User", "System Manager"})


def after_install():
	_run(ensure_modules)
	_run(ensure_roles)
	_run(ensure_custom_fields)
	_run(seed_defaults)
	frappe.clear_cache()


def after_migrate():
	_run(ensure_modules)
	_run(ensure_roles)
	_run(ensure_custom_fields)
	frappe.clear_cache()


def _run(fn):
	"""One failing step must never abort install/migrate: log it and continue."""
	try:
		fn()
		frappe.db.commit()
	except Exception:
		frappe.db.rollback()
		frappe.log_error(title=f"ledgerx_sales install step failed: {fn.__name__}")


def ensure_modules():
	if not frappe.db.exists("Module Def", MODULE):
		frappe.get_doc({"doctype": "Module Def", "module_name": MODULE, "app_name": "ledgerx_sales"}).insert(ignore_permissions=True)


def ensure_roles():
	for role in ROLES:
		if not frappe.db.exists("Role", role):
			frappe.get_doc({"doctype": "Role", "role_name": role, "desk_access": 0}).insert(ignore_permissions=True)


def ensure_custom_fields():
	create_custom_fields(CUSTOM_FIELDS, update=True)


def seed_defaults():
	"""Fill Field Sales Settings with sensible guesses (every value can be changed afterwards)."""
	company = frappe.defaults.get_global_default("company")
	if not company:
		return
	s = frappe.get_single("Field Sales Settings")
	s.company = s.company or company
	abbr = frappe.get_cached_value("Company", company, "abbr")
	if not s.cash_parent_account:
		s.cash_parent_account = frappe.db.get_value("Account", {"company": company, "account_name": "Cash In Hand", "is_group": 1})
	if not s.cashier_account:
		s.cashier_account = frappe.db.get_value("Account", {"company": company, "account_name": "Cash", "is_group": 0}) or None
	if not s.default_price_list and frappe.db.exists("Price List", "Standard Selling"):
		s.default_price_list = "Standard Selling"
	if not s.main_warehouse:
		s.main_warehouse = frappe.db.get_value("Warehouse", {"company": company, "is_group": 0, "name": ["like", "Stores%"]})
	if not s.cost_center:
		s.cost_center = frappe.db.get_value("Company", company, "cost_center")
	if not s.commission_component:
		name = "Field Sales Commission"
		if not frappe.db.exists("Salary Component", name):
			try:
				frappe.get_doc({"doctype": "Salary Component", "salary_component": name, "salary_component_abbr": "FSC",
					"type": "Earning"}).insert(ignore_permissions=True)
			except Exception:
				name = None
		s.commission_component = name
	s.save(ignore_permissions=True)
