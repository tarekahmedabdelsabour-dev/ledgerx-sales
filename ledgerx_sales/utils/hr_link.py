"""Field sales <-> HR: attendance from the salesman screen and monthly commission in payroll.

Best effort and silent for attendance: a failure is logged but never blocks the salesman.
"""
import frappe
from frappe import _
from frappe.utils import add_months, get_datetime, get_first_day, get_last_day, getdate, nowdate, time_diff_in_hours

from ledgerx_sales.utils import logic, sales


def employee_of(sm):
	"""Employee on the salesman card, else the one behind his driver card, else the one with the same login user."""
	if sm.get("employee"):
		return sm.employee
	if sm.get("driver"):
		emp = frappe.db.get_value("Driver", sm.driver, "employee")
		if emp:
			return emp
	if sm.get("user"):
		return frappe.db.get_value("Employee", {"user_id": sm.user, "status": "Active"}, "name")
	return None


def mark_present(employee, date=None):
	"""Present attendance for the day. Does nothing when one already exists (e.g. made by the driver screen)."""
	if not employee or not frappe.db.exists("DocType", "Attendance"):
		return None
	date = getdate(date or nowdate())
	try:
		if frappe.db.exists("Attendance", {"employee": employee, "attendance_date": date, "docstatus": ["<", 2]}):
			return None
		company = frappe.db.get_value("Employee", employee, "company")
		doc = frappe.get_doc({"doctype": "Attendance", "employee": employee, "attendance_date": date,
			"status": "Present", "company": company}).insert(ignore_permissions=True)
		doc.submit()
		return doc.name
	except Exception:
		frappe.log_error(title="LedgerX: attendance from the screen failed")
		return None


def on_activity(sm):
	"""First check-in or sale of the day marks the salesman present."""
	emp = employee_of(sm)
	if emp:
		mark_present(emp)


def on_day_close(sm, date):
	"""Working hours = first check-in of the day until now, only when nothing set them already."""
	emp = employee_of(sm)
	if not emp:
		return
	try:
		name = frappe.db.get_value("Attendance", {"employee": emp, "attendance_date": getdate(date), "docstatus": 1},
			["name", "working_hours"], as_dict=True)
		first = frappe.db.sql("SELECT MIN(check_in) FROM `tabRoute Visit` WHERE salesman=%s AND visit_date=%s",
			(sm.name, date))[0][0]
		if name and first and not (name.working_hours or 0):
			hours = round(max(0, time_diff_in_hours(get_datetime(), get_datetime(first))), 2)
			frappe.db.set_value("Attendance", name.name, "working_hours", hours, update_modified=False)
	except Exception:
		frappe.log_error(title="LedgerX: working hours from the screen failed")


def make_commission(sm, from_date, to_date, settings=None):
	"""Draft Additional Salary for the commission of a period; returns its name, or None when not due / already made."""
	s = settings or sales.settings()
	employee = employee_of(sm)
	if not employee or not s.commission_component:
		return None
	amount = logic.commission(sales.period_base(sm, from_date, to_date), sm.commission_percent)
	if amount <= 0:
		return None
	if frappe.db.exists("Additional Salary", {"employee": employee, "salary_component": s.commission_component,
			"ref_doctype": "Salesman", "ref_docname": sm.name, "payroll_date": to_date, "docstatus": ["<", 2]}):
		return None
	doc = frappe.get_doc({"doctype": "Additional Salary", "employee": employee,
		"salary_component": s.commission_component, "amount": amount, "payroll_date": to_date,
		"company": sales.company_of(sm, s), "overwrite_salary_structure_amount": 1,
		"ref_doctype": "Salesman", "ref_docname": sm.name}).insert(ignore_permissions=True)
	return doc.name


def monthly_commissions():
	"""Scheduler: on the 1st, last month's commission for every active salesman as drafts for HR to review."""
	last = add_months(getdate(nowdate()), -1)
	s = sales.settings()
	if not s.commission_component:
		return
	for name in frappe.get_all("Salesman", filters={"status": "Active"}, pluck="name"):
		try:
			make_commission(frappe.get_doc("Salesman", name), get_first_day(last), get_last_day(last), s)
			frappe.db.commit()
		except Exception:
			frappe.db.rollback()
			frappe.log_error(title=f"LedgerX: monthly commission failed for {name}")
