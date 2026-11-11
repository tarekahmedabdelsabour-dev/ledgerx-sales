import frappe
from frappe import _
from frappe.model.document import Document
from frappe.utils import flt

from ledgerx_sales.utils import sales


class SalesmanCashHandover(Document):
	def validate(self):
		if flt(self.amount) <= 0:
			frappe.throw(_("Amount must be greater than zero"))
		s = sales.settings()
		sm = frappe.get_doc("Salesman", self.salesman)
		self.company = self.company or sales.company_of(sm, s)
		if self.method == "Bank Deposit":
			self.bank_account = self.bank_account or s.default_bank_account
			if not self.bank_account:
				frappe.throw(_("Choose the bank account"))
		if self.is_new():
			self.cash_in_hand = sales.cash_in_hand(self.salesman)
		if self.status == "Pending" and flt(self.amount) > flt(sales.cash_in_hand(self.salesman)) + 0.005 and self.is_new():
			frappe.throw(_("The amount is more than the cash in the salesman's hands ({0})").format(self.cash_in_hand))

	@frappe.whitelist()
	def confirm(self):
		"""The cashier / accountant confirms receipt: posts the journal entry."""
		frappe.only_for(("Sales Manager", "Accounts User", "System Manager"))
		if self.status != "Pending":
			frappe.throw(_("Only a pending handover can be confirmed"))
		if flt(self.amount) > flt(sales.cash_in_hand(self.salesman)) + 0.005:
			frappe.throw(_("The salesman's cash account holds less than this amount"))
		self.journal_entry = sales.make_handover_journal(self)
		self.status = "Confirmed"
		self.reviewed_by = frappe.session.user
		self.save(ignore_permissions=True)
		return self.journal_entry

	@frappe.whitelist()
	def reject(self, reason):
		frappe.only_for(("Sales Manager", "Accounts User", "System Manager"))
		if self.status != "Pending":
			frappe.throw(_("Only a pending handover can be rejected"))
		if not reason:
			frappe.throw(_("Enter the rejection reason"))
		self.status = "Rejected"
		self.rejection_reason = reason
		self.reviewed_by = frappe.session.user
		self.save(ignore_permissions=True)

	def on_trash(self):
		if self.status == "Confirmed":
			frappe.throw(_("A confirmed handover cannot be deleted"))
