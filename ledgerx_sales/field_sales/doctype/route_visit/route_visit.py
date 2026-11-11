import frappe
from frappe import _
from frappe.model.document import Document


class RouteVisit(Document):
	def validate(self):
		if self.status == "Completed" and not self.outcome:
			frappe.throw(_("Choose the visit outcome"))
		if self.check_in and self.check_out and self.check_out < self.check_in:
			frappe.throw(_("Check-out cannot be before check-in"))
