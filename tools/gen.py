"""DocType generator for ledgerx_sales.

Reads tools/spec.py (compact field specs) and writes DocType JSON + controller/JS stubs.
Existing .py / .js files are never overwritten, so hand-written logic is safe; JSON is always
regenerated from the spec. Also writes translations/ar.csv from tools/ar.py.

Run from the repo root:  python3 tools/gen.py
"""
import csv
import json
import os
import re
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(ROOT, "tools"))

import spec  # noqa: E402
from ar import AR, FALLBACK  # noqa: E402

APP = "ledgerx_sales"
MODULE = "Field Sales"
MODULE_DIR = os.path.join(ROOT, APP, "field_sales")
from datetime import datetime  # noqa: E402

# Must be newer than what the site already has, or `bench migrate` skips the changed file.
STAMP = datetime.now().strftime("%Y-%m-%d %H:%M:%S.%f")

SECTIONING = ("Section Break", "Column Break", "Tab Break")


def scrub(name):
	return re.sub(r"[\s\-]+", "_", name.strip()).lower()


def classname(name):
	return "".join(p.capitalize() if not p.isupper() else p for p in re.split(r"[\s\-]+", name))


def build_fields(items):
	fields = []
	cb = sec = 0
	for it in items:
		kind = it[0]
		if kind == "S":  # section: ("S", label, opts)
			sec += 1
			label = it[1]
			opts = dict(it[2]) if len(it) > 2 else {}
			f = {"fieldname": opts.pop("name", f"section_break_{sec}"), "fieldtype": "Section Break"}
			if label:
				f["label"] = label
			f.update(opts)
			fields.append(f)
		elif kind == "C":  # column break
			cb += 1
			opts = dict(it[1]) if len(it) > 1 else {}
			f = {"fieldname": f"column_break_{cb}", "fieldtype": "Column Break"}
			f.update(opts)
			fields.append(f)
		else:  # ("F", fieldname, fieldtype, label, opts)
			_, fieldname, ftype, label = it[:4]
			opts = dict(it[4]) if len(it) > 4 else {}
			f = {"fieldname": fieldname, "fieldtype": ftype, "label": label}
			f.update(opts)
			fields.append(f)
	return fields


PERMS = {
	"master": [
		("Sales Manager", "cr_w_d_exp_rep_prt_eml_shr"),
		("System Manager", "cr_w_d_exp_rep_prt_eml_shr"),
		("Sales User", "r_rep_prt"),
		("Accounts User", "r_rep"),
	],
	"ops": [
		("Sales Manager", "cr_w_d_exp_rep_prt_eml_shr_sub_can_amd"),
		("System Manager", "cr_w_d_exp_rep_prt_eml_shr_sub_can_amd"),
		("Sales User", "r_w_cr_rep_prt_sub"),
		("Accounts User", "r_rep_prt"),
	],
	"ops_nosubmit": [
		("Sales Manager", "cr_w_d_exp_rep_prt_eml_shr"),
		("System Manager", "cr_w_d_exp_rep_prt_eml_shr"),
		("Sales User", "r_w_cr_rep_prt"),
		("Accounts User", "r_rep_prt"),
	],
	"settings": [
		("Sales Manager", "r_w"),
		("System Manager", "r_w"),
	],
	"child": [],
}

KEYS = {
	"r": "read", "w": "write", "cr": "create", "d": "delete", "exp": "export", "rep": "report",
	"prt": "print", "eml": "email", "shr": "share", "sub": "submit", "can": "cancel", "amd": "amend",
}


def build_perms(kind):
	out = []
	for role, codes in PERMS[kind]:
		p = {"role": role}
		for c in codes.split("_"):
			p[KEYS[c]] = 1
		out.append(dict(sorted(p.items())))
	return out


def build_doctype(d):
	fields = build_fields(d["fields"])
	doc = {
		"actions": [],
		"creation": STAMP,
		"doctype": "DocType",
		"engine": "InnoDB",
		"field_order": [f["fieldname"] for f in fields],
		"fields": fields,
		"links": d.get("links", []),
		"modified": STAMP,
		"modified_by": "Administrator",
		"module": MODULE,
		"name": d["name"],
		"owner": "Administrator",
		"permissions": build_perms(d.get("perms", "master")) if not d.get("istable") else [],
		"sort_field": "creation",
		"sort_order": "DESC",
		"states": [],
	}
	if d.get("autoname"):
		doc["autoname"] = d["autoname"]
	for key in ("title_field", "search_fields", "image_field", "icon", "description"):
		if d.get(key):
			doc[key] = d[key]
	if d.get("istable"):
		doc["istable"] = 1
		doc["editable_grid"] = 1
	elif d.get("single"):
		doc["issingle"] = 1
	else:
		doc["track_changes"] = 1
		doc["allow_import"] = 1
		doc["show_title_field_in_link"] = 1 if d.get("title_field") else 0
	if d.get("submittable"):
		doc["is_submittable"] = 1
	if d.get("no_copy_doc"):
		doc["allow_copy"] = 0
	if d.get("sort_field"):
		doc["sort_field"] = d["sort_field"]
	if d.get("quick_entry") is not None:
		doc["quick_entry"] = d["quick_entry"]
	return doc


def write_json(path, data):
	os.makedirs(os.path.dirname(path), exist_ok=True)
	with open(path, "w", encoding="utf-8") as fh:
		json.dump(data, fh, indent=1, ensure_ascii=False)
		fh.write("\n")


def write_stub(path, text):
	if os.path.exists(path):
		return
	os.makedirs(os.path.dirname(path), exist_ok=True)
	with open(path, "w", encoding="utf-8") as fh:
		fh.write(text)


def strings_of(doc):
	out = {doc["name"]}
	for f in doc["fields"]:
		if f.get("label"):
			out.add(f["label"])
		if f["fieldtype"] == "Select" and f.get("options"):
			out.update(o for o in f["options"].split("\n") if o)
	return out


def main():
	all_strings = set()
	names = []
	for d in spec.DOCTYPES:
		doc = build_doctype(d)
		names.append(d["name"])
		folder = os.path.join(MODULE_DIR, "doctype", scrub(d["name"]))
		os.makedirs(folder, exist_ok=True)
		write_stub(os.path.join(folder, "__init__.py"), "")
		write_json(os.path.join(folder, scrub(d["name"]) + ".json"), doc)
		write_stub(
			os.path.join(folder, scrub(d["name"]) + ".py"),
			"from frappe.model.document import Document\n\n\n"
			f"class {classname(d['name'])}(Document):\n\tpass\n",
		)
		if not d.get("istable") and not d.get("single"):
			write_stub(os.path.join(folder, scrub(d["name"]) + ".js"), f'frappe.ui.form.on("{d["name"]}", {{}});\n')
		elif d.get("single"):
			write_stub(os.path.join(folder, scrub(d["name"]) + ".js"), f'frappe.ui.form.on("{d["name"]}", {{}});\n')
		all_strings |= strings_of(doc)

	# extra UI strings (reports, buttons, messages) registered in spec.EXTRA_STRINGS
	all_strings |= set(spec.EXTRA_STRINGS)

	import extract_strings  # noqa: E402

	all_strings |= extract_strings.collect()
	for s_ in all_strings:
		if s_ not in AR and s_ in FALLBACK:
			AR[s_] = FALLBACK[s_]
	missing = sorted(s for s in all_strings if s not in AR)
	if missing:
		print("MISSING Arabic for %d strings:" % len(missing))
		for s in missing:
			print("  ", json.dumps(s, ensure_ascii=False))
	rows = sorted(AR.items())  # every known string (spec + code), so code-only messages are covered too
	os.makedirs(os.path.join(ROOT, APP, "translations"), exist_ok=True)
	with open(os.path.join(ROOT, APP, "translations", "ar.csv"), "w", encoding="utf-8", newline="") as fh:
		w = csv.writer(fh)
		for r in rows:
			w.writerow(r)
	print("doctypes:", len(names), "translated strings:", len(rows), "missing:", len(missing))
	return 1 if missing else 0


if __name__ == "__main__":
	sys.exit(main())
