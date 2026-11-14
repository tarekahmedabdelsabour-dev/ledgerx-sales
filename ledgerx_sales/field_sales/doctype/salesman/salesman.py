import frappe
from frappe import _
from frappe.model.document import Document
from frappe.utils import flt

from ledgerx_sales.utils import logic, sales


class Salesman(Document):
	def validate(self):
		if self.user and frappe.db.exists("Salesman", {"user": self.user, "name": ["!=", self.name]}):
			frappe.throw(_("User {0} is already linked to another salesman").format(self.user))
		s = sales.settings()
		self.company = self.company or s.company
		self.cost_center = self.cost_center or s.cost_center
		self.price_list = self.price_list or s.default_price_list
		# one person: the same user may also be a driver and an employee, link them without retyping
		if self.user and not self.driver:
			self.driver = frappe.db.get_value("Driver", {"user": self.user, "status": "Active"}, "name")
		if not self.employee:
			from ledgerx_sales.utils import hr_link

			self.employee = hr_link.employee_of(self)
		if self.driver and not self.vehicle:
			self.vehicle = frappe.db.get_value("Driver", self.driver, "current_vehicle")
		# a default coming from the form can still be text at this point, so convert before comparing
		self.max_discount_percent = flt(self.max_discount_percent)
		if self.max_discount_percent < 0 or self.max_discount_percent > 100:
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
		from ledgerx_sales.utils import hr_link

		if not hr_link.employee_of(self):
			frappe.throw(_("Link the salesman to an Employee first"))
		if not s.commission_component:
			frappe.throw(_("Set the commission salary component in Field Sales Settings"))
		base = sales.period_base(self, from_date, to_date)
		if logic.commission(base, self.commission_percent) <= 0:
			frappe.throw(_("No commission is due for this period"))
		name = hr_link.make_commission(self, from_date, to_date, s)
		if not name:
			frappe.throw(_("A commission for this period was already created"))
		return name
