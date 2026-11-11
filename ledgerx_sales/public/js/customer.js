frappe.ui.form.on("Customer", {
	refresh(frm) {
		if (frm.is_new()) return;
		if (frm.doc.default_salesman) {
			frm.add_custom_button(__("Salesman"), () => frappe.set_route("Form", "Salesman", frm.doc.default_salesman), __("Field Sales"));
		}
		frm.add_custom_button(__("Route Visits"), () => frappe.set_route("List", "Route Visit", { customer: frm.doc.name }), __("Field Sales"));
		if (frm.doc.fs_latitude && frm.doc.fs_longitude) {
			frm.add_custom_button(__("Open Shop on Map"), () =>
				window.open(`https://www.google.com/maps?q=${frm.doc.fs_latitude},${frm.doc.fs_longitude}`, "_blank"), __("Field Sales"));
		}
	},
});
