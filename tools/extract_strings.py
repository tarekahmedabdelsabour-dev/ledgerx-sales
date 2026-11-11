"""List every translatable string used in py/js code and custom field definitions."""
import ast
import os
import re
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(ROOT))
sys.path.insert(0, os.path.join(ROOT, "tools"))


def py_strings(path):
	out = set()
	tree = ast.parse(open(path, encoding="utf-8").read())
	for n in ast.walk(tree):
		if isinstance(n, ast.Call) and isinstance(n.func, ast.Name) and n.func.id == "_" and n.args:
			a = n.args[0]
			if isinstance(a, ast.Constant) and isinstance(a.value, str):
				out.add(a.value)
	return out


JS_RE = re.compile(r"""__\(\s*(["'`])((?:\\.|(?!\1).)*)\1""")


def js_strings(path):
	return {m.group(2).replace('\\"', '"').replace("\\'", "'") for m in JS_RE.finditer(open(path, encoding="utf-8").read())}


def collect():
	found = set()
	for base, _d, files in os.walk(os.path.join(ROOT, "ledgerx_sales")):
		for f in files:
			p = os.path.join(base, f)
			if f.endswith(".py"):
				found |= py_strings(p)
			elif f.endswith(".js"):
				found |= js_strings(p)
	try:
		import frappe  # noqa: F401
	except ImportError:  # only the data tables of install.py are needed here
		import types

		for name in ("frappe", "frappe.custom", "frappe.custom.doctype", "frappe.custom.doctype.custom_field",
				"frappe.custom.doctype.custom_field.custom_field"):
			sys.modules[name] = types.ModuleType(name)
		sys.modules["frappe.custom.doctype.custom_field.custom_field"].create_custom_fields = lambda *a, **k: None
	from ledgerx_sales import install

	for flds in install.CUSTOM_FIELDS.values():
		for fld in flds:
			if fld.get("label"):
				found.add(fld["label"])
	import gen_desk

	for title, _l, _d, items, related in gen_desk.MODULES:
		found.add(title)
		found |= {it[0] for it in items} | {r[0] for r in related}
	found |= set(gen_desk.CARDS) | set(gen_desk.CHARTS)
	found |= {"Related", "Home", "Field Sales", "Field Salesman"}
	return found


if __name__ == "__main__":
	for s in sorted(collect()):
		print(s)
