"""Generate the desk files exactly like HRMS ships them: app tile (Desktop Icon), module rail (Dock),
one Workspace + Workspace Sidebar per module, and the icon sprite.   python3 tools/gen_desk.py"""
import json
import os
import uuid

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
APP = os.path.join(ROOT, "ledgerx_sales")
MODULE = "Field Sales"
APP_LABEL = "Field Sales"
APP_ROUTE = "/desk/field-sales"
STAMP = __import__("datetime").datetime.now().strftime("%Y-%m-%d %H:%M:%S.%f")  # newer than the DB copy, or migrate skips the file

# (title, lucide icon, dock icon, [(label, link_to, kind, icon)], [related (label, doctype, icon)])
MODULES = [
	("Field Sales", "truck", "field-sales-soft", [
		("Salesman Screen", "/salesman", "URL", "smartphone"),
		("Salesman", "Salesman", "DocType", "user-round"),
		("Sales Route", "Sales Route", "DocType", "route"),
		("Route Visit", "Route Visit", "DocType", "map-pin"),
		("Van Stock Transfer", "Van Stock Transfer", "DocType", "truck"),
		("Salesman Cash Handover", "Salesman Cash Handover", "DocType", "banknote"),
		("Salesman Settlement", "Salesman Settlement", "DocType", "calendar-check"),
		("Salesman Receivables", "Salesman Receivables", "Report", "hand-coins"),
		("Salesman Cash Position", "Salesman Cash Position", "Report", "wallet"),
		("Salesman Performance", "Salesman Performance", "Report", "trending-up"),
		("Field Sales Settings", "Field Sales Settings", "DocType", "settings"),
	], [("Customer", "Customer", "users"), ("Sales Invoice", "Sales Invoice", "receipt"),
		("Payment Entry", "Payment Entry", "wallet"), ("Stock Entry", "Stock Entry", "arrow-right-left"),
		("Warehouse", "Warehouse", "warehouse"), ("Vehicle", "Vehicle", "car"), ("Employee", "Employee", "square-user-round")]),
]

REPORT_DT = {"Salesman Receivables": "Sales Invoice", "Salesman Cash Position": "Salesman",
	"Salesman Performance": "Salesman"}


def dump(path, data):
	os.makedirs(os.path.dirname(path), exist_ok=True)
	with open(path, "w", encoding="utf-8") as fh:
		json.dump(data, fh, indent=1, ensure_ascii=False, sort_keys=True)
		fh.write("\n")


def scrub(n):
	return n.lower().replace(" ", "_")


def item(label, link_to, link_type, icon="", child=0):
	if link_type == "URL":
		return {"child": child, "collapsible": 1, "icon": icon, "indent": 0, "keep_closed": 0, "label": label,
			"url": link_to, "link_type": "URL", "show_arrow": 0, "type": "Link"}
	return {"child": child, "collapsible": 1, "icon": icon, "indent": 0, "keep_closed": 0, "label": label,
		"link_to": link_to, "link_type": link_type, "show_arrow": 0, "type": "Link"}


def section(label, icon, closed=1):
	return {"child": 0, "collapsible": 1, "icon": icon, "indent": 1, "keep_closed": closed, "label": label,
		"link_type": "DocType", "show_arrow": 0, "type": "Section Break"}


# ---------------------------------------------------------------- dashboards
def _f(*rows):
	return json.dumps([list(r) for r in rows])


# name: (doctype, filters, function, sum_field)
CARDS = {
	"Active Salesmen": ("Salesman", _f(("Salesman", "status", "=", "Active")), "Count", None),
	"Sales Today": ("Sales Invoice", _f(("Sales Invoice", "docstatus", "=", 1), ("Sales Invoice", "salesman", "is", "set"), ("Sales Invoice", "posting_date", "Timespan", "today")), "Sum", "grand_total"),
	"Field Sales This Month": ("Sales Invoice", _f(("Sales Invoice", "docstatus", "=", 1), ("Sales Invoice", "salesman", "is", "set"), ("Sales Invoice", "posting_date", "Timespan", "this month")), "Sum", "grand_total"),
	"Pending Cash Handovers": ("Salesman Cash Handover", _f(("Salesman Cash Handover", "status", "=", "Pending")), "Count", None),
	"Visits Today": ("Route Visit", _f(("Route Visit", "visit_date", "Timespan", "today")), "Count", None),
	"Out of Range Visits": ("Route Visit", _f(("Route Visit", "out_of_range", "=", 1), ("Route Visit", "visit_date", "Timespan", "this month")), "Count", None),
	"Load Requests": ("Van Stock Transfer", _f(("Van Stock Transfer", "docstatus", "=", 0)), "Count", None),
}

# name: (doctype, kind, type, filters, group_by_or_(based_on,value_field))
CHARTS = {
	"Field Sales per Month": ("Sales Invoice", "Sum", "Bar", _f(("Sales Invoice", "docstatus", "=", 1), ("Sales Invoice", "salesman", "is", "set")), ("posting_date", "grand_total")),
	"Visits by Outcome": ("Route Visit", "Group By", "Donut", _f(), "outcome"),
	"Handovers by Status": ("Salesman Cash Handover", "Group By", "Donut", _f(), "status"),
}

DASH = {
	"Field Sales": (["Sales Today", "Field Sales This Month", "Pending Cash Handovers", "Visits Today"], ["Field Sales per Month", "Visits by Outcome"]),
}


def write_dashboards():
	for name, (dt, flt, fn, field) in CARDS.items():
		card = {"creation": STAMP, "docstatus": 0, "doctype": "Number Card", "document_type": dt, "filters_json": flt,
			"function": fn, "idx": 0, "is_public": 1, "is_standard": 1, "label": name, "modified": STAMP,
			"modified_by": "Administrator", "module": MODULE, "name": name, "owner": "Administrator",
			"show_percentage_stats": 1, "stats_time_interval": "Monthly", "type": "Document Type"}
		if field:
			card["aggregate_function_based_on"] = field
		dump(os.path.join(APP, "field_sales", "number_card", scrub(name), scrub(name) + ".json"), card)
	for name, (dt, kind, typ, flt, spec) in CHARTS.items():
		ch = {"chart_name": name, "chart_type": kind, "creation": STAMP, "docstatus": 0, "doctype": "Dashboard Chart",
			"document_type": dt, "dynamic_filters_json": "", "filters_json": flt, "idx": 0, "is_public": 1,
			"is_standard": 1, "modified": STAMP, "modified_by": "Administrator", "module": MODULE, "name": name,
			"number_of_groups": 0, "owner": "Administrator", "type": typ, "use_report_chart": 0, "y_axis": []}
		if kind == "Group By":
			ch.update({"group_by_based_on": spec, "group_by_type": "Count", "timeseries": 0})
		else:
			ch.update({"based_on": spec[0], "value_based_on": spec[1], "timeseries": 1, "timespan": "Last Year",
				"time_interval": "Monthly"})
		dump(os.path.join(APP, "field_sales", "dashboard_chart", scrub(name), scrub(name) + ".json"), ch)


def main():
	write_dashboards()
	dock_items, icons = [], []
	for idx, (title, lucide, dock_icon, items, related) in enumerate(MODULES):
		# ---- workspace (landing page of the module)
		content = [{"id": uuid.uuid4().hex[:10], "type": "header",
			"data": {"text": f'<span class="h4"><b>{title}</b></span>', "col": 12}}]
		cards, charts = DASH.get(title, ([], []))
		for c in charts:
			content.append({"id": uuid.uuid4().hex[:10], "type": "chart", "data": {"chart_name": c, "col": 6}})
		for c in cards:
			content.append({"id": uuid.uuid4().hex[:10], "type": "number_card", "data": {"number_card_name": c, "col": 3}})
		shortcuts = []
		for label, target, kind, ic in items:
			content.append({"id": uuid.uuid4().hex[:10], "type": "shortcut", "data": {"shortcut_name": label, "col": 3}})
			sc = {"label": label, "link_to": target, "type": kind}
			if kind == "URL":
				sc = {"label": label, "url": target, "type": "URL"}
			elif kind == "DocType":
				sc["doc_view"] = "List"
			else:
				sc["report_ref_doctype"] = REPORT_DT[target]
			shortcuts.append(sc)
		mod = os.path.join(APP, scrub(title))
		os.makedirs(mod, exist_ok=True)
		open(os.path.join(mod, "__init__.py"), "a").close()
		dump(os.path.join(mod, "workspace", scrub(title), scrub(title) + ".json"), {
			"charts": [{"chart_name": c, "label": c} for c in charts], "content": json.dumps(content), "creation": STAMP, "custom_blocks": [], "docstatus": 0,
			"doctype": "Workspace", "for_user": "", "hide_custom": 1, "icon": lucide, "idx": idx + 1,
			"is_hidden": 0, "label": title, "links": [], "modified": STAMP, "modified_by": "Administrator",
			"module": title, "name": title, "number_cards": [{"label": c, "number_card_name": c} for c in cards], "owner": "Administrator", "parent_page": "",
			"public": 1, "quick_lists": [], "roles": [], "sequence_id": float(idx + 20), "shortcuts": shortcuts,
			"title": title, "type": "Workspace",
		})
		# ---- sidebar (frappe 16.5x: a standard `Sidebar` rooted at the app, owned by the module)
		sb = [item("Home", title, "Workspace", "house")]
		for label, target, kind, ic in items:
			sb.append(item(label, target, kind, ic))
		if related:
			sb.append(section("Related", "link-2"))
			for label, target, ic in related:
				sb.append(item(label, target, "DocType", ic, child=1))
		for i, it in enumerate(sb, start=1):
			it.update({"doctype": "Sidebar Item", "parentfield": "items", "parenttype": "Sidebar", "idx": i})
		dump(os.path.join(APP, "sidebar", scrub(title), scrub(title) + ".json"), {
			"doctype": "Sidebar", "name": title, "module": title, "title": title, "header_icon": lucide,
			"app": "ledgerx_sales", "standard": 1, "items": sb,
		})
		# ---- dock entry
		dock_items.append({"added": 0, "hidden": 0, "icon": dock_icon, "link_to": title, "link_type": "Sidebar", "title": title})

	dump(os.path.join(APP, "dock", "ledgerx_sales", "ledgerx_sales.json"), {
		"app": "ledgerx_sales", "creation": STAMP, "docstatus": 0, "doctype": "Dock", "idx": 0, "items": dock_items,
		"modified": STAMP, "modified_by": "Administrator", "name": "ledgerx_sales", "owner": "Administrator", "standard": 1,
	})


if __name__ == "__main__":
	main()
