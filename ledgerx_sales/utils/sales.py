"""Frappe-side helpers for Field Sales: settings, lookups, stock, cash, ERPNext document builders."""
import frappe
from frappe import _
from frappe.utils import add_days, flt, getdate, nowdate

from ledgerx_sales.utils import logic

SALESMAN_ROLE = "Field Salesman"


def settings():
	return frappe.get_cached_doc("Field Sales Settings")


def company_of(salesman=None, s=None):
	s = s or settings()
	return (salesman.company if salesman else None) or s.company or frappe.defaults.get_global_default("company")


# ------------------------------------------------------------------ stock
def van_stock(warehouse):
	"""{item_code: qty} currently in the van warehouse (only positive balances)."""
	if not warehouse:
		return {}
	rows = frappe.get_all("Bin", filters={"warehouse": warehouse, "actual_qty": ["!=", 0]},
		fields=["item_code", "actual_qty"])
	return {r.item_code: flt(r.actual_qty) for r in rows if flt(r.actual_qty) > 0}


def create_stock_transfer(doc):
	"""Material Transfer between the main warehouse and the van for a submitted Van Stock Transfer."""
	se = frappe.new_doc("Stock Entry")
	se.stock_entry_type = "Material Transfer"
	se.purpose = "Material Transfer"
	se.company = doc.company
	se.posting_date = doc.posting_date
	se.from_warehouse = doc.from_warehouse
	se.to_warehouse = doc.to_warehouse
	se.remarks = _("Van stock {0}: {1} - {2}").format(_(doc.transfer_type), doc.name, doc.salesman)
	for r in doc.items:
		se.append("items", {"item_code": r.item_code, "qty": r.qty, "uom": r.uom, "s_warehouse": doc.from_warehouse,
			"t_warehouse": doc.to_warehouse})
	se.insert(ignore_permissions=True)
	se.submit()
	return se.name


# ------------------------------------------------------------------ cash
def cash_in_hand(salesman, till=None):
	"""Balance of the salesman's own cash account (what he carries and has not handed over)."""
	acc = frappe.db.get_value("Salesman", salesman, "cash_account")
	if not acc:
		return 0.0
	cond = "account = %s AND is_cancelled = 0"
	args = [acc]
	if till:
		cond += " AND posting_date <= %s"
		args.append(getdate(till))
	r = frappe.db.sql(f"SELECT COALESCE(SUM(debit - credit), 0) FROM `tabGL Entry` WHERE {cond}", args)
	return flt(r[0][0]) if r else 0.0


def pending_handover(salesman):
	return flt(frappe.db.sql("SELECT COALESCE(SUM(amount),0) FROM `tabSalesman Cash Handover` "
		"WHERE salesman=%s AND status='Pending'", salesman)[0][0])


def make_account_name(base, company):
	abbr = frappe.get_cached_value("Company", company, "abbr")
	return f"{base} - {abbr}"


# ------------------------------------------------------------------ customers
def customer_outstanding(customer, company):
	from erpnext.selling.doctype.customer.customer import get_credit_limit, get_customer_outstanding

	limit = get_credit_limit(customer, company)
	out = get_customer_outstanding(customer, company, ignore_outstanding_sales_order=True)
	return flt(out), flt(limit)


def open_invoices(customer, company):
	return frappe.get_all("Sales Invoice", filters={"customer": customer, "company": company, "docstatus": 1,
		"outstanding_amount": [">", 0.005]},
		fields=["name", "posting_date", "due_date", "grand_total", "outstanding_amount", "salesman"],
		order_by="due_date asc, posting_date asc")


def customer_location(customer, route_row=None):
	lat = lng = None
	if route_row:
		lat, lng = route_row.get("latitude"), route_row.get("longitude")
	if not lat or not lng:
		lat, lng = frappe.db.get_value("Customer", customer, ["fs_latitude", "fs_longitude"]) or (None, None)
	return (flt(lat) or None, flt(lng) or None)


# ------------------------------------------------------------------ documents
def price_list_rate(item, price_list, uom=None):
	if price_list:
		r = frappe.db.get_value("Item Price", {"item_code": item, "price_list": price_list, "selling": 1},
			"price_list_rate", order_by="valid_from desc")
		if r:
			return flt(r)
	return flt(frappe.db.get_value("Item", item, "standard_rate"))


def default_taxes(si):
	try:
		from erpnext.accounts.services.taxes import _get_default_taxes_and_charges

		d = _get_default_taxes_and_charges("Sales Taxes and Charges Template", company=si.company)
		if d and d.get("taxes_and_charges") and not si.get("taxes"):
			si.taxes_and_charges = d["taxes_and_charges"]
			for t in d.get("taxes") or []:
				si.append("taxes", t)
	except Exception:
		frappe.log_error(title="Field Sales: default taxes")


def make_payment_entry(salesman, customer, amount, mode, allocations, posting_date=None, reference_no=None,
		reference_date=None, route_visit=None, request_id=None, remarks=None, bank_account=None):
	"""Receive money from a customer. mode: 'Cash' (into the salesman's cash account) or 'Bank'."""
	s = settings()
	sm = frappe.get_doc("Salesman", salesman)
	company = company_of(sm, s)
	if mode == "Cash":
		to_account = sm.cash_account
		if not to_account:
			frappe.throw(_("Salesman {0} has no cash account. Open the salesman and press Create Accounts.").format(sm.name))
	else:
		to_account = bank_account or s.default_bank_account
		if not to_account:
			frappe.throw(_("Set the default bank account in Field Sales Settings"))
		if not reference_no:
			frappe.throw(_("Enter the transfer or cheque reference"))
	from erpnext.accounts.party import get_party_account

	paid_from = get_party_account("Customer", customer, company)
	ccy = frappe.get_cached_value("Account", to_account, "account_currency")
	pe = frappe.new_doc("Payment Entry")
	pe.payment_type = "Receive"
	pe.company = company
	pe.posting_date = posting_date or nowdate()
	pe.party_type = "Customer"
	pe.party = customer
	pe.paid_from = paid_from
	pe.paid_to = to_account
	pe.paid_from_account_currency = frappe.get_cached_value("Account", paid_from, "account_currency")
	pe.paid_to_account_currency = ccy
	pe.paid_amount = pe.received_amount = flt(amount)
	pe.source_exchange_rate = pe.target_exchange_rate = 1
	pe.cost_center = sm.cost_center or s.cost_center
	pe.mode_of_payment = "Cash" if mode == "Cash" and frappe.db.exists("Mode of Payment", "Cash") else None
	if reference_no:
		pe.reference_no = reference_no
		pe.reference_date = reference_date or pe.posting_date
	for inv, amt in allocations:
		pe.append("references", {"reference_doctype": "Sales Invoice", "reference_name": inv, "allocated_amount": flt(amt)})
	pe.remarks = remarks or _("Collected by {0}").format(sm.salesman_name)
	pe.salesman = salesman
	pe.route_visit = route_visit
	pe.fs_request_id = request_id
	pe.insert(ignore_permissions=True)
	pe.submit()
	return pe


def make_handover_journal(doc):
	"""Dr cashier / bank  Cr salesman cash account."""
	s = settings()
	sm = frappe.get_doc("Salesman", doc.salesman)
	company = company_of(sm, s)
	debit = s.cashier_account if doc.method == "Cash to Cashier" else (doc.bank_account or s.default_bank_account)
	if not debit or not sm.cash_account:
		frappe.throw(_("Set the cashier account in Field Sales Settings and create the salesman's cash account."),
			title=_("Accounting Not Configured"))
	cc = sm.cost_center or s.cost_center
	je = frappe.new_doc("Journal Entry")
	je.voucher_type = "Journal Entry"
	je.company = company
	je.posting_date = doc.posting_date
	je.cheque_no = doc.deposit_reference or None
	je.cheque_date = doc.posting_date if doc.deposit_reference else None
	je.user_remark = _("Cash handover {0} - {1}").format(doc.name, sm.salesman_name)
	je.append("accounts", {"account": debit, "debit_in_account_currency": flt(doc.amount), "cost_center": cc})
	je.append("accounts", {"account": sm.cash_account, "credit_in_account_currency": flt(doc.amount), "cost_center": cc})
	je.insert(ignore_permissions=True)
	je.submit()
	return je.name


def cancel_linked(doctype, name):
	if name and frappe.db.exists(doctype, name) and frappe.db.get_value(doctype, name, "docstatus") == 1:
		frappe.get_doc(doctype, name).cancel()


def period_base(sm, from_date, to_date):
	"""Amount the commission is calculated on: collected money or invoiced sales in the period."""
	if sm.commission_basis == "Invoiced":
		r = frappe.db.sql("SELECT COALESCE(SUM(grand_total),0) FROM `tabSales Invoice` WHERE salesman=%s AND docstatus=1 "
			"AND posting_date BETWEEN %s AND %s", (sm.name, from_date, to_date))
	else:
		r = frappe.db.sql("SELECT COALESCE(SUM(paid_amount),0) FROM `tabPayment Entry` WHERE salesman=%s AND docstatus=1 "
			"AND payment_type='Receive' AND posting_date BETWEEN %s AND %s", (sm.name, from_date, to_date))
	return flt(r[0][0])
