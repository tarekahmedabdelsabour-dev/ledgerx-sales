import frappe
from frappe import _
from frappe.model.document import Document


class SalesRoute(Document):
	def validate(self):
		seen = set()
		for i, r in enumerate(self.customers, start=1):
			if r.customer in seen:
				frappe.throw(_("Row {0}: customer {1} is repeated").format(r.idx, r.customer))
			seen.add(r.customer)
			if not r.sequence:
				r.sequence = i
		self.company = self.company or frappe.defaults.get_global_default("company")
