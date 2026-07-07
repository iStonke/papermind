import unittest
from datetime import date

from sqlalchemy import true

from app.services.dashboard import DashboardService, _add_months, _first_of_month


class _FakeRow:
    def __init__(self, year: int, count: int) -> None:
        self.year = year
        self.count = count


class _FakeResult:
    def __init__(self, rows: list["_FakeRow"]) -> None:
        self._rows = rows

    def all(self) -> list["_FakeRow"]:
        return self._rows


class _FakeDB:
    """Gibt für jede execute()-Abfrage dieselben vorgegebenen Jahres-Zeilen zurück."""

    def __init__(self, rows: list["_FakeRow"]) -> None:
        self._rows = rows

    def execute(self, *_args, **_kwargs) -> "_FakeResult":
        return _FakeResult(self._rows)


class DocumentsPerYearClippingTest(unittest.TestCase):
    TODAY = date(2026, 7, 7)  # current_year - 30 == 1996

    def _series(self, rows: list["_FakeRow"]):
        service = DashboardService(_FakeDB(rows))
        return service._documents_per_year(self.TODAY, true())

    def test_older_documents_are_folded_into_clipped_start_bucket(self) -> None:
        # 1988 und 1990 liegen vor dem 30-Jahre-Deckel (1996) und müssen in den
        # 1996-Startbalken einfließen, der dadurch als clipped markiert wird.
        series = self._series([_FakeRow(1988, 3), _FakeRow(1990, 2), _FakeRow(2005, 4)])
        by_year = {p.year: p for p in series}

        start = by_year[1996]
        self.assertEqual(start.count, 5)  # 3 + 2 eingefaltet, keine echten 1996er
        self.assertTrue(start.clipped)

        self.assertEqual(by_year[2005].count, 4)
        self.assertFalse(by_year[2005].clipped)
        # Nur der Startbalken ist clipped.
        self.assertEqual([p.year for p in series if p.clipped], [1996])

    def test_start_bucket_merges_clipped_and_real_counts(self) -> None:
        series = self._series([_FakeRow(1990, 2), _FakeRow(1996, 4)])
        start = next(p for p in series if p.year == 1996)
        self.assertEqual(start.count, 6)  # 4 echte 1996er + 2 eingefaltet
        self.assertTrue(start.clipped)

    def test_no_clipping_when_earliest_within_cap(self) -> None:
        # Ältestes Jahr liegt innerhalb des Deckels -> nichts wird eingefaltet.
        series = self._series([_FakeRow(2020, 3), _FakeRow(2026, 1)])
        by_year = {p.year: p for p in series}
        self.assertEqual(by_year[2020].count, 3)
        self.assertFalse(by_year[2020].clipped)
        self.assertEqual([p.year for p in series if p.clipped], [])


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
