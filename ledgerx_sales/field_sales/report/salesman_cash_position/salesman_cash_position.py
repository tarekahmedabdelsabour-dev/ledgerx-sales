import frappe
from frappe import _
from frappe.utils import flt, nowdate

from ledgerx_sales.utils import sales


def execute(filters=None):
	filters = frappe._dict(filters or {})
	f = {"status": ["!=", "Inactive"]}
	if filters.company:
		f["company"] = filters.company
	if filters.salesman:
		f["name"] = filters.salesman
	data = []
	for s in frappe.get_all("Salesman", filters=f, fields=["name", "salesman_name", "cash_account"]):
		today_col = flt(frappe.db.sql("SELECT COALESCE(SUM(paid_amount),0) FROM `tabPayment Entry` WHERE salesman=%s AND posting_date=%s "
			"AND docstatus=1 AND payment_type='Receive' AND paid_to=%s", (s.name, nowdate(), s.cash_account or ""))[0][0])
		today_hand = flt(frappe.db.sql("SELECT COALESCE(SUM(amount),0) FROM `tabSalesman Cash Handover` WHERE salesman=%s "
			"AND posting_date=%s AND status='Confirmed'", (s.name, nowdate()))[0][0])
		last = frappe.db.get_value("Salesman Settlement", {"salesman": s.name, "docstatus": 1}, "settlement_date", order_by="settlement_date desc")
		data.append({"salesman": s.name, "salesman_name": s.salesman_name, "in_hand": sales.cash_in_hand(s.name),
			"pending": sales.pending_handover(s.name), "collected_today": today_col, "handed_today": today_hand, "last_close": last})
	cols = [
		{"fieldname": "salesman", "label": _("Salesman"), "fieldtype": "Link", "options": "Salesman", "width": 110},
		{"fieldname": "salesman_name", "label": _("Salesman Name"), "fieldtype": "Data", "width": 160},
		{"fieldname": "in_hand", "label": _("Cash in Hand"), "fieldtype": "Currency", "width": 130},
		{"fieldname": "pending", "label": _("Pending Handover"), "fieldtype": "Currency", "width": 130},
		{"fieldname": "collected_today", "label": _("Collected Today"), "fieldtype": "Currency", "width": 130},
		{"fieldname": "handed_today", "label": _("Handed Over Today"), "fieldtype": "Currency", "width": 140},
		{"fieldname": "last_close", "label": _("Last Day Close"), "fieldtype": "Date", "width": 120},
	]
	return cols, data
