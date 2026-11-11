"""Field specs for every Field Sales DocType. See gen.py."""


def F(fieldname, ftype, label, **o):
	return ("F", fieldname, ftype, label, o)


def S(label="", **o):
	return ("S", label, o)


def C(**o):
	return ("C", o)


def COMPANY(**o):
	return F("company", "Link", "Company", **{"options": "Company", **o})


DOCTYPES = []
WEEKDAYS = "Saturday\nSunday\nMonday\nTuesday\nWednesday\nThursday\nFriday\nEvery Day"

# --------------------------------------------------------------------------- settings
DOCTYPES.append(dict(
	name="Field Sales Settings", single=True, perms="settings", icon="fa fa-cog",
	fields=[
		S("General"),
		COMPANY(),
		F("cost_center", "Link", "Default Cost Center", options="Cost Center"),
		F("default_price_list", "Link", "Default Selling Price List", options="Price List"),
		C(),
		F("main_warehouse", "Link", "Main Warehouse (loads come from here)", options="Warehouse"),
		F("require_gps", "Check", "Require GPS at Check-in", default=1),
		F("max_visit_distance", "Int", "Allowed Distance from Customer (m)", default=300,
			description="A check-in farther than this from the customer's saved location is flagged. 0 = off."),
		S("Sales Rules"),
		F("block_credit_over_limit", "Check", "Block Credit Sales Over the Customer Limit", default=1),
		F("allow_negative_van_stock", "Check", "Allow Selling Beyond Van Stock", default=0),
		C(),
		F("day_close_tolerance", "Currency", "Cash Difference Tolerance at Day Close", default=5),
		S("Cash and Accounting"),
		F("cashier_account", "Link", "Company Cash Account (receives handovers)", options="Account"),
		F("default_bank_account", "Link", "Default Bank Account (deposits and transfers)", options="Account"),
		C(),
		F("cash_parent_account", "Link", "Parent Group for Salesman Cash Accounts", options="Account",
			description="Each salesman gets his own cash account under this group (an asset group such as Cash In Hand)."),
		F("commission_component", "Link", "Salary Component for Commission", options="Salary Component"),
	],
))

# --------------------------------------------------------------------------- salesman
DOCTYPES.append(dict(
	name="Salesman", autoname="format:SM-{#####}", title_field="salesman_name", icon="fa fa-user-circle",
	search_fields="salesman_name,mobile_no,user", perms="master", quick_entry=0,
	fields=[
		F("salesman_name", "Data", "Salesman Name", reqd=1, in_list_view=1),
		F("user", "Link", "Login User", options="User", reqd=1, unique=1, in_list_view=1,
			description="The user this salesman logs in with on the mobile screen (/salesman)."),
		F("status", "Select", "Status", options="Active\nOn Leave\nInactive", default="Active", in_list_view=1,
			in_standard_filter=1),
		C(),
		F("mobile_no", "Data", "Mobile No", options="Phone"),
		F("employee", "Link", "Employee", options="Employee", description="HR link: used for commission payroll."),
		F("driver", "Link", "Driver", options="Driver", description="Fleet link: if he also drives, start and end of day record the odometer."),
		S("Van and Stock"),
		F("vehicle", "Link", "Vehicle", options="Vehicle", in_standard_filter=1),
		F("warehouse", "Link", "Van Warehouse", options="Warehouse",
			description="The stock he carries in the vehicle."),
		C(),
		F("cash_account", "Link", "Salesman Cash Account", options="Account",
			description="Collected cash accumulates here until he hands it over."),
		COMPANY(),
		S("Selling Rules"),
		F("price_list", "Link", "Price List", options="Price List"),
		F("territory", "Link", "Territory", options="Territory"),
		F("cost_center", "Link", "Cost Center", options="Cost Center"),
		C(),
		F("can_sell_on_credit", "Check", "Can Sell on Credit", default=1),
		F("max_discount_percent", "Percent", "Max Discount %", default=10),
		F("default_route", "Link", "Default Route", options="Sales Route"),
		S("Target and Commission"),
		F("monthly_target", "Currency", "Monthly Sales Target"),
		F("commission_percent", "Percent", "Commission %"),
		C(),
		F("commission_basis", "Select", "Commission On", options="Collected\nInvoiced", default="Collected"),
	],
))

# --------------------------------------------------------------------------- routes
DOCTYPES.append(dict(name="Route Customer", istable=1, fields=[
	F("customer", "Link", "Customer", options="Customer", reqd=1, in_list_view=1),
	F("customer_name", "Data", "Customer Name", fetch_from="customer.customer_name", read_only=1, in_list_view=1),
	F("sequence", "Int", "Stop Order", in_list_view=1),
	F("area", "Data", "Area / Address", in_list_view=1),
	F("latitude", "Float", "Latitude", precision="6"),
	F("longitude", "Float", "Longitude", precision="6"),
	F("notes", "Small Text", "Notes"),
]))

DOCTYPES.append(dict(
	name="Sales Route", autoname="field:route_name", icon="fa fa-road", search_fields="route_name,salesman",
	perms="master", quick_entry=0,
	fields=[
		F("route_name", "Data", "Route Name", reqd=1, unique=1, in_list_view=1),
		F("salesman", "Link", "Salesman", options="Salesman", in_list_view=1, in_standard_filter=1),
		F("weekday", "Select", "Day", options=WEEKDAYS, default="Every Day", in_list_view=1, in_standard_filter=1),
		C(),
		F("is_active", "Check", "Active", default=1),
		COMPANY(),
		S("Stops"),
		F("customers", "Table", "Customers", options="Route Customer"),
	],
))

DOCTYPES.append(dict(
	name="Route Visit", autoname="format:VIS-{YYYY}-{#####}", title_field="customer", icon="fa fa-map-marker",
	search_fields="salesman,customer", perms="ops_nosubmit",
	fields=[
		F("salesman", "Link", "Salesman", options="Salesman", reqd=1, in_list_view=1, in_standard_filter=1),
		F("route", "Link", "Route", options="Sales Route", in_standard_filter=1),
		F("customer", "Link", "Customer", options="Customer", reqd=1, in_list_view=1),
		F("visit_date", "Date", "Date", reqd=1, default="Today", in_list_view=1, in_standard_filter=1),
		C(),
		F("status", "Select", "Status", options="Planned\nChecked In\nCompleted\nSkipped", default="Planned",
			in_list_view=1, in_standard_filter=1),
		F("outcome", "Select", "Outcome", options="\nSale\nCollection\nSale and Collection\nNo Order\nShop Closed\nPostponed",
			in_list_view=1),
		S("Check-in"),
		F("check_in", "Datetime", "Check-in Time", read_only=1),
		F("check_out", "Datetime", "Check-out Time", read_only=1),
		F("in_latitude", "Float", "Latitude", read_only=1, precision="6"),
		F("in_longitude", "Float", "Longitude", read_only=1, precision="6"),
		C(),
		F("distance_m", "Int", "Distance from Customer (m)", read_only=1),
		F("out_of_range", "Check", "Out of Range", read_only=1),
		F("photo", "Attach Image", "Shop Photo"),
		S("Result"),
		F("sales_total", "Currency", "Sales Total", read_only=1),
		F("collected_total", "Currency", "Collected Total", read_only=1),
		C(),
		F("notes", "Small Text", "Notes"),
		F("request_id", "Data", "Request ID", hidden=1, read_only=1, no_copy=1, search_index=1),
		COMPANY(hidden=1),
	],
))

# --------------------------------------------------------------------------- van stock
DOCTYPES.append(dict(name="Van Transfer Item", istable=1, fields=[
	F("item_code", "Link", "Item", options="Item", reqd=1, in_list_view=1),
	F("item_name", "Data", "Item Name", fetch_from="item_code.item_name", read_only=1, in_list_view=1),
	F("qty", "Float", "Qty", reqd=1, in_list_view=1),
	F("uom", "Link", "UOM", options="UOM", fetch_from="item_code.stock_uom", in_list_view=1),
]))

DOCTYPES.append(dict(
	name="Van Stock Transfer", autoname="format:VST-{YYYY}-{#####}", title_field="salesman", icon="fa fa-truck",
	search_fields="salesman,transfer_type", perms="ops", submittable=True,
	fields=[
		F("transfer_type", "Select", "Transfer Type", options="Load\nReturn", reqd=1, default="Load", in_list_view=1,
			in_standard_filter=1, description="Load: main warehouse to the van. Return: van back to the main warehouse."),
		F("salesman", "Link", "Salesman", options="Salesman", reqd=1, in_list_view=1, in_standard_filter=1),
		F("posting_date", "Date", "Date", reqd=1, default="Today", in_list_view=1),
		C(),
		F("from_warehouse", "Link", "From Warehouse", options="Warehouse", read_only=1),
		F("to_warehouse", "Link", "To Warehouse", options="Warehouse", read_only=1),
		COMPANY(),
		S("Items"),
		F("items", "Table", "Items", options="Van Transfer Item", reqd=1),
		S("Reference"),
		F("remarks", "Small Text", "Remarks"),
		C(),
		F("stock_entry", "Link", "Stock Entry", options="Stock Entry", read_only=1, no_copy=1),
		F("requested_from_app", "Check", "Requested from the Mobile Screen", read_only=1, no_copy=1),
		F("request_id", "Data", "Request ID", hidden=1, read_only=1, no_copy=1, search_index=1),
		F("amended_from", "Link", "Amended From", options="Van Stock Transfer", read_only=1, no_copy=1, print_hide=1),
	],
))

# --------------------------------------------------------------------------- cash handover
DOCTYPES.append(dict(
	name="Salesman Cash Handover", autoname="format:SCH-{YYYY}-{#####}", title_field="salesman", icon="fa fa-money",
	search_fields="salesman,method,status", perms="ops_nosubmit",
	fields=[
		F("salesman", "Link", "Salesman", options="Salesman", reqd=1, in_list_view=1, in_standard_filter=1),
		F("posting_date", "Date", "Date", reqd=1, default="Today", in_list_view=1),
		C(),
		F("method", "Select", "Method", options="Cash to Cashier\nBank Deposit", reqd=1, default="Cash to Cashier",
			in_list_view=1, in_standard_filter=1),
		F("amount", "Currency", "Amount", reqd=1, in_list_view=1),
		S("Deposit Details", depends_on="eval:doc.method=='Bank Deposit'"),
		F("bank_account", "Link", "Bank Account", options="Account", mandatory_depends_on="eval:doc.method=='Bank Deposit'"),
		F("deposit_reference", "Data", "Deposit Reference"),
		C(),
		F("deposit_slip", "Attach Image", "Deposit Slip Photo"),
		S("Review"),
		F("status", "Select", "Status", options="Pending\nConfirmed\nRejected", default="Pending", in_list_view=1,
			in_standard_filter=1),
		F("cash_in_hand", "Currency", "Cash in Hand When Requested", read_only=1, no_copy=1),
		C(),
		F("reviewed_by", "Link", "Reviewed By", options="User", read_only=1, no_copy=1),
		F("rejection_reason", "Small Text", "Rejection Reason", depends_on="eval:doc.status=='Rejected'"),
		S("Accounting", collapsible=1),
		COMPANY(),
		F("journal_entry", "Link", "Journal Entry", options="Journal Entry", read_only=1, no_copy=1),
		F("request_id", "Data", "Request ID", hidden=1, read_only=1, no_copy=1, search_index=1),
	],
))

# --------------------------------------------------------------------------- day close
DOCTYPES.append(dict(name="Settlement Stock Line", istable=1, fields=[
	F("item_code", "Link", "Item", options="Item", reqd=1, in_list_view=1),
	F("item_name", "Data", "Item Name", fetch_from="item_code.item_name", read_only=1, in_list_view=1),
	F("system_qty", "Float", "System Qty", read_only=1, in_list_view=1),
	F("counted_qty", "Float", "Counted Qty", in_list_view=1),
	F("difference", "Float", "Difference", read_only=1, in_list_view=1),
]))

DOCTYPES.append(dict(
	name="Salesman Settlement", autoname="format:SSET-{YYYY}-{#####}", title_field="salesman", icon="fa fa-calendar-check-o",
	search_fields="salesman,settlement_date", perms="ops", submittable=True,
	fields=[
		F("salesman", "Link", "Salesman", options="Salesman", reqd=1, in_list_view=1, in_standard_filter=1),
		F("settlement_date", "Date", "Date", reqd=1, default="Today", in_list_view=1, in_standard_filter=1),
		C(),
		COMPANY(),
		F("difference", "Currency", "Cash Difference", read_only=1, in_list_view=1),
		S("Sales"),
		F("invoiced_total", "Currency", "Invoiced Total", read_only=1),
		F("credit_given", "Currency", "Given on Credit", read_only=1),
		C(),
		F("collections_cash", "Currency", "Collected in Cash", read_only=1),
		F("collections_other", "Currency", "Collected by Transfer / Cheque", read_only=1),
		S("Cash"),
		F("cash_in_hand", "Currency", "Cash in Hand (system)", read_only=1),
		F("cash_counted", "Currency", "Cash Counted"),
		C(),
		F("handed_over", "Currency", "Handed Over Today", read_only=1),
		S("Activity"),
		F("visits_planned", "Int", "Visits Planned", read_only=1),
		F("visits_completed", "Int", "Visits Completed", read_only=1),
		C(),
		F("distance_km", "Int", "Distance (km)", read_only=1),
		S("Van Stock Count"),
		F("stock_lines", "Table", "Stock Lines", options="Settlement Stock Line"),
		F("remarks", "Small Text", "Remarks"),
		F("amended_from", "Link", "Amended From", options="Salesman Settlement", read_only=1, no_copy=1, print_hide=1),
	],
))

EXTRA_STRINGS = []
