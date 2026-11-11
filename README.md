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
