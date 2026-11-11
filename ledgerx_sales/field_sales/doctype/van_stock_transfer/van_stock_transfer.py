import frappe
from frappe import _
from frappe.model.document import Document
from frappe.utils import flt

from ledgerx_sales.utils import sales


class VanStockTransfer(Document):
	def validate(self):
		s = sales.settings()
		sm = frappe.get_doc("Salesman", self.salesman)
		self.company = self.company or sales.company_of(sm, s)
		if not sm.warehouse:
			frappe.throw(_("Salesman {0} has no van warehouse").format(sm.name))
		if not s.main_warehouse:
			frappe.throw(_("Set the main warehouse in Field Sales Settings"))
		if self.transfer_type == "Load":
			self.from_warehouse, self.to_warehouse = s.main_warehouse, sm.warehouse
		else:
			self.from_warehouse, self.to_warehouse = sm.warehouse, s.main_warehouse
		if not self.items:
			frappe.throw(_("Add at least one item"))
		for r in self.items:
			if flt(r.qty) <= 0:
				frappe.throw(_("Row {0}: quantity must be greater than zero").format(r.idx))

	def on_submit(self):
		name = sales.create_stock_transfer(self)
		self.db_set("stock_entry", name)

	def on_cancel(self):
		sales.cancel_linked("Stock Entry", self.stock_entry)
