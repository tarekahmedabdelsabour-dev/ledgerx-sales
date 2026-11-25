"""Row-level scope for the salesman reports: a plain salesman sees only himself; managers and accountants see everyone."""
import frappe
from frappe import _

SEE_ALL = {"System Manager", "Sales Manager", "Accounts User", "Accounts Manager"}


def own_salesmen():
	"""None = no restriction. Otherwise the list of Salesman records linked to the current user (possibly empty)."""
	if frappe.session.user == "Administrator" or SEE_ALL & set(frappe.get_roles()):
		return None
	return frappe.get_all("Salesman", filters={"user": frappe.session.user}, pluck="name")


def check_filter(filters):
	"""Reject a salesman filter that is not the user's own; return the user's own names (or None)."""
	own = own_salesmen()
	if own is not None and filters.get("salesman") and filters.salesman not in own:
		frappe.throw(_("You can only see your own figures"), frappe.PermissionError)
	return own
