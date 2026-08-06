"""analysis 서비스(기간 계산·요약 문장) 테스트."""
import unittest
from datetime import date

from app.services import analysis


class PeriodRangeTest(unittest.TestCase):
    def test_week_starts_sunday(self):
        # 2026-07-12는 일요일
        start, end, _ = analysis.period_range("주간", date(2026, 7, 12))
        self.assertEqual((start, end), ("2026-07-12", "2026-07-18"))
        # 주중 어느 날이든 같은 주
        start, end, _ = analysis.period_range("주간", date(2026, 7, 15))
        self.assertEqual((start, end), ("2026-07-12", "2026-07-18"))

    def test_month_handles_leap_february(self):
        start, end, label = analysis.period_range("월간", date(2024, 2, 10))
        self.assertEqual((start, end), ("2024-02-01", "2024-02-29"))
        self.assertEqual(label, "2024 / 02")

    def test_year(self):
        start, end, label = analysis.period_range("연간", date(2026, 7, 12))
        self.assertEqual((start, end), ("2026-01-01", "2026-12-31"))
        self.assertEqual(label, "2026")

    def test_unknown_unit_raises(self):
        with self.assertRaises(ValueError):
            analysis.period_range("분기", date(2026, 7, 12))


class ShiftAnchorTest(unittest.TestCase):
    def test_week_shift(self):
        self.assertEqual(analysis.shift_anchor("주간", date(2026, 7, 12), -1),
                         date(2026, 7, 5))

    def test_month_shift_across_year(self):
        self.assertEqual(analysis.shift_anchor("월간", date(2026, 1, 15), -1),
                         date(2025, 12, 1))
        self.assertEqual(analysis.shift_anchor("월간", date(2025, 12, 3), 1),
                         date(2026, 1, 1))

    def test_year_shift(self):
        self.assertEqual(analysis.shift_anchor("연간", date(2026, 7, 12), 1),
                         date(2027, 1, 1))


class SummarySentenceTest(unittest.TestCase):
    def test_empty(self):
        self.assertIn("없어요", analysis.mood_summary_sentence(0, 0, 0))

    def test_positive_majority(self):
        self.assertIn("좋은 날이 더 많았", analysis.mood_summary_sentence(3, 1, 1))

    def test_negative_majority(self):
        self.assertIn("힘든 날", analysis.mood_summary_sentence(1, 0, 4))

    def test_tie(self):
        self.assertIn("비슷", analysis.mood_summary_sentence(2, 1, 2))


if __name__ == "__main__":
    unittest.main()
