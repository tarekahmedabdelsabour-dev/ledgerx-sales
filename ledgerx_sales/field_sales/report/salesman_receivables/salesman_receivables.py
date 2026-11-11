import frappe
from frappe import _
from frappe.utils import flt, getdate, nowdate

from ledgerx_sales.utils import logic

BUCKETS = ["current", "1-30", "31-60", "61-90", "90+"]


def execute(filters=None):
	filters = frappe._dict(filters or {})
	today = getdate(nowdate())
	cond, args = ["si.docstatus = 1", "si.outstanding_amount > 0.005"], {}
	if filters.company:
		cond.append("si.company = %(company)s")
		args["company"] = filters.company
	if filters.customer:
		cond.append("si.customer = %(customer)s")
		args["customer"] = filters.customer
	if filters.salesman:
		cond.append("COALESCE(NULLIF(si.salesman, ''), c.default_salesman) = %(salesman)s")
		args["salesman"] = filters.salesman
	else:
		cond.append("COALESCE(NULLIF(si.salesman, ''), c.default_salesman) IS NOT NULL")
	rows = frappe.db.sql(
		f"""SELECT COALESCE(NULLIF(si.salesman, ''), c.default_salesman) AS salesman, si.customer, si.customer_name,
			si.outstanding_amount, si.due_date FROM `tabSales Invoice` si JOIN `tabCustomer` c ON c.name = si.customer
			WHERE {' AND '.join(cond)}""", args, as_dict=True)
	grouped = {}
	for r in rows:
		g = grouped.setdefault((r.salesman, r.customer), {"salesman": r.salesman, "customer": r.customer, "customer_name": r.customer_name,
			"items": []})
		g["items"].append((r.outstanding_amount, getdate(r.due_date) if r.due_date else None))
	data = []
	for g in grouped.values():
		t = logic.aging_totals(g["items"], today)
		data.append({"salesman": g["salesman"], "customer": g["customer"], "customer_name": g["customer_name"],
			"outstanding": round(sum(t.values()), 2), "b0": t["current"], "b1": t["1-30"], "b2": t["31-60"], "b3": t["61-90"], "b4": t["90+"]})
	data.sort(key=lambda d: (d["salesman"] or "", -d["outstanding"]))
	cols = [
		{"fieldname": "salesman", "label": _("Salesman"), "fieldtype": "Link", "options": "Salesman", "width": 110},
		{"fieldname": "customer", "label": _("Customer"), "fieldtype": "Link", "options": "Customer", "width": 120},
		{"fieldname": "customer_name", "label": _("Customer Name"), "fieldtype": "Data", "width": 180},
		{"fieldname": "outstanding", "label": _("Outstanding"), "fieldtype": "Currency", "width": 120},
		{"fieldname": "b0", "label": _("Not Due"), "fieldtype": "Currency", "width": 100},
		{"fieldname": "b1", "label": _("1-30 Days"), "fieldtype": "Currency", "width": 100},
		{"fieldname": "b2", "label": _("31-60 Days"), "fieldtype": "Currency", "width": 100},
		{"fieldname": "b3", "label": _("61-90 Days"), "fieldtype": "Currency", "width": 100},
		{"fieldname": "b4", "label": _("Over 90 Days"), "fieldtype": "Currency", "width": 110},
	]
	return cols, data
