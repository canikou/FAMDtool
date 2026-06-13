import unittest
from datetime import datetime

from famd_tool import (
    LogEntry,
    build_individual_log_text,
    first_image_path,
    format_hours,
    parse_image_paths,
    serialize_image_paths,
    split_shift_segments,
    VITAL_TYPES,
    week_start_for,
)


class TimeLogicTests(unittest.TestCase):
    def test_week_starts_on_sunday(self):
        self.assertEqual(
            week_start_for(datetime(2026, 6, 13).date()).isoformat(),
            "2026-06-07",
        )

    def test_formats_zero_and_nonzero_hours(self):
        self.assertEqual(format_hours(0), "0h0m")
        self.assertEqual(format_hours(83), "1h23m")
        self.assertEqual(format_hours(191), "3h11m")

    def test_same_day_shift_stays_single_segment(self):
        start = datetime(2026, 6, 8, 3, 45)
        end = datetime(2026, 6, 8, 5, 8)

        self.assertEqual(split_shift_segments(start, end), [(start, end)])

    def test_overnight_shift_splits_at_manual_boundary(self):
        start = datetime(2026, 6, 11, 23, 0)
        end = datetime(2026, 6, 12, 2, 0)

        self.assertEqual(
            split_shift_segments(start, end),
            [
                (datetime(2026, 6, 11, 23, 0), datetime(2026, 6, 11, 23, 59)),
                (datetime(2026, 6, 12, 0, 0), datetime(2026, 6, 12, 2, 0)),
            ],
        )

    def test_multi_day_shift_splits_each_day(self):
        start = datetime(2026, 6, 11, 23, 0)
        end = datetime(2026, 6, 13, 2, 0)

        self.assertEqual(
            split_shift_segments(start, end),
            [
                (datetime(2026, 6, 11, 23, 0), datetime(2026, 6, 11, 23, 59)),
                (datetime(2026, 6, 12, 0, 0), datetime(2026, 6, 12, 23, 59)),
                (datetime(2026, 6, 13, 0, 0), datetime(2026, 6, 13, 2, 0)),
            ],
        )

    def test_individual_vital_export_text(self):
        entry = LogEntry(
            id=1,
            event_date=datetime(2026, 6, 13).date(),
            kind="vital",
            postal="8092",
            event_type="TREATMENT",
            responders="Yeol Bakunawa",
            details="",
            image_path="",
            created_at=datetime(2026, 6, 13, 4, 30),
        )

        self.assertEqual(
            build_individual_log_text(entry),
            "Timestamp: 6/13/2026 4:30AM\n"
            "Postal: 8092\n"
            "Specify: TREATMENT\n"
            "Responder/s: Yeol Bakunawa\n"
            "Vital ss:",
        )

    def test_individual_response_export_text(self):
        entry = LogEntry(
            id=2,
            event_date=datetime(2026, 6, 13).date(),
            kind="response",
            postal="1000",
            event_type="ROBBERY",
            responders="Yeol Bakunawa Wildtime",
            details="",
            image_path="",
            created_at=datetime(2026, 6, 13, 5, 8),
        )

        self.assertEqual(
            build_individual_log_text(entry),
            "Timestamp: 6/13/2026 5:08AM\n"
            "Type: ROBBERY\n"
            "Postal: 1000\n"
            "Responder/s: Yeol Bakunawa Wildtime\n"
            "Screenshot:",
        )

    def test_multiple_image_paths_round_trip(self):
        payload = serialize_image_paths(["one.png", "two.png"])

        self.assertEqual(parse_image_paths(payload), ["one.png", "two.png"])
        self.assertEqual(first_image_path(payload), "one.png")
        self.assertEqual(parse_image_paths("legacy.png"), ["legacy.png"])

    def test_vital_types_include_revival(self):
        self.assertIn("REVIVAL", VITAL_TYPES)


if __name__ == "__main__":
    unittest.main()
