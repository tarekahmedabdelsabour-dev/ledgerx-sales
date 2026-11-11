frappe.query_reports["Salesman Performance"] = {
	filters: [
		{ fieldname: "company", label: __("Company"), fieldtype: "Link", options: "Company", default: frappe.defaults.get_user_default("Company") },
		{ fieldname: "salesman", label: __("Salesman"), fieldtype: "Link", options: "Salesman" },
		{ fieldname: "from_date", label: __("From"), fieldtype: "Date", reqd: 1, default: frappe.datetime.month_start() },
		{ fieldname: "to_date", label: __("To"), fieldtype: "Date", reqd: 1, default: frappe.datetime.get_today() },
	],
};
