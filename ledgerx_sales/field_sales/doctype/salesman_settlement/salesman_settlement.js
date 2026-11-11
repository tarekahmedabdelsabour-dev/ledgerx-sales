frappe.ui.form.on("Salesman Settlement", {
	refresh(frm) {
		if (frm.doc.docstatus === 0 && !frm.is_new()) return;
	},
	salesman(frm) {
		if (!frm.doc.salesman) return;
		frappe.db.get_value("Salesman", frm.doc.salesman, "warehouse").then((r) => {
			const wh = r.message && r.message.warehouse;
			if (!wh || (frm.doc.stock_lines || []).length) return;
			frappe.db.get_list("Bin", { filters: { warehouse: wh, actual_qty: [">", 0] }, fields: ["item_code", "actual_qty"], limit: 500 }).then((rows) => {
				rows.forEach((b) => frm.add_child("stock_lines", { item_code: b.item_code, system_qty: b.actual_qty, counted_qty: b.actual_qty }));
				frm.refresh_field("stock_lines");
			});
		});
	},
});
