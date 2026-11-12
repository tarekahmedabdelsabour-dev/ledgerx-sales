"""Backend of the salesman's mobile page (/salesman).

Every method works for the logged-in user's own Salesman record only; the salesman is never taken
from the request. Every write carries a request_id so a retry from a flaky connection (or the
offline queue) can never create the same invoice / collection twice.
"""
import base64
import json
import re

import frappe
from frappe import _
from frappe.utils import add_days, cint, flt, get_datetime, getdate, now_datetime, nowdate

from ledgerx_sales.utils import logic, sales

MAX_PHOTO_BYTES = 3 * 1024 * 1024
DATA_URL = re.compile(r"^data:image/(jpeg|jpg|png|webp);base64,(.+)$", re.S)


# ------------------------------------------------------------------ plumbing
def _salesman():
	if frappe.session.user == "Guest":
		frappe.throw(_("Please log in"), frappe.AuthenticationError)
	name = frappe.db.get_value("Salesman", {"user": frappe.session.user, "status": "Active"}, "name")
	if not name:
		frappe.throw(_("Your user ({0}) is not linked to an active salesman. Ask the sales manager.").format(frappe.session.user), frappe.PermissionError)
	return frappe.get_doc("Salesman", name)


def _json(v, default):
	if v in (None, ""):
		return default
	if isinstance(v, (list, dict)):
		return v
	try:
		return json.loads(v)
	except Exception:
		frappe.throw(_("Invalid data"))


def _save_photo(doc, fieldname, data_url, required=False):
	if not data_url:
		if required:
			frappe.throw(_("A photo is required"))
		return
	m = DATA_URL.match(data_url.strip())
	if not m:
		frappe.throw(_("Invalid photo"))
	try:
		content = base64.b64decode(m.group(2), validate=False)
	except Exception:
		frappe.throw(_("Invalid photo"))
	if len(content) > MAX_PHOTO_BYTES:
		frappe.throw(_("Photo is too large"))
	ext = "png" if m.group(1) == "png" else ("webp" if m.group(1) == "webp" else "jpg")
	f = frappe.get_doc({"doctype": "File", "file_name": f"{doc.name}-{fieldname}.{ext}", "attached_to_doctype": doc.doctype,
		"attached_to_name": doc.name, "attached_to_field": fieldname, "content": content, "is_private": 1}).insert(ignore_permissions=True)
	doc.db_set(fieldname, f.file_url, update_modified=False)


def _existing(doctype, request_id, field="request_id"):
	if request_id:
		return frappe.db.get_value(doctype, {field: request_id}, "name")


def _allowed_customers(sm):
	"""Customers on his routes + customers whose default salesman he is."""
	names = set(frappe.get_all("Route Customer", filters={"parenttype": "Sales Route", "parent": ["in",
		frappe.get_all("Sales Route", filters={"salesman": sm.name, "is_active": 1}, pluck="name") or [""]]}, pluck="customer"))
	names |= set(frappe.get_all("Customer", filters={"default_salesman": sm.name, "disabled": 0}, pluck="name"))
	return names


def _check_customer(sm, customer):
	if not customer or customer not in _allowed_customers(sm):
		frappe.throw(_("Customer {0} is not on your routes").format(customer or ""), frappe.PermissionError)


def _bump_visit(visit, sales_amt=0.0, collected=0.0):
	if not visit or not frappe.db.exists("Route Visit", visit):
		return
	st, col = frappe.db.get_value("Route Visit", visit, ["sales_total", "collected_total"])
	frappe.db.set_value("Route Visit", visit, {"sales_total": flt(st) + flt(sales_amt), "collected_total": flt(col) + flt(collected)},
		update_modified=False)


def _visit_of(sm, visit, customer):
	if not visit:
		return None
	row = frappe.db.get_value("Route Visit", visit, ["salesman", "customer"], as_dict=True)
	if not row or row.salesman != sm.name or row.customer != customer:
		frappe.throw(_("Invalid visit"))
	return visit


# ------------------------------------------------------------------ home
@frappe.whitelist()
def me():
	sm = _salesman()
	s = sales.settings()
	company = sales.company_of(sm, s)
	today = getdate(nowdate())
	month_start = today.replace(day=1)
	inv_day = frappe.db.sql("SELECT COALESCE(SUM(grand_total),0), COUNT(*) FROM `tabSales Invoice` WHERE salesman=%s AND posting_date=%s AND docstatus=1", (sm.name, today))[0]
	pay_day = frappe.db.sql("SELECT COALESCE(SUM(paid_amount),0) FROM `tabPayment Entry` WHERE salesman=%s AND posting_date=%s AND docstatus=1 AND payment_type='Receive'", (sm.name, today))[0][0]
	inv_month = frappe.db.sql("SELECT COALESCE(SUM(grand_total),0) FROM `tabSales Invoice` WHERE salesman=%s AND posting_date>=%s AND docstatus=1", (sm.name, month_start))[0][0]
	col_month = sales.period_base(frappe._dict(name=sm.name, commission_basis="Collected"), month_start, today)
	achieved = inv_month
	vis = frappe.db.sql("SELECT COUNT(*), SUM(status='Completed') FROM `tabRoute Visit` WHERE salesman=%s AND visit_date=%s", (sm.name, today))[0]
	stops = _route_rows(sm, today)
	closed = frappe.db.get_value("Salesman Settlement", {"salesman": sm.name, "settlement_date": today, "docstatus": 1}, "name")
	stock = sales.van_stock(sm.warehouse)
	base = col_month if sm.commission_basis == "Collected" else inv_month
	return {
		"salesman": sm.name, "name": sm.salesman_name, "vehicle": sm.vehicle, "warehouse": sm.warehouse,
		"currency": frappe.get_cached_value("Company", company, "default_currency"),
		"can_credit": cint(sm.can_sell_on_credit), "max_discount": flt(sm.max_discount_percent),
		"require_gps": cint(s.require_gps), "has_cash_account": bool(sm.cash_account),
		"today": {"sales": flt(inv_day[0]), "invoices": cint(inv_day[1]), "collected": flt(pay_day),
			"visits_total": cint(vis[0]), "visits_done": cint(vis[1] or 0), "stops": len(stops),
			"stops_done": len([x for x in stops if x["visit_status"] == "Completed"])},
		"cash": {"in_hand": sales.cash_in_hand(sm.name), "pending": sales.pending_handover(sm.name)},
		"month": {"sales": flt(inv_month), "collected": flt(col_month), "target": flt(sm.monthly_target),
			"progress": logic.target_progress(achieved, sm.monthly_target), "commission": logic.commission(base, sm.commission_percent),
			"commission_percent": flt(sm.commission_percent)},
		"stock": {"items": len(stock), "qty": sum(stock.values())},
		"day_closed": closed, "recent_handovers": frappe.get_all("Salesman Cash Handover", filters={"salesman": sm.name}, limit=8,
			order_by="creation desc", fields=["name", "posting_date", "method", "amount", "status", "rejection_reason"]),
	}


def _route_rows(sm, day):
	wd = logic.weekday_name(day)
	routes = frappe.get_all("Sales Route", filters={"salesman": sm.name, "is_active": 1, "weekday": ["in", [wd, "Every Day"]]},
		pluck="name")
	rows, seen = [], set()
	for rn in routes:
		for r in frappe.get_all("Route Customer", filters={"parent": rn, "parenttype": "Sales Route"},
				fields=["customer", "customer_name", "sequence", "area", "latitude", "longitude", "notes"], order_by="sequence asc, idx asc"):
			if r.customer in seen:
				continue
			seen.add(r.customer)
			visit = frappe.db.get_value("Route Visit", {"salesman": sm.name, "customer": r.customer, "visit_date": day},
				["name", "status", "outcome", "sales_total", "collected_total", "out_of_range"], as_dict=True) or {}
			lat, lng = sales.customer_location(r.customer, r)
			rows.append({"route": rn, "customer": r.customer, "customer_name": r.customer_name, "sequence": r.sequence,
				"area": r.area, "notes": r.notes, "lat": lat, "lng": lng, "visit": visit.get("name"),
				"visit_status": visit.get("status") or "Planned", "outcome": visit.get("outcome"),
				"visit_sales": flt(visit.get("sales_total")), "visit_collected": flt(visit.get("collected_total"))})
	return rows


@frappe.whitelist()
def route_today():
	sm = _salesman()
	return _route_rows(sm, getdate(nowdate()))


@frappe.whitelist()
def customers(search=None, limit=40):
	sm = _salesman()
	allowed = list(_allowed_customers(sm))
	if not allowed:
		return []
	flt_ = {"name": ["in", allowed], "disabled": 0}
	rows = frappe.get_all("Customer", filters=flt_, or_filters=(
		[["customer_name", "like", f"%{search}%"], ["name", "like", f"%{search}%"], ["mobile_no", "like", f"%{search}%"]] if search else None),
		fields=["name", "customer_name", "mobile_no", "territory"], limit=cint(limit), order_by="customer_name asc")
	company = sales.company_of(sm)
	for r in rows:
		r["outstanding"], r["limit"] = sales.customer_outstanding(r.name, company)
	return rows


@frappe.whitelist()
def customer_detail(customer):
	sm = _salesman()
	_check_customer(sm, customer)
	company = sales.company_of(sm)
	today = getdate(nowdate())
	out, limit = sales.customer_outstanding(customer, company)
	inv = sales.open_invoices(customer, company)
	aging = logic.aging_totals([(i.outstanding_amount, getdate(i.due_date) if i.due_date else None) for i in inv], today)
	for i in inv:
		i["days_overdue"] = (today - getdate(i.due_date)).days if i.due_date else 0
	c = frappe.db.get_value("Customer", customer, ["customer_name", "mobile_no", "primary_address", "fs_latitude", "fs_longitude"], as_dict=True)
	last_sales = frappe.get_all("Sales Invoice", filters={"customer": customer, "docstatus": 1}, limit=5, order_by="posting_date desc, creation desc",
		fields=["name", "posting_date", "grand_total", "outstanding_amount"])
	last_pay = frappe.get_all("Payment Entry", filters={"party": customer, "party_type": "Customer", "docstatus": 1, "payment_type": "Receive"},
		limit=5, order_by="posting_date desc, creation desc", fields=["name", "posting_date", "paid_amount", "mode_of_payment"])
	return {"customer": customer, "customer_name": c.customer_name, "mobile": c.mobile_no, "address": c.primary_address,
		"lat": flt(c.fs_latitude) or None, "lng": flt(c.fs_longitude) or None, "outstanding": out, "limit": limit,
		"available": None if not limit else round(limit - out, 2), "aging": aging, "open_invoices": inv,
		"last_sales": last_sales, "last_payments": last_pay}


@frappe.whitelist()
def items(search=None, limit=60):
	"""Items available in the van, with the selling price from the salesman's price list."""
	sm = _salesman()
	stock = sales.van_stock(sm.warehouse)
	if not stock:
		return []
	filters = {"name": ["in", list(stock)], "disabled": 0, "is_sales_item": 1}
	rows = frappe.get_all("Item", filters=filters, or_filters=(
		[["item_name", "like", f"%{search}%"], ["name", "like", f"%{search}%"], ["barcodes.barcode", "like", f"%{search}%"]] if search else None),
		fields=["name", "item_name", "stock_uom", "image"], limit=cint(limit), order_by="item_name asc")
	for r in rows:
		r["qty"] = stock.get(r.name, 0)
		r["rate"] = sales.price_list_rate(r.name, sm.price_list)
	return rows


@frappe.whitelist()
def all_items(search=None, limit=40):
	"""Items that can be requested from the main warehouse (any sales stock item)."""
	_salesman()
	filters = {"disabled": 0, "is_sales_item": 1, "is_stock_item": 1}
	return frappe.get_all("Item", filters=filters, or_filters=(
		[["item_name", "like", f"%{search}%"], ["name", "like", f"%{search}%"]] if search else None),
		fields=["name", "item_name", "stock_uom"], limit=cint(limit), order_by="item_name asc")


@frappe.whitelist()
def save_location(customer, lat, lng):
	"""Pin the customer's shop on the map from the field (used later to verify visits)."""
	sm = _salesman()
	_check_customer(sm, customer)
	lat, lng = flt(lat), flt(lng)
	if not (-90 <= lat <= 90 and -180 <= lng <= 180) or (not lat and not lng):
		frappe.throw(_("Invalid location"))
	frappe.db.set_value("Customer", customer, {"fs_latitude": lat, "fs_longitude": lng})
	return True


# ------------------------------------------------------------------ visits
@frappe.whitelist()
def check_in(customer, lat=None, lng=None, photo=None, request_id=None):
	sm = _salesman()
	_check_customer(sm, customer)
	s = sales.settings()
	if cint(s.require_gps) and (lat in (None, "") or lng in (None, "")):
		frappe.throw(_("Turn on the location to check in"))
	today = getdate(nowdate())
	name = frappe.db.get_value("Route Visit", {"salesman": sm.name, "customer": customer, "visit_date": today}, "name")
	visit = frappe.get_doc("Route Visit", name) if name else frappe.new_doc("Route Visit")
	if visit.status == "Checked In":
		return {"visit": visit.name, "warning": None}
	if not name:
		route = frappe.db.get_value("Route Customer", {"customer": customer, "parent": ["in",
			frappe.get_all("Sales Route", filters={"salesman": sm.name, "is_active": 1}, pluck="name") or [""]]}, "parent")
		visit.update({"salesman": sm.name, "customer": customer, "visit_date": today, "route": route, "company": sales.company_of(sm, s)})
	visit.status = "Checked In"
	visit.check_in = now_datetime()
	row = None
	if visit.route:
		row = frappe.db.get_value("Route Customer", {"parent": visit.route, "customer": customer}, ["latitude", "longitude"], as_dict=True)
	clat, clng = sales.customer_location(customer, row)
	warning = None
	if lat not in (None, "") and lng not in (None, ""):
		visit.in_latitude, visit.in_longitude = flt(lat), flt(lng)
		dist = logic.haversine_m(flt(lat), flt(lng), clat, clng) if clat and clng else None
		visit.distance_m = dist
		limit = cint(s.max_visit_distance)
		if dist is not None and limit and dist > limit:
			visit.out_of_range = 1
			warning = _("You are {0} m away from the customer's location").format(dist)
		elif dist is None:
			warning = _("The customer has no saved location yet. Save it from the customer screen.")
	visit.save(ignore_permissions=True)
	if photo:
		_save_photo(visit, "photo", photo)
	return {"visit": visit.name, "warning": warning, "distance": visit.distance_m}


@frappe.whitelist()
def check_out(visit, outcome=None, notes=None):
	sm = _salesman()
	doc = frappe.get_doc("Route Visit", visit)
	if doc.salesman != sm.name:
		frappe.throw(_("Invalid visit"), frappe.PermissionError)
	if not outcome:
		outcome = logic.visit_outcome(flt(doc.sales_total) > 0, flt(doc.collected_total) > 0)
	if outcome not in ("Sale", "Collection", "Sale and Collection", "No Order", "Shop Closed", "Postponed"):
		frappe.throw(_("Invalid outcome"))
	doc.outcome = outcome
	doc.status = "Skipped" if outcome in ("Shop Closed", "Postponed") else "Completed"
	doc.check_out = now_datetime()
	if notes:
		doc.notes = notes
	doc.save(ignore_permissions=True)
	return {"visit": doc.name, "status": doc.status}


# ------------------------------------------------------------------ sale
@frappe.whitelist()
def create_sale(customer, lines, paid_amount=0, payment_mode="Cash", reference_no=None, visit=None, request_id=None):
	"""Invoice from the van warehouse; an optional payment received at the same time."""
	sm = _salesman()
	_check_customer(sm, customer)
	if old := _existing("Sales Invoice", request_id, "fs_request_id"):
		return _sale_result(old)
	s = sales.settings()
	company = sales.company_of(sm, s)
	lines = _json(lines, [])
	paid = round(flt(paid_amount), 2)
	if not lines:
		frappe.throw(_("Add at least one item"))
	if not sm.warehouse:
		frappe.throw(_("No van warehouse is set for you"))
	visit = _visit_of(sm, visit, customer)
	merged = {}
	for ln in lines:
		code, qty, rate = ln.get("item_code"), flt(ln.get("qty")), flt(ln.get("rate"))
		if not code or qty <= 0 or rate < 0:
			frappe.throw(_("Invalid item line"))
		merged.setdefault(code, []).append((qty, rate))
	# stock
	if not cint(s.allow_negative_van_stock):
		short = logic.stock_shortfalls([(c, q) for c, v in merged.items() for q, _r in v], sales.van_stock(sm.warehouse))
		if short:
			frappe.throw(_("Not enough stock in the van: {0}").format(", ".join(f"{i} ({w:g} > {h:g})" for i, w, h in short)))
	# discount
	for code, v in merged.items():
		base = sales.price_list_rate(code, sm.price_list)
		for _q, rate in v:
			d = logic.discount_percent(rate, base)
			if d > flt(sm.max_discount_percent) + 0.005:
				frappe.throw(_("Discount on {0} is {1}%, more than your limit of {2}%").format(code, d, sm.max_discount_percent))
	si = frappe.new_doc("Sales Invoice")
	si.customer = customer
	si.company = company
	si.posting_date = nowdate()
	si.update_stock = 1
	si.set_warehouse = sm.warehouse
	si.cost_center = sm.cost_center or s.cost_center
	si.selling_price_list = sm.price_list or s.default_price_list
	si.ignore_pricing_rule = 1
	si.salesman = sm.name
	si.route_visit = visit
	si.fs_request_id = request_id
	si.remarks = _("Field sale by {0}").format(sm.salesman_name)
	for ln in lines:
		si.append("items", {"item_code": ln["item_code"], "qty": flt(ln["qty"]), "rate": flt(ln["rate"]),
			"warehouse": sm.warehouse, "cost_center": si.cost_center})
	si.run_method("set_missing_values")
	sales.default_taxes(si)
	si.insert(ignore_permissions=True)
	total = flt(si.grand_total)
	if paid < 0 or paid > total + 0.005:
		frappe.throw(_("The paid amount cannot exceed the invoice total ({0})").format(total))
	credit = round(total - paid, 2)
	if credit > 0.005:
		if not cint(sm.can_sell_on_credit):
			frappe.throw(_("You cannot sell on credit. Collect the full amount."))
		if cint(s.block_credit_over_limit):
			out, limit = sales.customer_outstanding(customer, company)
			ok, avail = logic.credit_check(out, credit, limit)
			if not ok:
				frappe.throw(_("Credit limit exceeded. Available credit: {0}").format(avail))
	si.submit()
	pe = None
	if paid > 0.005:
		pe = sales.make_payment_entry(sm.name, customer, paid, "Cash" if payment_mode == "Cash" else "Bank",
			[(si.name, paid)], reference_no=reference_no, route_visit=visit, request_id=f"{request_id}-pay" if request_id else None)
	_bump_visit(visit, total, paid)
	return _sale_result(si.name, pe.name if pe else None)


def _sale_result(name, payment=None):
	si = frappe.db.get_value("Sales Invoice", name, ["name", "grand_total", "outstanding_amount", "customer"], as_dict=True)
	return {"invoice": si.name, "total": flt(si.grand_total), "outstanding": flt(si.outstanding_amount), "payment": payment,
		"print_url": f"/printview?doctype=Sales%20Invoice&name={si.name}&trigger_print=0&format=Standard&no_letterhead=0"}


# ------------------------------------------------------------------ collection
@frappe.whitelist()
def collect(customer, amount, mode="Cash", reference_no=None, invoices=None, visit=None, request_id=None):
	"""Receive money: allocated to the customer's oldest open invoices (or the chosen ones); any rest stays as advance."""
	sm = _salesman()
	_check_customer(sm, customer)
	if old := _existing("Payment Entry", request_id, "fs_request_id"):
		return {"payment": old, "amount": flt(frappe.db.get_value("Payment Entry", old, "paid_amount"))}
	amount = round(flt(amount), 2)
	if amount <= 0:
		frappe.throw(_("Amount must be greater than zero"))
	company = sales.company_of(sm)
	visit = _visit_of(sm, visit, customer)
	chosen = _json(invoices, [])
	openi = sales.open_invoices(customer, company)
	if chosen:
		names = set(chosen)
		openi = [i for i in openi if i.name in names]
	alloc, rest = logic.allocate_payment(amount, [(i.name, i.outstanding_amount, i.due_date) for i in openi])
	pe = sales.make_payment_entry(sm.name, customer, amount, "Cash" if mode == "Cash" else "Bank", alloc, reference_no=reference_no,
		route_visit=visit, request_id=request_id)
	_bump_visit(visit, 0, amount)
	return {"payment": pe.name, "amount": amount, "allocated": [{"invoice": n, "amount": a} for n, a in alloc], "advance": rest}


# ------------------------------------------------------------------ cash handover
@frappe.whitelist()
def handover(amount, method="Cash to Cashier", deposit_reference=None, slip=None, bank_account=None, request_id=None):
	sm = _salesman()
	if old := _existing("Salesman Cash Handover", request_id):
		return {"handover": old}
	if method not in ("Cash to Cashier", "Bank Deposit"):
		frappe.throw(_("Invalid method"))
	if method == "Bank Deposit" and not (deposit_reference or slip):
		frappe.throw(_("Enter the deposit reference or attach the deposit slip photo"))
	doc = frappe.get_doc({"doctype": "Salesman Cash Handover", "salesman": sm.name, "posting_date": nowdate(), "method": method,
		"amount": flt(amount), "deposit_reference": deposit_reference, "request_id": request_id,
		"bank_account": bank_account or None}).insert(ignore_permissions=True)
	_save_photo(doc, "deposit_slip", slip)
	return {"handover": doc.name}


# ------------------------------------------------------------------ stock request
@frappe.whitelist()
def request_transfer(lines, transfer_type="Load", remarks=None, request_id=None):
	"""A request to load or return stock: saved as a draft for the manager to submit."""
	sm = _salesman()
	if old := _existing("Van Stock Transfer", request_id):
		return {"transfer": old}
	if transfer_type not in ("Load", "Return"):
		frappe.throw(_("Invalid transfer type"))
	lines = _json(lines, [])
	if not lines:
		frappe.throw(_("Add at least one item"))
	doc = frappe.get_doc({"doctype": "Van Stock Transfer", "transfer_type": transfer_type, "salesman": sm.name,
		"posting_date": nowdate(), "remarks": remarks, "requested_from_app": 1, "request_id": request_id,
		"items": [{"item_code": l["item_code"], "qty": flt(l["qty"])} for l in lines]})
	doc.insert(ignore_permissions=True)
	return {"transfer": doc.name}


@frappe.whitelist()
def stock():
	sm = _salesman()
	st = sales.van_stock(sm.warehouse)
	rows = frappe.get_all("Item", filters={"name": ["in", list(st) or [""]]}, fields=["name", "item_name", "stock_uom"], order_by="item_name asc")
	for r in rows:
		r["qty"] = st.get(r.name, 0)
		r["rate"] = sales.price_list_rate(r.name, sm.price_list)
	pending = frappe.get_all("Van Stock Transfer", filters={"salesman": sm.name, "docstatus": 0}, fields=["name", "transfer_type", "posting_date"],
		order_by="creation desc", limit=10)
	value = round(sum(r["qty"] * r["rate"] for r in rows), 2)
	return {"items": rows, "pending_requests": pending, "value": value}


# ------------------------------------------------------------------ day
@frappe.whitelist()
def day_summary():
	"""Everything of today in one list (sales, collections, handovers) for the "my day" tab."""
	sm = _salesman()
	today = getdate(nowdate())
	inv = frappe.get_all("Sales Invoice", filters={"salesman": sm.name, "posting_date": today, "docstatus": 1},
		fields=["name", "customer_name", "grand_total", "outstanding_amount", "creation"], order_by="creation desc")
	pay = frappe.get_all("Payment Entry", filters={"salesman": sm.name, "posting_date": today, "docstatus": 1, "payment_type": "Receive"},
		fields=["name", "party_name", "paid_amount", "paid_to", "creation"], order_by="creation desc")
	for p in pay:
		p["cash"] = p.paid_to == sm.cash_account
	return {"invoices": inv, "payments": pay, "cash_in_hand": sales.cash_in_hand(sm.name),
		"closed": frappe.db.get_value("Salesman Settlement", {"salesman": sm.name, "settlement_date": today, "docstatus": 1}, "name")}


@frappe.whitelist()
def close_day(cash_counted, stock_counts=None, remarks=None, request_id=None):
	sm = _salesman()
	today = getdate(nowdate())
	if closed := frappe.db.get_value("Salesman Settlement", {"salesman": sm.name, "settlement_date": today, "docstatus": 1}, "name"):
		return {"settlement": closed, "difference": 0}
	counts = _json(stock_counts, {})
	st = sales.van_stock(sm.warehouse)
	lines = [{"item_code": i, "counted_qty": flt(counts.get(i, q))} for i, q in st.items()]
	doc = frappe.get_doc({"doctype": "Salesman Settlement", "salesman": sm.name, "settlement_date": today,
		"cash_counted": flt(cash_counted), "remarks": remarks, "stock_lines": lines})
	doc.insert(ignore_permissions=True)
	doc.submit()
	return {"settlement": doc.name, "difference": flt(doc.difference), "cash_in_hand": flt(doc.cash_in_hand),
		"invoiced": flt(doc.invoiced_total), "collected": flt(doc.collections_cash) + flt(doc.collections_other)}
