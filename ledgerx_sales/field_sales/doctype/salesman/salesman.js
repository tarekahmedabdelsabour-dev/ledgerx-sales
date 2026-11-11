frappe.ui.form.on("Salesman", {
	refresh(frm) {
		if (frm.is_new()) return;
		if (!frm.doc.warehouse || !frm.doc.cash_account) {
			frm.add_custom_button(__("Create Van Warehouse and Cash Account"), () =>
				frm.call("create_accounts").then((r) => {
					frappe.show_alert({ message: __("Created: {0}", [(r.message || []).join(", ")]), indicator: "green" });
					frm.reload_doc();
				})
			, __("Setup"));
		}
		frm.add_custom_button(__("Salesman Screen"), () => window.open("/salesman", "_blank"));
		frm.add_custom_button(__("Cash Position"), () => frappe.set_route("query-report", "Salesman Cash Position", { salesman: frm.doc.name }), __("View"));
		frm.add_custom_button(__("Receivables"), () => frappe.set_route("query-report", "Salesman Receivables", { salesman: frm.doc.name }), __("View"));
		frm.add_custom_button(__("Performance"), () => frappe.set_route("query-report", "Salesman Performance", { salesman: frm.doc.name }), __("View"));
		if (frm.doc.employee && frm.doc.commission_percent) {
			frm.add_custom_button(__("Create Commission (Additional Salary)"), () => {
				frappe.prompt([
					{ fieldname: "from_date", fieldtype: "Date", label: __("From"), reqd: 1, default: frappe.datetime.month_start() },
					{ fieldname: "to_date", fieldtype: "Date", label: __("To"), reqd: 1, default: frappe.datetime.month_end() },
				], (v) => frm.call("create_commission", v).then((r) => frappe.set_route("Form", "Additional Salary", r.message)),
				__("Commission Period"));
			}, __("HR"));
		}
		if (frm.doc.vehicle) frm.add_custom_button(__("Vehicle"), () => frappe.set_route("Form", "Vehicle", frm.doc.vehicle), __("View"));
		if (frm.doc.warehouse) frm.add_custom_button(__("Van Stock"), () => frappe.set_route("query-report", "Stock Balance", { warehouse: frm.doc.warehouse }), __("View"));
	},
	user(frm) {
		if (frm.doc.user && !frm.doc.salesman_name) frappe.db.get_value("User", frm.doc.user, "full_name").then((r) => frm.set_value("salesman_name", r.message.full_name));
	},
});
