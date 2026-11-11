frappe.ui.form.on("Van Stock Transfer", {
	refresh(frm) {
		if (frm.doc.stock_entry) frm.add_custom_button(__("Stock Entry"), () => frappe.set_route("Form", "Stock Entry", frm.doc.stock_entry), __("View"));
	},
});
