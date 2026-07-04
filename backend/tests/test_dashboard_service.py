import unittest
from datetime import date

from app.services.dashboard import _add_months, _first_of_month


class DashboardDateMathTest(unittest.TestCase):
    def test_first_of_month(self) -> None:
        self.assertEqual(_first_of_month(date(2026, 7, 4)), date(2026, 7, 1))
        self.assertEqual(_first_of_month(date(2026, 2, 28)), date(2026, 2, 1))

    def test_add_months_forward(self) -> None:
        self.assertEqual(_add_months(date(2026, 7, 1), 1), date(2026, 8, 1))
        self.assertEqual(_add_months(date(2026, 11, 1), 3), date(2027, 2, 1))

    def test_add_months_backward_crosses_year(self) -> None:
        # 12-Monats-Fenster: aktueller Monat minus 11 Monate.
        self.assertEqual(_add_months(date(2026, 7, 1), -11), date(2025, 8, 1))
        self.assertEqual(_add_months(date(2026, 1, 1), -1), date(2025, 12, 1))

    def test_add_months_zero_is_identity(self) -> None:
        self.assertEqual(_add_months(date(2026, 3, 1), 0), date(2026, 3, 1))

    def test_twelve_month_window_is_contiguous(self) -> None:
        month_start = _first_of_month(date(2026, 7, 15))
        window_start = _add_months(month_start, -11)
        months = [_add_months(window_start, i) for i in range(12)]
        self.assertEqual(len(months), 12)
        self.assertEqual(months[0], date(2025, 8, 1))
        self.assertEqual(months[-1], date(2026, 7, 1))
        # Keine Duplikate, streng aufsteigend.
        self.assertEqual(months, sorted(set(months)))


if __name__ == "__main__":
    unittest.main()
