frappe.ui.form.on("Salesman Cash Handover", {
	refresh(frm) {
		if (frm.is_new() || frm.doc.status !== "Pending") return;
		frm.add_custom_button(__("Confirm Receipt"), () =>
			frappe.confirm(__("Confirm that you received {0}?", [format_currency(frm.doc.amount)]), () =>
				frm.call("confirm").then(() => frm.reload_doc())), null).addClass("btn-primary");
		frm.add_custom_button(__("Reject"), () =>
			frappe.prompt({ fieldname: "reason", fieldtype: "Small Text", label: __("Rejection Reason"), reqd: 1 },
				(v) => frm.call("reject", { reason: v.reason }).then(() => frm.reload_doc())));
	},
});
