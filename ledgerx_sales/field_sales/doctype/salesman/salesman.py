import frappe
from frappe import _
from frappe.model.document import Document

from ledgerx_sales.utils import sales


class Salesman(Document):
	def validate(self):
		if self.user and frappe.db.exists("Salesman", {"user": self.user, "name": ["!=", self.name]}):
			frappe.throw(_("User {0} is already linked to another salesman").format(self.user))
		s = sales.settings()
		self.company = self.company or s.company
		self.cost_center = self.cost_center or s.cost_center
		self.price_list = self.price_list or s.default_price_list
		if self.driver and not self.vehicle:
			self.vehicle = frappe.db.get_value("Driver", self.driver, "current_vehicle")
		if self.max_discount_percent and (self.max_discount_percent < 0 or self.max_discount_percent > 100):
			frappe.throw(_("Max Discount % must be between 0 and 100"))

	def on_update(self):
		self.ensure_role()

	def ensure_role(self):
		if self.user and self.status == "Active" and not frappe.db.exists("Has Role", {"parent": self.user, "role": sales.SALESMAN_ROLE}):
			u = frappe.get_doc("User", self.user)
			u.append("roles", {"role": sales.SALESMAN_ROLE})
			u.save(ignore_permissions=True)

	@frappe.whitelist()
	def create_accounts(self):
		"""Create the van warehouse and the personal cash account if they are missing."""
		frappe.only_for(("Sales Manager", "System Manager"))
		s = sales.settings()
		company = sales.company_of(self, s)
		made = []
		if not self.warehouse:
			base = _("Van {0}").format(self.salesman_name)
			parent = s.main_warehouse and frappe.db.get_value("Warehouse", s.main_warehouse, "parent_warehouse")
			wh = frappe.get_doc({"doctype": "Warehouse", "warehouse_name": base, "company": company,
				"parent_warehouse": parent or None}).insert(ignore_permissions=True)
			self.warehouse = wh.name
			made.append(wh.name)
		if not self.cash_account:
			if not s.cash_parent_account:
				frappe.throw(_("Set the parent group for salesman cash accounts in Field Sales Settings first"))
			root, rtype = frappe.db.get_value("Account", s.cash_parent_account, ["root_type", "account_type"])
			acc = frappe.get_doc({"doctype": "Account", "account_name": _("Cash - {0}").format(self.salesman_name),
				"parent_account": s.cash_parent_account, "company": company, "is_group": 0, "account_type": "Cash",
				"root_type": root}).insert(ignore_permissions=True)
			self.cash_account = acc.name
			made.append(acc.name)
		self.save(ignore_permissions=True)
		return made

	@frappe.whitelist()
	def create_commission(self, from_date, to_date):
		"""HR link: an Additional Salary for the commission earned in a period."""
		frappe.only_for(("Sales Manager", "System Manager"))
		s = sales.settings()
		if not self.employee:
			frappe.throw(_("Link the salesman to an Employee first"))
		if not s.commission_component:
			frappe.throw(_("Set the commission salary component in Field Sales Settings"))
		from ledgerx_sales.utils import logic

		base = sales.period_base(self, from_date, to_date)
		amount = logic.commission(base, self.commission_percent)
		if amount <= 0:
			frappe.throw(_("No commission is due for this period"))
		doc = frappe.get_doc({"doctype": "Additional Salary", "employee": self.employee,
			"salary_component": s.commission_component, "amount": amount, "payroll_date": to_date,
			"company": sales.company_of(self, s), "overwrite_salary_structure_amount": 1}).insert(ignore_permissions=True)
		return doc.name
