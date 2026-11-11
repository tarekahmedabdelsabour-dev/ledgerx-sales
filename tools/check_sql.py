"""Parse every frappe.db.sql() query with sqlglot (MySQL dialect) and check table/column names
against the DocType specs.   python3 tools/check_sql.py   (needs: pip install sqlglot)"""
import ast
import json
import os
import re
import sys

import sqlglot
from sqlglot import exp

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
APP = os.path.join(ROOT, "ledgerx_sales")
STD = {"name", "owner", "creation", "modified", "modified_by", "docstatus", "idx", "parent", "parentfield", "parenttype"}

schema = {}
for d in os.listdir(os.path.join(APP, "field_sales", "doctype")):
	p = os.path.join(APP, "field_sales", "doctype", d, d + ".json")
	if os.path.isfile(p):
		j = json.load(open(p, encoding="utf-8"))
		schema["tab" + j["name"]] = {f["fieldname"] for f in j["fields"]} | STD
# external tables we touch: only the columns we use
schema["tabVehicle"] = STD | {"last_odometer", "fleet_status", "fleet_cost_center", "current_driver", "payload_kg",
	"fuel_type", "gps_device", "service_plan", "last_position_lat", "last_position_lng", "last_position_time"}
schema["tabDriver"] = STD | {"employee", "current_vehicle", "full_name"}
schema["tabAccount"] = STD | {"report_type"}
errors = []


def sql_strings(path):
	tree = ast.parse(open(path, encoding="utf-8").read())
	for n in ast.walk(tree):
		is_sql = isinstance(n, ast.Call) and (
			(isinstance(n.func, ast.Attribute) and n.func.attr == "sql") or (isinstance(n.func, ast.Name) and n.func.id == "_sum")
		)
		if is_sql and n.args:
			a = n.args[0]
			if isinstance(a, ast.Constant) and isinstance(a.value, str):
				yield n.lineno, a.value
			elif isinstance(a, ast.JoinedStr):
				out = ""
				for v in a.values:
					if isinstance(v, ast.Constant):
						out += v.value
					else:
						tail = out.rstrip().lower()
						out += " 1=1 " if tail.endswith(("where", "and")) else " "
				yield n.lineno, out


def check(path, lineno, sql):
	q = re.sub(r"%\(\w+\)s", "1", sql)
	q = q.replace("%s", "1").replace("%%", "%")
	if not q.lstrip().lower().startswith(("select", "update", "delete")):
		return
	try:
		tree = sqlglot.parse_one(q, read="mysql")
	except Exception as e:
		errors.append(f"{path}:{lineno}: SQL does not parse: {str(e)[:120]}")
		return
	aliases = {}
	for t in tree.find_all(exp.Table):
		aliases[(t.alias or t.name)] = t.name
	selects = {a.alias for a in tree.find_all(exp.Alias)}
	for t in set(aliases.values()):
		if t.startswith("tab") and t not in schema:
			errors.append(f"{path}:{lineno}: unknown table {t}")
	for c in tree.find_all(exp.Column):
		col, tbl = c.name, c.table
		if tbl:
			tname = aliases.get(tbl)
			if tname in schema and col not in schema[tname]:
				errors.append(f"{path}:{lineno}: {tname}.{col} does not exist")
		else:
			if col in selects:
				continue
			owners = [t for t in set(aliases.values()) if t in schema]
			if owners and not any(col in schema[t] for t in owners) and len(owners) == len(set(aliases.values())):
				errors.append(f"{path}:{lineno}: column {col} not in {sorted(set(aliases.values()))}")


n = 0
for base, _d, files in os.walk(APP):
	for f in files:
		if f.endswith(".py"):
			p = os.path.join(base, f)
			for line, s in sql_strings(p):
				n += 1
				check(os.path.relpath(p, ROOT), line, s)
for e in errors:
	print("ERROR:", e)
print(f"{n} queries checked, {len(errors)} errors")
sys.exit(1 if errors else 0)
