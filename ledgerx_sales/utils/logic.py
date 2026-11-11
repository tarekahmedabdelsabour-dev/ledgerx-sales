"""Pure business rules of Field Sales (no Frappe imports, unit-tested)."""
from datetime import date
from math import asin, cos, radians, sin, sqrt

EPS = 0.005
WEEKDAYS = ["Monday", "Tuesday", "Wednesday", "Thursday", "Friday", "Saturday", "Sunday"]


def weekday_name(d):
	"""English weekday name of a date (Python: Monday = 0)."""
	return WEEKDAYS[d.weekday()]


def haversine_m(lat1, lon1, lat2, lon2):
	"""Distance in metres between two GPS points."""
	if None in (lat1, lon1, lat2, lon2):
		return None
	p1, p2 = radians(lat1), radians(lat2)
	dp, dl = p2 - p1, radians(lon2 - lon1)
	a = sin(dp / 2) ** 2 + cos(p1) * cos(p2) * sin(dl / 2) ** 2
	return int(round(2 * 6371000 * asin(sqrt(a))))


def allocate_payment(amount, invoices):
	"""Spread a payment over open invoices, oldest due date first.

	invoices: iterable of (name, outstanding, due_date). Returns (allocations, unallocated)
	where allocations is [(name, allocated)]. Nothing is allocated beyond an invoice's outstanding.
	"""
	left = round(float(amount or 0), 2)
	out = []
	for name, outstanding, due in sorted(invoices, key=lambda r: (r[2] or date.max, r[0])):
		if left <= EPS:
			break
		o = round(float(outstanding or 0), 2)
		if o <= EPS:
			continue
		take = round(min(left, o), 2)
		out.append((name, take))
		left = round(left - take, 2)
	return out, max(left, 0.0)


def aging_bucket(days_overdue):
	if days_overdue is None or days_overdue <= 0:
		return "current"
	if days_overdue <= 30:
		return "1-30"
	if days_overdue <= 60:
		return "31-60"
	if days_overdue <= 90:
		return "61-90"
	return "90+"


def aging_totals(rows, today):
	"""rows: (outstanding, due_date). Returns bucket -> total."""
	t = {"current": 0.0, "1-30": 0.0, "31-60": 0.0, "61-90": 0.0, "90+": 0.0}
	for outstanding, due in rows:
		days = (today - due).days if due else 0
		t[aging_bucket(days)] = round(t[aging_bucket(days)] + float(outstanding or 0), 2)
	return t


def credit_check(outstanding, new_credit, limit):
	"""(ok, available). limit 0/None means no limit is set."""
	if not limit:
		return True, None
	available = round(float(limit) - float(outstanding or 0), 2)
	return new_credit <= available + EPS, available


def discount_percent(rate, price_list_rate):
	if not price_list_rate:
		return 0.0
	return max(round((1 - float(rate) / float(price_list_rate)) * 100, 2), 0.0)


def cash_in_hand(cash_collected, handed_confirmed, handed_pending=0.0):
	"""Cash the salesman still carries. Pending handovers are shown separately, not yet removed."""
	return round(float(cash_collected or 0) - float(handed_confirmed or 0), 2)


def settlement_difference(cash_counted, cash_in_hand_system):
	return round(float(cash_counted or 0) - float(cash_in_hand_system or 0), 2)


def commission(base, percent):
	return round(float(base or 0) * float(percent or 0) / 100.0, 2)


def target_progress(achieved, target):
	if not target:
		return None
	return round(float(achieved or 0) / float(target) * 100, 1)


def sale_totals(lines):
	"""lines: [(qty, rate)] -> total."""
	return round(sum(float(q) * float(r) for q, r in lines), 2)


def split_payment(total, paid):
	"""(paid_now, credit). paid cannot exceed the total (extra is rejected by the caller)."""
	paid = round(float(paid or 0), 2)
	total = round(float(total or 0), 2)
	return paid, round(total - paid, 2)


def stock_shortfalls(lines, available):
	"""lines: [(item, qty)], available: {item: qty}. Returns [(item, wanted, have)] where short."""
	need = {}
	for item, qty in lines:
		need[item] = round(need.get(item, 0) + float(qty), 6)
	return [(i, q, available.get(i, 0.0)) for i, q in need.items() if q > available.get(i, 0.0) + 1e-9]


def visit_outcome(sale, collected):
	if sale and collected:
		return "Sale and Collection"
	if sale:
		return "Sale"
	if collected:
		return "Collection"
	return "No Order"
