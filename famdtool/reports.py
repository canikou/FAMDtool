from __future__ import annotations

from datetime import date, datetime, timedelta

from .database import FamdDatabase
from .models import Shift
from .time_utils import (
    format_day,
    format_hours,
    format_short_date,
    format_time,
    local_now,
    minutes_between,
    split_shift_for_view,
)


def display_shifts_for_day(db: FamdDatabase, day: date, now: datetime | None = None) -> list[Shift]:
    current_time = now or local_now()
    results: list[Shift] = []
    for shift in db.list_shifts_for_day(day):
        actual_end = shift.end or current_time
        clipped = split_shift_for_view(shift.start, actual_end, day)
        if clipped:
            clipped_start, clipped_end = clipped
            end_value = clipped_end if shift.end or clipped_end < current_time else None
            results.append(Shift(shift.id, clipped_start, end_value))
    return results


def total_minutes(
    db: FamdDatabase,
    start_day: date,
    end_day: date,
    now: datetime | None = None,
) -> int:
    current_time = now or local_now()
    total = 0
    current_day = start_day
    while current_day <= end_day:
        for shift in db.list_shifts_for_day(current_day):
            actual_end = shift.end or current_time
            clipped = split_shift_for_view(shift.start, actual_end, current_day)
            if clipped:
                total += minutes_between(*clipped)
        current_day += timedelta(days=1)
    return total


def build_weekly_export_text(
    db: FamdDatabase,
    week_start: date,
    now: datetime | None = None,
) -> str:
    lines = ["======================================="]
    week_end = week_start + timedelta(days=6)
    total_responses = 0

    for offset in range(7):
        day = week_start + timedelta(days=offset)
        shifts = display_shifts_for_day(db, day, now)
        responses = len(db.list_logs_for_day("response", day))
        total_responses += responses
        time_ins = " | ".join(format_time(shift.start) for shift in shifts)
        clock_outs = " | ".join(format_time(shift.end) for shift in shifts)
        lines.extend(
            [
                format_day(day),
                f"Date: {format_short_date(day)}",
                f"Time-in: {time_ins}",
                f"Clock-out: {clock_outs}",
                f"Total Robbery/Distress Response: {responses}",
                f"TOTAL HOURS: {format_hours(total_minutes(db, day, day, now))}",
                "--",
            ]
        )

    if lines[-1] == "--":
        lines.pop()
    lines.extend(
        [
            "",
            f"Total Robbery/Distress Responses: {total_responses}",
            f"TOTAL HOURS FOR THE WEEK: {format_hours(total_minutes(db, week_start, week_end, now))}",
            "=======================================",
        ]
    )
    return "\n".join(lines)
