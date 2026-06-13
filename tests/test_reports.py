import unittest
from datetime import date, datetime
from pathlib import Path
from tempfile import TemporaryDirectory

from famdtool.database import FamdDatabase
from famdtool.reports import build_weekly_export_text, display_shifts_for_day, total_minutes


class ReportTests(unittest.TestCase):
    def test_empty_week_export_matches_manual_format(self):
        with TemporaryDirectory() as temp_dir:
            db = FamdDatabase(Path(temp_dir) / "test.sqlite3")

            text = build_weekly_export_text(db, date(2026, 6, 7))

            self.assertIn("SUNDAY\nDate: 6/7/2026\nTime-in: \nClock-out:", text)
            self.assertIn("SATURDAY\nDate: 6/13/2026", text)
            self.assertIn("Total Robbery/Distress Responses: 0", text)
            self.assertIn("TOTAL HOURS FOR THE WEEK: 0h0m", text)
            self.assertTrue(text.endswith("======================================="))
            self.assertNotIn("\n--\n\nTotal Robbery", text)
            db.close()

    def test_export_uses_only_selected_week_logs_and_shifts(self):
        with TemporaryDirectory() as temp_dir:
            db = FamdDatabase(Path(temp_dir) / "test.sqlite3")
            db.add_shift(datetime(2026, 6, 6, 1, 0), datetime(2026, 6, 6, 2, 0))
            db.add_shift(datetime(2026, 6, 7, 1, 0), datetime(2026, 6, 7, 2, 0))
            db.add_shift(datetime(2026, 6, 8, 3, 0), datetime(2026, 6, 8, 4, 0))
            db.add_shift(datetime(2026, 6, 14, 5, 0), datetime(2026, 6, 14, 6, 0))
            db.add_log("response", date(2026, 6, 6), "old", "ROBBERY", "Yeol", "", "")
            db.add_log("response", date(2026, 6, 7), "included", "ROBBERY", "Yeol", "", "")
            db.add_log("response", date(2026, 6, 8), "1000", "ROBBERY", "Yeol", "", "")
            db.add_log("response", date(2026, 6, 14), "future", "ROBBERY", "Yeol", "", "")

            text = build_weekly_export_text(db, date(2026, 6, 7))

            self.assertIn("Time-in: 1:00AM", text)
            self.assertIn("Time-in: 3:00AM", text)
            self.assertIn("Total Robbery/Distress Responses: 2", text)
            self.assertIn("TOTAL HOURS FOR THE WEEK: 2h00m", text)
            self.assertNotIn("5:00AM", text)
            db.close()

    def test_display_shifts_clips_active_shift_to_requested_day(self):
        with TemporaryDirectory() as temp_dir:
            db = FamdDatabase(Path(temp_dir) / "test.sqlite3")
            db.start_shift(datetime(2026, 6, 11, 23, 30))
            now = datetime(2026, 6, 12, 0, 30)

            day_four = display_shifts_for_day(db, date(2026, 6, 11), now)
            day_five = display_shifts_for_day(db, date(2026, 6, 12), now)

            self.assertEqual(day_four[0].start, datetime(2026, 6, 11, 23, 30))
            self.assertEqual(day_four[0].end, datetime(2026, 6, 11, 23, 59))
            self.assertEqual(day_five[0].start, datetime(2026, 6, 12, 0, 0))
            self.assertIsNone(day_five[0].end)
            db.close()

    def test_total_minutes_with_active_shift_uses_supplied_now(self):
        with TemporaryDirectory() as temp_dir:
            db = FamdDatabase(Path(temp_dir) / "test.sqlite3")
            db.start_shift(datetime(2026, 6, 13, 4, 0))

            self.assertEqual(
                total_minutes(db, date(2026, 6, 13), date(2026, 6, 13), datetime(2026, 6, 13, 6, 15)),
                135,
            )
            db.close()


if __name__ == "__main__":
    unittest.main()
