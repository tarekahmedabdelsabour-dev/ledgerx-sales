"""Static checks for the app (run before every release):  python3 tools/validate.py"""
import ast
import json
import os
import re
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
APP = os.path.join(ROOT, "ledgerx_sales")
DT_DIR = os.path.join(APP, "field_sales", "doctype")

# DocTypes from Frappe / ERPNext / HRMS that we link to
EXTERNAL = {"Price List", "Territory", "UOM", "Payment Entry", "Route Customer", "Warehouse", "Journal Entry", "Stock Entry", "Item", "Customer", "Account", "Employee", "Driver", "Vehicle", "Salary Component",
	"Company", "Cost Center", "Account", "Vehicle", "Driver", "Employee", "Customer", "Supplier", "Item", "Warehouse",
	"Sales Invoice", "Journal Entry", "Stock Entry", "Salary Component", "Additional Salary", "User", "Role",
}
VALID_TYPES = {
	"Data", "Link", "Select", "Check", "Int", "Float", "Currency", "Date", "Datetime", "Small Text", "Text", "Attach",
	"Attach Image", "Table", "Password", "Read Only", "Section Break", "Column Break", "Tab Break", "Long Text",
	"Code", "Percent", "HTML", "Time", "Dynamic Link", "Text Editor",
}
DOC_ATTRS = {
	"name", "docstatus", "meta", "flags", "get", "set", "db_set", "doctype", "owner", "creation", "modified",
	"idx", "parent", "parentfield", "parenttype", "get_doc_before_save", "has_value_changed", "check_permission",
	"append", "save", "insert", "submit", "cancel", "is_new", "get_title", "is_submittable", "as_dict", "reload",
	"modified_by", "delete", "run_method", "db_insert", "set_user_and_timestamp", "validate", "on_update",
}

errors, warns = [], []


def err(msg):
	errors.append(msg)


def load_doctypes():
	out = {}
	for d in sorted(os.listdir(DT_DIR)):
		p = os.path.join(DT_DIR, d, d + ".json")
		if os.path.isfile(p):
			try:
				out[d] = json.load(open(p, encoding="utf-8"))
			except Exception as e:
				err(f"{p}: invalid JSON ({e})")
	return out


def check_doctypes(docs):
	names = {d["name"] for d in docs.values()}
	known = names | EXTERNAL
	children = {d["name"] for d in docs.values() if d.get("istable")}
	table_targets = set()
	for key, d in docs.items():
		n = d["name"]
		if key != re.sub(r"[\s\-]+", "_", n).lower():
			err(f"{n}: folder name {key} does not match")
		fn = [f["fieldname"] for f in d["fields"]]
		if len(fn) != len(set(fn)):
			err(f"{n}: duplicate fieldnames {[x for x in fn if fn.count(x) > 1]}")
		if d["field_order"] != fn:
			err(f"{n}: field_order mismatch")
		fields = {f["fieldname"]: f for f in d["fields"]}
		for f in d["fields"]:
			t = f["fieldtype"]
			where = f"{n}.{f['fieldname']}"
			if t not in VALID_TYPES:
				err(f"{where}: bad fieldtype {t}")
			if t not in ("Section Break", "Column Break", "Tab Break") and not f.get("label"):
				err(f"{where}: missing label")
			if t in ("Link", "Table") and f.get("options") not in known:
				err(f"{where}: unknown doctype {f.get('options')!r}")
			if t == "Table":
				table_targets.add(f["options"])
				if f["options"] not in children:
					err(f"{where}: {f['options']} is not a child table")
			if t == "Select" and not f.get("options"):
				err(f"{where}: Select without options")
			if t == "Select" and f.get("default") and f["default"] not in f["options"].split("\n"):
				err(f"{where}: default {f['default']!r} not in options")
			if f.get("fetch_from"):
				link, _, target = f["fetch_from"].partition(".")
				if link not in fields or fields[link]["fieldtype"] != "Link":
					err(f"{where}: fetch_from link {link} missing")
				else:
					tgt = fields[link]["options"]
					td = next((x for x in docs.values() if x["name"] == tgt), None)
					if td and target not in {x["fieldname"] for x in td["fields"]}:
						err(f"{where}: fetch_from target {tgt}.{target} missing")
			for k in ("depends_on", "mandatory_depends_on"):
				for ref in re.findall(r"doc\.(\w+)", f.get(k, "") or ""):
					if ref not in fields and ref not in ("docstatus", "name"):
						err(f"{where}: {k} uses unknown field {ref}")
				if f.get(k) and not f[k].startswith("eval:") and f[k] not in fields:
					err(f"{where}: {k} {f[k]!r} not a field")
		an = d.get("autoname", "")
		if an.startswith("field:") and an[6:] not in fields:
			err(f"{n}: autoname field {an[6:]} missing")
		if d.get("title_field") and d["title_field"] not in fields:
			err(f"{n}: title_field missing")
		for sf in (d.get("search_fields") or "").split(","):
			if sf and sf.strip() not in fields:
				err(f"{n}: search field {sf} missing")
		if d.get("is_submittable") and "amended_from" not in fields:
			err(f"{n}: submittable without amended_from")
		if d.get("is_submittable") and not any(p.get("submit") for p in d["permissions"]):
			err(f"{n}: submittable but nobody can submit")
		if not d.get("istable") and not d.get("issingle") and not d.get("autoname"):
			err(f"{n}: no autoname")
		if not d.get("istable") and not d["permissions"]:
			err(f"{n}: no permissions")
		for f in d["fields"]:
			if f["fieldtype"] == "Table" and f.get("reqd") is None:
				pass
	for c in children - table_targets:
		err(f"child table {c} is not used by any parent")


def class_info(path):
	tree = ast.parse(open(path, encoding="utf-8").read())
	return tree, [n for n in tree.body if isinstance(n, ast.ClassDef)]


def check_controllers(docs):
	for key, d in docs.items():
		n = d["name"]
		py = os.path.join(DT_DIR, key, key + ".py")
		if not os.path.isfile(py):
			err(f"{n}: controller missing")
			continue
		tree, classes = class_info(py)
		want = "".join(p if p.isupper() else p.capitalize() for p in re.split(r"[\s\-]+", n))
		if want not in [c.name for c in classes]:
			err(f"{n}: class {want} not found in {key}.py")
			continue
		cls = next(c for c in classes if c.name == want)
		methods = {m.name for m in cls.body if isinstance(m, ast.FunctionDef)}
		fields = {f["fieldname"] for f in d["fields"]}
		for node in ast.walk(cls):
			if isinstance(node, ast.Attribute) and isinstance(node.value, ast.Name) and node.value.id == "self":
				a = node.attr
				if a not in fields and a not in methods and a not in DOC_ATTRS:
					err(f"{n}: self.{a} is not a field or method")
		# fields written/read through child rows
		if d.get("istable"):
			continue
		js = os.path.join(DT_DIR, key, key + ".js")
		if not os.path.isfile(js):
			err(f"{n}: js missing")


def check_whitelisted_refs():
	pat = re.compile(r"ledgerx_sales\.[\w\.]+")
	for base, _d, files in os.walk(APP):
		for f in files:
			if not f.endswith((".js", ".py")):
				continue
			text = open(os.path.join(base, f), encoding="utf-8").read()
			for ref in set(pat.findall(text)):
				ref = ref.rstrip(".")
				parts = ref.split(".")
				for cut in range(len(parts), 1, -1):
					mod = os.path.join(ROOT, *parts[:cut]) + ".py"
					if os.path.isfile(mod):
						attr = parts[cut:]
						if attr:
							src = open(mod, encoding="utf-8").read()
							if not re.search(rf"def {attr[0]}\(", src):
								err(f"{f}: {ref}: function {attr[0]} not defined in {mod}")
						break
				else:
					if ref.count(".") > 1 and not ref.endswith((".css", ".js")):
						err(f"{f}: cannot resolve {ref}")


def check_hooks():
	text = open(os.path.join(APP, "hooks.py"), encoding="utf-8").read()
	for ref in re.findall(r'"(ledgerx_sales\.[\w\.]+)"', text):
		parts = ref.split(".")
		mod = os.path.join(ROOT, *parts[:-1]) + ".py"
		if not os.path.isfile(mod):
			err(f"hooks: module for {ref} missing")
		elif not re.search(rf"def {parts[-1]}\(", open(mod, encoding="utf-8").read()):
			err(f"hooks: {ref} not defined")
	for m in re.findall(r'"(public/js/[\w\./]+)"', text):
		if not os.path.isfile(os.path.join(APP, m)):
			err(f"hooks: {m} missing")
	for m in re.findall(r"/assets/ledgerx_sales/([\w\./-]+)", text):
		if not os.path.isfile(os.path.join(APP, "public", m)):
			err(f"hooks: asset {m} missing")


def check_reports():
	rep = os.path.join(APP, "field_sales", "report")
	for d in sorted(os.listdir(rep)):
		p = os.path.join(rep, d)
		if not os.path.isdir(p) or d.startswith("__"):
			continue
		j = json.load(open(os.path.join(p, d + ".json"), encoding="utf-8"))
		if j["report_type"] != "Script Report" or not os.path.isfile(os.path.join(p, d + ".py")):
			err(f"report {d} incomplete")
		if "def execute(" not in open(os.path.join(p, d + ".py"), encoding="utf-8").read():
			err(f"report {d}: no execute()")
	from_install = open(os.path.join(APP, "install.py"), encoding="utf-8").read()
	for m in re.findall(r'"(\w[\w ]+)", "\1", "Report"', from_install):
		if not os.path.isdir(os.path.join(rep, re.sub(r"\s+", "_", m).lower())):
			err(f"install.py links to missing report {m}")


def check_translations():
	import csv

	rows = list(csv.reader(open(os.path.join(APP, "translations", "ar.csv"), encoding="utf-8")))
	src = {r[0] for r in rows}
	for r in rows:
		ph = lambda s: sorted(re.findall(r"\{\d+\}", s))
		if ph(r[0]) != ph(r[1]):
			err(f"translation placeholders differ: {r[0]!r}")
	sys.path.insert(0, os.path.join(ROOT, "tools"))
	sys.path.insert(0, ROOT)
	import extract_strings

	for s in extract_strings.collect():
		if s.strip() and s not in src:
			err(f"no Arabic for {s!r}")


def main():
	docs = load_doctypes()
	check_doctypes(docs)
	check_controllers(docs)
	check_whitelisted_refs()
	check_hooks()
	check_reports()
	check_translations()
	for e in errors:
		print("ERROR:", e)
	print(f"{len(docs)} doctypes checked, {len(errors)} errors")
	return 1 if errors else 0


if __name__ == "__main__":
	sys.exit(main())
