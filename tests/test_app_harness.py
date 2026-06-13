import sqlite3
import unittest
from datetime import date, datetime
from pathlib import Path
from tempfile import TemporaryDirectory

import famd_tool
from famdtool import config
from famd_tool import (
    DATE_FMT,
    DT_FMT,
    FamdDatabase,
    FamdToolApp,
    LogEntry,
    build_discord_card_image,
    copy_images_to_attachments,
    format_db_dt,
    minute_after_scroll,
    parse_user_datetime,
    parse_image_paths,
    serialize_image_paths,
)


class AppHarness:
    def __init__(self, db: FamdDatabase, week_start: date) -> None:
        self.app = object.__new__(FamdToolApp)
        self.app.db = db
        self.app.week_start = week_start

    def total_minutes(self, start_day: date, end_day: date) -> int:
        return FamdToolApp.total_minutes(self.app, start_day, end_day)

    def export_text(self) -> str:
        return FamdToolApp.build_export_text(self.app)


class DatabaseAndExportHarnessTests(unittest.TestCase):
    def test_manual_overnight_shift_is_split_and_totaled_per_day(self):
        with TemporaryDirectory() as temp_dir:
            db = FamdDatabase(Path(temp_dir) / "test.sqlite3")
            db.add_shift(datetime(2026, 6, 11, 23, 0), datetime(2026, 6, 12, 2, 0))

            day_four = db.list_shifts_for_day(date(2026, 6, 11))
            day_five = db.list_shifts_for_day(date(2026, 6, 12))
            harness = AppHarness(db, date(2026, 6, 7))

            self.assertEqual(len(day_four), 1)
            self.assertEqual(len(day_five), 1)
            self.assertEqual(harness.total_minutes(date(2026, 6, 11), date(2026, 6, 11)), 59)
            self.assertEqual(harness.total_minutes(date(2026, 6, 12), date(2026, 6, 12)), 120)
            db.close()

    def test_editing_shift_to_overnight_splits_existing_record(self):
        with TemporaryDirectory() as temp_dir:
            db = FamdDatabase(Path(temp_dir) / "test.sqlite3")
            db.add_shift(datetime(2026, 6, 11, 20, 0), datetime(2026, 6, 11, 21, 0))
            shift = db.list_shifts_for_day(date(2026, 6, 11))[0]

            db.update_shift(shift.id, datetime(2026, 6, 11, 23, 30), datetime(2026, 6, 12, 0, 30))

            self.assertEqual(len(db.list_shifts_for_day(date(2026, 6, 11))), 1)
            self.assertEqual(len(db.list_shifts_for_day(date(2026, 6, 12))), 1)
            db.close()

    def test_duplicate_active_shift_is_rejected(self):
        with TemporaryDirectory() as temp_dir:
            db = FamdDatabase(Path(temp_dir) / "test.sqlite3")
            db.start_shift(datetime(2026, 6, 13, 4, 0))

            with self.assertRaisesRegex(ValueError, "already an active shift"):
                db.start_shift(datetime(2026, 6, 13, 5, 0))

            db.close()

    def test_update_shift_to_active_rejects_when_another_active_shift_exists(self):
        with TemporaryDirectory() as temp_dir:
            db = FamdDatabase(Path(temp_dir) / "test.sqlite3")
            db.add_shift(datetime(2026, 6, 13, 1, 0), datetime(2026, 6, 13, 2, 0))
            closed_shift = db.list_shifts_for_day(date(2026, 6, 13))[0]
            db.start_shift(datetime(2026, 6, 13, 4, 0))

            with self.assertRaisesRegex(ValueError, "already an active shift"):
                db.update_shift(closed_shift.id, datetime(2026, 6, 13, 1, 0), None)

            db.close()

    def test_backwards_shift_is_rejected(self):
        with TemporaryDirectory() as temp_dir:
            db = FamdDatabase(Path(temp_dir) / "test.sqlite3")

            with self.assertRaisesRegex(ValueError, "earlier than time-in"):
                db.add_shift(datetime(2026, 6, 13, 5, 0), datetime(2026, 6, 13, 4, 0))

            db.close()

    def test_missing_shift_update_or_close_is_rejected(self):
        with TemporaryDirectory() as temp_dir:
            db = FamdDatabase(Path(temp_dir) / "test.sqlite3")

            with self.assertRaisesRegex(ValueError, "Shift not found"):
                db.update_shift(999, datetime(2026, 6, 13, 23, 0), datetime(2026, 6, 14, 1, 0))
            with self.assertRaisesRegex(ValueError, "Shift not found"):
                db.close_shift(999, datetime(2026, 6, 13, 23, 0), datetime(2026, 6, 14, 1, 0))
            self.assertEqual(db.list_shifts_for_day(date(2026, 6, 14)), [])
            db.close()

    def test_log_create_update_delete_and_created_timestamp_is_stable(self):
        with TemporaryDirectory() as temp_dir:
            db = FamdDatabase(Path(temp_dir) / "test.sqlite3")
            db.add_log("response", date(2026, 6, 13), " 1000 ", "robbery", " Yeol ", " notes ", "")
            entry = db.list_logs_for_day("response", date(2026, 6, 13))[0]
            created_at = entry.created_at

            self.assertEqual(entry.postal, "1000")
            self.assertEqual(entry.event_type, "ROBBERY")
            self.assertEqual(entry.responders, "Yeol")
            self.assertEqual(entry.details, "notes")

            db.update_log(entry.id, date(2026, 6, 13), "2000", "distress", "Yeol Two", "", "")
            updated = db.get_log(entry.id)

            self.assertIsNotNone(updated)
            self.assertEqual(updated.created_at, created_at)
            self.assertEqual(updated.event_type, "DISTRESS")
            db.delete_log(entry.id)
            self.assertIsNone(db.get_log(entry.id))
            db.close()

    def test_missing_log_update_is_rejected(self):
        with TemporaryDirectory() as temp_dir:
            db = FamdDatabase(Path(temp_dir) / "test.sqlite3")

            with self.assertRaisesRegex(ValueError, "Log not found"):
                db.update_log(999, date(2026, 6, 13), "1000", "ROBBERY", "Yeol", "", "")

            db.close()

    def test_settings_persist_across_connections(self):
        with TemporaryDirectory() as temp_dir:
            db_path = Path(temp_dir) / "test.sqlite3"
            db = FamdDatabase(db_path)
            db.set_setting("responder_name", "Yeol Bakunawa Wildtime")
            db.close()

            reopened = FamdDatabase(db_path)
            self.assertEqual(reopened.get_setting("responder_name"), "Yeol Bakunawa Wildtime")
            self.assertEqual(reopened.get_setting("missing", "fallback"), "fallback")
            reopened.close()

    def test_export_counts_multiple_shifts_and_response_totals(self):
        with TemporaryDirectory() as temp_dir:
            db = FamdDatabase(Path(temp_dir) / "test.sqlite3")
            db.add_shift(datetime(2026, 6, 8, 3, 45), datetime(2026, 6, 8, 5, 8))
            db.add_shift(datetime(2026, 6, 9, 2, 30), datetime(2026, 6, 9, 4, 20))
            db.add_shift(datetime(2026, 6, 9, 7, 52), datetime(2026, 6, 9, 9, 13))
            db.add_log("response", date(2026, 6, 9), "8092", "ROBBERY", "Yeol", "", "")
            db.add_log("response", date(2026, 6, 9), "1012", "DISTRESS", "Yeol", "", "")
            harness = AppHarness(db, date(2026, 6, 7))

            text = harness.export_text()

            self.assertIn("SUNDAY\nDate: 6/7/2026", text)
            self.assertIn("MONDAY\nDate: 6/8/2026\nTime-in: 3:45AM", text)
            self.assertIn("TUESDAY\nDate: 6/9/2026\nTime-in: 2:30AM | 7:52AM", text)
            self.assertIn("Clock-out: 4:20AM | 9:13AM", text)
            self.assertIn("Total Robbery/Distress Responses: 2", text)
            self.assertIn("TOTAL HOURS FOR THE WEEK: 4h34m", text)
            db.close()

    def test_old_database_schema_is_migrated_without_losing_logs(self):
        with TemporaryDirectory() as temp_dir:
            db_path = Path(temp_dir) / "legacy.sqlite3"
            conn = sqlite3.connect(db_path)
            conn.execute(
                """
                CREATE TABLE logs (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    event_date TEXT NOT NULL,
                    kind TEXT NOT NULL,
                    postal TEXT NOT NULL DEFAULT '',
                    event_type TEXT NOT NULL DEFAULT '',
                    details TEXT NOT NULL DEFAULT '',
                    created_at TEXT NOT NULL
                )
                """
            )
            conn.execute(
                """
                INSERT INTO logs (event_date, kind, postal, event_type, details, created_at)
                VALUES (?, ?, ?, ?, ?, ?)
                """,
                (
                    date(2026, 6, 13).strftime(DATE_FMT),
                    "vital",
                    "8092",
                    "TREATMENT",
                    "",
                    datetime(2026, 6, 13, 4, 30).strftime(DT_FMT),
                ),
            )
            conn.commit()
            conn.close()

            db = FamdDatabase(db_path)
            entry = db.list_logs_for_day("vital", date(2026, 6, 13))[0]

            self.assertEqual(entry.postal, "8092")
            self.assertEqual(entry.responders, "")
            self.assertEqual(entry.image_path, "")
            db.close()

    def test_invalid_log_kind_is_rejected_with_clear_error(self):
        with TemporaryDirectory() as temp_dir:
            db = FamdDatabase(Path(temp_dir) / "test.sqlite3")

            with self.assertRaisesRegex(ValueError, "response or vital"):
                db.add_log("repair", date(2026, 6, 13), "1000", "ROBBERY", "Yeol", "", "")
            with self.assertRaisesRegex(ValueError, "response or vital"):
                db.list_logs("repair", date(2026, 6, 13), date(2026, 6, 13))

            db.close()

    def test_blank_log_counter_uses_same_log_table_and_can_be_edited_later(self):
        with TemporaryDirectory() as temp_dir:
            db = FamdDatabase(Path(temp_dir) / "test.sqlite3")

            db.add_blank_log("response", date(2026, 6, 13), "Yeol")
            entry = db.list_logs_for_day("response", date(2026, 6, 13))[0]

            self.assertEqual(entry.postal, "")
            self.assertEqual(entry.event_type, "ROBBERY")
            self.assertEqual(entry.responders, "Yeol")
            self.assertEqual(entry.details, "")

            db.update_log(entry.id, date(2026, 6, 13), "8092", "distress", "Yeol", "notes", "")
            updated = db.get_log(entry.id)

            self.assertIsNotNone(updated)
            self.assertEqual(updated.postal, "8092")
            self.assertEqual(updated.event_type, "DISTRESS")
            db.close()

    def test_blank_log_decrement_prefers_blank_rows_and_clamps_at_zero(self):
        with TemporaryDirectory() as temp_dir:
            db = FamdDatabase(Path(temp_dir) / "test.sqlite3")
            db.add_log("response", date(2026, 6, 13), "1000", "ROBBERY", "Yeol", "detailed", "")
            db.add_blank_log("response", date(2026, 6, 13), "Yeol")

            deleted = db.delete_latest_log_for_day("response", date(2026, 6, 13))
            remaining = db.list_logs_for_day("response", date(2026, 6, 13))

            self.assertIsNotNone(deleted)
            self.assertEqual(deleted.postal, "")
            self.assertEqual(len(remaining), 1)
            self.assertEqual(remaining[0].postal, "1000")

            db.delete_latest_log_for_day("response", date(2026, 6, 13))
            self.assertIsNone(db.delete_latest_log_for_day("response", date(2026, 6, 13)))
            self.assertEqual(db.list_logs_for_day("response", date(2026, 6, 13)), [])
            db.close()


class UserInputEdgeCaseTests(unittest.TestCase):
    def test_parse_user_datetime_accepts_common_time_formats(self):
        self.assertEqual(
            parse_user_datetime("6/13/2026", "4:05AM"),
            datetime(2026, 6, 13, 4, 5),
        )
        self.assertEqual(
            parse_user_datetime("2026-06-13", "16:05"),
            datetime(2026, 6, 13, 16, 5),
        )

    def test_parse_user_datetime_rejects_bad_date_or_time(self):
        with self.assertRaisesRegex(ValueError, "date format"):
            parse_user_datetime("2026-02-30", "4:05AM")
        with self.assertRaisesRegex(ValueError, "time format"):
            parse_user_datetime("2026-06-13", "25:99")

    def test_minute_scroll_wraps_and_shift_steps_by_ten(self):
        self.assertEqual(minute_after_scroll("00", -1), "59")
        self.assertEqual(minute_after_scroll("59", 1), "00")
        self.assertEqual(minute_after_scroll("55", 1, shift_held=True), "05")
        self.assertEqual(minute_after_scroll("05", -1, shift_held=True), "55")
        self.assertEqual(minute_after_scroll("garbage", 1), "01")

    def test_image_path_parser_handles_json_strings_and_ignores_empty_values(self):
        self.assertEqual(parse_image_paths('"single.png"'), ["single.png"])
        self.assertEqual(parse_image_paths(serialize_image_paths(["", "one.png", "  "])), ["one.png"])
        self.assertEqual(parse_image_paths('["one.png", null, 3, ""]'), ["one.png"])
        self.assertEqual(parse_image_paths("{}"), [])

    def test_copy_images_to_attachments_copies_multiple_and_deduplicates(self):
        with TemporaryDirectory() as temp_dir:
            old_attach_dir = config.ATTACH_DIR
            config.ATTACH_DIR = Path(temp_dir) / "attachments"
            source = Path(temp_dir) / "source.png"
            source.write_bytes(b"fake image bytes")
            try:
                payload = copy_images_to_attachments([str(source), str(source)])
                paths = parse_image_paths(payload)

                self.assertEqual(len(paths), 1)
                self.assertTrue(Path(paths[0]).exists())
                self.assertEqual(Path(paths[0]).read_bytes(), b"fake image bytes")
            finally:
                config.ATTACH_DIR = old_attach_dir

    def test_copy_images_to_attachments_rejects_missing_file(self):
        with TemporaryDirectory() as temp_dir:
            old_attach_dir = config.ATTACH_DIR
            config.ATTACH_DIR = Path(temp_dir) / "attachments"
            try:
                with self.assertRaisesRegex(ValueError, "Image file not found"):
                    copy_images_to_attachments([str(Path(temp_dir) / "missing.png")])
            finally:
                config.ATTACH_DIR = old_attach_dir

    def test_build_discord_card_image_creates_png(self):
        if famd_tool.Image is None:
            self.skipTest("Pillow is not installed.")
        with TemporaryDirectory() as temp_dir:
            old_attach_dir = config.ATTACH_DIR
            config.ATTACH_DIR = Path(temp_dir) / "attachments"
            source = Path(temp_dir) / "source.png"
            famd_tool.Image.new("RGB", (64, 48), "red").save(source)
            entry = LogEntry(
                id=7,
                event_date=date(2026, 6, 13),
                kind="response",
                postal="8092",
                event_type="ROBBERY",
                responders="Yeol Bakunawa",
                details="",
                image_path=str(source),
                created_at=datetime(2026, 6, 13, 4, 30),
            )
            try:
                card_path = build_discord_card_image(entry)

                self.assertTrue(card_path.exists())
                self.assertEqual(card_path.suffix, ".png")
                self.assertGreater(card_path.stat().st_size, 0)
            finally:
                config.ATTACH_DIR = old_attach_dir


if __name__ == "__main__":
    unittest.main()
