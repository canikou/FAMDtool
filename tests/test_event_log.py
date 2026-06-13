import json
import unittest
from datetime import date, datetime
from pathlib import Path
from tempfile import TemporaryDirectory

from famdtool import config, event_log
from famdtool.attachments import serialize_image_paths
from famdtool.database import FamdDatabase


def read_log_records(log_dir: Path) -> list[dict]:
    records: list[dict] = []
    for path in sorted(log_dir.glob("famd_tool_*.log")):
        for line in path.read_text(encoding="utf-8").splitlines():
            records.append(json.loads(line))
    return records


class EventLogTests(unittest.TestCase):
    def setUp(self) -> None:
        event_log.flush_logs(timeout=2.0)

    def test_log_event_writes_json_line_asynchronously(self):
        with TemporaryDirectory() as temp_dir:
            old_log_dir = config.LOG_DIR
            config.LOG_DIR = Path(temp_dir) / "logs"
            try:
                event_log.log_event(
                    "unit_test_event",
                    affected_id=7,
                    path=Path("relative.png"),
                    when=datetime(2026, 6, 13, 4, 30),
                )

                self.assertTrue(event_log.flush_logs(timeout=2.0))
                records = read_log_records(config.LOG_DIR)

                self.assertEqual(len(records), 1)
                self.assertEqual(records[0]["event"], "unit_test_event")
                self.assertEqual(records[0]["data"]["affected_id"], 7)
                self.assertEqual(records[0]["data"]["path"], "relative.png")
                self.assertEqual(records[0]["data"]["when"], "2026-06-13T04:30:00")
                self.assertIn("timestamp", records[0])
                self.assertIn("source_thread", records[0])
            finally:
                event_log.flush_logs(timeout=2.0)
                config.LOG_DIR = old_log_dir

    def test_database_mutations_emit_verbose_records(self):
        with TemporaryDirectory() as temp_dir:
            old_log_dir = config.LOG_DIR
            config.LOG_DIR = Path(temp_dir) / "logs"
            db = FamdDatabase(Path(temp_dir) / "test.sqlite3")
            try:
                db.add_shift(datetime(2026, 6, 13, 23, 0), datetime(2026, 6, 14, 1, 0))
                db.add_log(
                    "response",
                    date(2026, 6, 13),
                    "8092",
                    "robbery",
                    "Yeol",
                    "",
                    serialize_image_paths(["one.png", "two.png"]),
                )
                entry = db.list_logs_for_day("response", date(2026, 6, 13))[0]
                db.update_log(entry.id, date(2026, 6, 13), "1012", "distress", "Yeol", "", "")
                db.delete_log(entry.id)
                db.close()

                self.assertTrue(event_log.flush_logs(timeout=2.0))
                records = read_log_records(config.LOG_DIR)
                events = {record["event"]: record for record in records}

                self.assertEqual(events["shift_added"]["data"]["segment_count"], 2)
                self.assertEqual(events["log_added"]["data"]["attachment_count"], 2)
                self.assertEqual(events["log_added"]["data"]["event_type"], "ROBBERY")
                self.assertEqual(events["log_updated"]["data"]["event_type"], "DISTRESS")
                self.assertEqual(events["log_deleted"]["data"]["deleted"], 1)
            finally:
                if db.conn:
                    try:
                        db.close()
                    except Exception:
                        pass
                event_log.flush_logs(timeout=2.0)
                config.LOG_DIR = old_log_dir


if __name__ == "__main__":
    unittest.main()
