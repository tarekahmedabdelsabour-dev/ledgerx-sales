import frappe
from frappe import _
from frappe.model.document import Document
from frappe.utils import flt, getdate

from ledgerx_sales.utils import logic, sales


class SalesmanSettlement(Document):
	def validate(self):
		sm = frappe.get_doc("Salesman", self.salesman)
		s = sales.settings()
		self.company = self.company or sales.company_of(sm, s)
		dup = frappe.db.exists("Salesman Settlement", {"salesman": self.salesman, "settlement_date": self.settlement_date,
			"docstatus": 1, "name": ["!=", self.name]})
		if dup:
			frappe.throw(_("The day of {0} is already closed for this salesman ({1})").format(self.settlement_date, dup))
		self.compute(sm)
		if abs(flt(self.difference)) > flt(s.day_close_tolerance) and not (self.remarks or "").strip():
			frappe.throw(_("The cash difference is {0}. Write the reason in the remarks.").format(self.difference))

	def compute(self, sm):
		d = getdate(self.settlement_date)
		sm_name = self.salesman
		r = frappe.db.sql("SELECT COALESCE(SUM(grand_total),0), COALESCE(SUM(outstanding_amount),0) FROM `tabSales Invoice` "
			"WHERE salesman=%s AND posting_date=%s AND docstatus=1", (sm_name, d))[0]
		self.invoiced_total, self.credit_given = flt(r[0]), flt(r[1])
		cash = frappe.db.sql("SELECT COALESCE(SUM(paid_amount),0) FROM `tabPayment Entry` WHERE salesman=%s AND posting_date=%s "
			"AND docstatus=1 AND payment_type='Receive' AND paid_to=%s", (sm_name, d, sm.cash_account or ""))[0][0]
		allp = frappe.db.sql("SELECT COALESCE(SUM(paid_amount),0) FROM `tabPayment Entry` WHERE salesman=%s AND posting_date=%s "
			"AND docstatus=1 AND payment_type='Receive'", (sm_name, d))[0][0]
		self.collections_cash, self.collections_other = flt(cash), flt(allp) - flt(cash)
		self.handed_over = flt(frappe.db.sql("SELECT COALESCE(SUM(amount),0) FROM `tabSalesman Cash Handover` WHERE salesman=%s "
			"AND posting_date=%s AND status='Confirmed'", (sm_name, d))[0][0])
		self.cash_in_hand = sales.cash_in_hand(sm_name, d)
		self.difference = logic.settlement_difference(self.cash_counted, self.cash_in_hand)
		self.visits_planned = frappe.db.count("Route Visit", {"salesman": sm_name, "visit_date": d})
		self.visits_completed = frappe.db.count("Route Visit", {"salesman": sm_name, "visit_date": d, "status": "Completed"})
		self.distance_km = self.day_distance(sm, d)
		stock = sales.van_stock(sm.warehouse)
		for row in self.stock_lines:
			row.system_qty = flt(stock.get(row.item_code, 0))
			row.difference = flt(row.counted_qty) - row.system_qty

	@staticmethod
	def day_distance(sm, d):
		if not sm.driver:
			return 0
		try:
			r = frappe.db.sql("SELECT COALESCE(SUM(day_distance),0) FROM `tabDriver Odometer Log` WHERE driver=%s AND log_date=%s",
				(sm.driver, d))
			return int(r[0][0])
		except Exception:
			return 0
