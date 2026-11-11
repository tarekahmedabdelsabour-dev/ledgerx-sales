import unittest
from datetime import date

from ledgerx_sales.utils import logic as L


class TestLogic(unittest.TestCase):
	def test_haversine(self):
		self.assertEqual(L.haversine_m(30.0, 31.0, 30.0, 31.0), 0)
		d = L.haversine_m(30.0444, 31.2357, 30.0444, 31.2457)
		self.assertTrue(900 < d < 1100)
		self.assertIsNone(L.haversine_m(None, 1, 2, 3))

	def test_allocate_oldest_first(self):
		inv = [("B", 100, date(2026, 2, 1)), ("A", 50, date(2026, 1, 1)), ("C", 70, date(2026, 3, 1))]
		alloc, rest = L.allocate_payment(120, inv)
		self.assertEqual(alloc, [("A", 50), ("B", 70)])
		self.assertEqual(rest, 0)

	def test_allocate_remainder_and_zero(self):
		alloc, rest = L.allocate_payment(500, [("A", 50, date(2026, 1, 1)), ("Z", 0, date(2026, 1, 2))])
		self.assertEqual(alloc, [("A", 50)])
		self.assertEqual(rest, 450)
		self.assertEqual(L.allocate_payment(0, [("A", 5, date(2026, 1, 1))]), ([], 0.0))

	def test_aging(self):
		today = date(2026, 5, 1)
		t = L.aging_totals([(10, date(2026, 5, 10)), (20, date(2026, 4, 20)), (30, date(2026, 2, 1)), (5, date(2025, 12, 1))], today)
		self.assertEqual(t["current"], 10)
		self.assertEqual(t["1-30"], 20)
		self.assertEqual(t["61-90"], 30)
		self.assertEqual(t["90+"], 5)

	def test_credit(self):
		self.assertEqual(L.credit_check(100, 50, 0), (True, None))
		self.assertEqual(L.credit_check(100, 50, 200), (True, 100))
		self.assertEqual(L.credit_check(100, 150, 200), (False, 100))

	def test_cash_and_difference(self):
		self.assertEqual(L.cash_in_hand(1000, 400), 600)
		self.assertEqual(L.settlement_difference(590, 600), -10)

	def test_misc(self):
		self.assertEqual(L.commission(10000, 2.5), 250)
		self.assertEqual(L.target_progress(50, 200), 25)
		self.assertIsNone(L.target_progress(50, 0))
		self.assertEqual(L.discount_percent(90, 100), 10)
		self.assertEqual(L.discount_percent(110, 100), 0)
		self.assertEqual(L.split_payment(100, 40), (40, 60))
		self.assertEqual(L.weekday_name(date(2026, 11, 7)), "Saturday")
		self.assertEqual(L.visit_outcome(True, True), "Sale and Collection")
		self.assertEqual(L.visit_outcome(False, False), "No Order")

	def test_shortfalls(self):
		s = L.stock_shortfalls([("A", 3), ("A", 4), ("B", 1)], {"A": 5, "B": 1})
		self.assertEqual(s, [("A", 7, 5)])
