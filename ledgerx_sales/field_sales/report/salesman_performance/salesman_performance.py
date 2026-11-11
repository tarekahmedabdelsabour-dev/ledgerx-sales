import frappe
from frappe import _
from frappe.utils import flt

from ledgerx_sales.utils import logic, sales


def execute(filters=None):
	filters = frappe._dict(filters or {})
	f = {}
	if filters.company:
		f["company"] = filters.company
	if filters.salesman:
		f["name"] = filters.salesman
	fd, td = filters.from_date, filters.to_date
	data = []
	for s in frappe.get_all("Salesman", filters=f, fields=["name", "salesman_name", "monthly_target", "commission_percent", "commission_basis"]):
		inv = frappe.db.sql("SELECT COALESCE(SUM(grand_total),0), COUNT(*) FROM `tabSales Invoice` WHERE salesman=%s AND docstatus=1 "
			"AND posting_date BETWEEN %s AND %s", (s.name, fd, td))[0]
		col = sales.period_base(frappe._dict(name=s.name, commission_basis="Collected"), fd, td)
		v = frappe.db.sql("SELECT COUNT(*), COALESCE(SUM(status='Completed'),0), COALESCE(SUM(out_of_range),0), "
			"COALESCE(SUM(outcome IN ('Sale','Sale and Collection')),0) FROM `tabRoute Visit` WHERE salesman=%s AND visit_date BETWEEN %s AND %s", (s.name, fd, td))[0]
		diff = flt(frappe.db.sql("SELECT COALESCE(SUM(difference),0) FROM `tabSalesman Settlement` WHERE salesman=%s AND docstatus=1 "
			"AND settlement_date BETWEEN %s AND %s", (s.name, fd, td))[0][0])
		base = inv[0] if s.commission_basis == "Invoiced" else col
		data.append({"salesman": s.name, "salesman_name": s.salesman_name, "invoices": inv[1], "sales": flt(inv[0]), "collected": col,
			"target": flt(s.monthly_target), "progress": logic.target_progress(inv[0], s.monthly_target),
			"visits": v[0], "completed": v[1], "productive": v[3], "out_of_range": v[2],
			"hit_rate": round(v[3] / v[1] * 100, 1) if v[1] else 0, "cash_difference": diff,
			"commission": logic.commission(base, s.commission_percent)})
	cols = [
		{"fieldname": "salesman", "label": _("Salesman"), "fieldtype": "Link", "options": "Salesman", "width": 100},
		{"fieldname": "salesman_name", "label": _("Salesman Name"), "fieldtype": "Data", "width": 150},
		{"fieldname": "invoices", "label": _("Invoices"), "fieldtype": "Int", "width": 80},
		{"fieldname": "sales", "label": _("Sales"), "fieldtype": "Currency", "width": 120},
		{"fieldname": "collected", "label": _("Collected"), "fieldtype": "Currency", "width": 120},
		{"fieldname": "target", "label": _("Monthly Sales Target"), "fieldtype": "Currency", "width": 120},
		{"fieldname": "progress", "label": _("Target %"), "fieldtype": "Percent", "width": 90},
		{"fieldname": "visits", "label": _("Visits"), "fieldtype": "Int", "width": 70},
		{"fieldname": "completed", "label": _("Completed"), "fieldtype": "Int", "width": 90},
		{"fieldname": "productive", "label": _("Productive Visits"), "fieldtype": "Int", "width": 110},
		{"fieldname": "hit_rate", "label": _("Hit Rate %"), "fieldtype": "Percent", "width": 90},
		{"fieldname": "out_of_range", "label": _("Out of Range"), "fieldtype": "Int", "width": 90},
		{"fieldname": "cash_difference", "label": _("Cash Difference"), "fieldtype": "Currency", "width": 110},
		{"fieldname": "commission", "label": _("Commission"), "fieldtype": "Currency", "width": 110},
	]
	return cols, data
