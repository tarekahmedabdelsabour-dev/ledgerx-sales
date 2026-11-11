frappe.query_reports["Salesman Cash Position"] = {
	filters: [
		{ fieldname: "company", label: __("Company"), fieldtype: "Link", options: "Company", default: frappe.defaults.get_user_default("Company") },
		{ fieldname: "salesman", label: __("Salesman"), fieldtype: "Link", options: "Salesman" },
	],
};
