from __future__ import annotations

from datetime import date, datetime, time, timedelta

from .config import DT_FMT


def local_now() -> datetime:
    return datetime.now().replace(second=0, microsecond=0)


def parse_dt(value: str) -> datetime:
    return datetime.strptime(value, DT_FMT)


def format_db_dt(value: datetime) -> str:
    return value.strftime(DT_FMT)


def format_day(value: date) -> str:
    return value.strftime("%A").upper()


def format_short_date(value: date) -> str:
    return f"{value.month}/{value.day}/{value.year}"


def format_time(value: datetime | None) -> str:
    if value is None:
        return ""
    return value.strftime("%I:%M%p").lstrip("0")


def format_hours(total_minutes: int) -> str:
    hours, minutes = divmod(max(0, int(total_minutes)), 60)
    if hours == 0 and minutes == 0:
        return "0h0m"
    return f"{hours}h{minutes:02d}m"


def format_log_timestamp(value: datetime) -> str:
    return f"{format_short_date(value.date())} {format_time(value)}"


def parse_user_datetime(date_text: str, time_text: str) -> datetime:
    raw_date = date_text.strip()
    raw_time = time_text.strip().upper().replace(" ", "")
    parsed_date = None
    for fmt in ("%Y-%m-%d", "%m/%d/%Y", "%#m/%#d/%Y", "%m/%d/%y"):
        try:
            parsed_date = datetime.strptime(raw_date, fmt).date()
            break
        except ValueError:
            pass
    if parsed_date is None:
        raise ValueError("Use date format YYYY-MM-DD or M/D/YYYY.")

    parsed_time = None
    for fmt in ("%I:%M%p", "%H:%M"):
        try:
            parsed_time = datetime.strptime(raw_time, fmt).time()
            break
        except ValueError:
            pass
    if parsed_time is None:
        raise ValueError("Use time format 3:45AM or 15:45.")

    return datetime.combine(parsed_date, parsed_time)


def week_start_for(value: date) -> date:
    return value - timedelta(days=value.weekday())


def split_shift_segments(start: datetime, end: datetime) -> list[tuple[datetime, datetime]]:
    if end < start:
        raise ValueError("Clock-out cannot be earlier than time-in.")
    if start.date() == end.date():
        return [(start, end)]

    segments: list[tuple[datetime, datetime]] = []
    first_end = datetime.combine(start.date(), time(23, 59))
    segments.append((start, first_end))

    current_day = start.date() + timedelta(days=1)
    while current_day < end.date():
        segments.append(
            (
                datetime.combine(current_day, time(0, 0)),
                datetime.combine(current_day, time(23, 59)),
            )
        )
        current_day += timedelta(days=1)

    segments.append((datetime.combine(end.date(), time(0, 0)), end))
    return segments


def split_shift_for_view(start: datetime, end: datetime, target_day: date) -> tuple[datetime, datetime] | None:
    if end < start:
        return None
    day_start = datetime.combine(target_day, time(0, 0))
    day_end = datetime.combine(target_day, time(23, 59))
    clipped_start = max(start, day_start)
    clipped_end = min(end, day_end)
    if clipped_start.date() != target_day and clipped_end.date() != target_day:
        return None
    if clipped_end < clipped_start:
        return None
    return clipped_start, clipped_end


def minutes_between(start: datetime, end: datetime) -> int:
    return max(0, int((end - start).total_seconds() // 60))


def clamp_int(value: str, minimum: int, maximum: int) -> int:
    try:
        number = int(value)
    except ValueError:
        number = minimum
    return max(minimum, min(maximum, number))


def minute_after_scroll(current: str, direction: int, shift_held: bool = False) -> str:
    step = 10 if shift_held else 1
    minute = (clamp_int(current, 0, 59) + (direction * step)) % 60
    return f"{minute:02d}"
