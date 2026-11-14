# LedgerX Sales (Field Sales)

شاشة مندوب المبيعات للموبايل فوق LedgerX — تطبيق Frappe مستقل (`ledgerx_sales`) يعتمد على `erpnext`.

Mobile salesman (van-sales) app for LedgerX: route, customers and debts, sales from the van warehouse,
collections, cash / bank-deposit handover, GPS visits, and day close.

دليل التشغيل بالعربي: [SALESMAN_AR.md](SALESMAN_AR.md)

## Install
```
cd ~/frappe-bench-v16
bench get-app <repo-url> ledgerx_sales    # or copy the folder into apps/
bench --site mysite.localhost install-app ledgerx_sales
bench --site mysite.localhost migrate
```
Status: written and statically checked (JSON, SQL parse, unit tests of the business rules); not yet run against a live site.

## HR link (0.2.0)

- **One person:** saving a salesman fills the Driver (same login user) and the Employee (from the driver, else the employee with the same user) when they are empty.
- **Attendance:** the first check-in or sale of the day marks the employee Present (nothing is created if the driver screen already did); closing the day sets the working hours.
- **Commission:** on the 1st of each month a draft Additional Salary is created per active salesman for last month (needs the commission salary component in Field Sales Settings). The per-salesman button does the same for any period and never duplicates.
