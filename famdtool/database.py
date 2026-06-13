from __future__ import annotations

import sqlite3
from datetime import date, datetime, time, timedelta
from pathlib import Path

from .attachments import parse_image_paths
from . import config
from .event_log import log_event
from .models import LogEntry, Shift
from .time_utils import format_db_dt, local_now, parse_dt, split_shift_segments, week_start_for


class FamdDatabase:
    def __init__(self, path: Path) -> None:
        self.path = path
        self.conn = sqlite3.connect(path)
        self.conn.row_factory = sqlite3.Row
        self.init_schema()

    def init_schema(self) -> None:
        self.conn.executescript(
            """
            CREATE TABLE IF NOT EXISTS shifts (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                start_ts TEXT NOT NULL,
                end_ts TEXT
            );

            CREATE TABLE IF NOT EXISTS logs (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                event_date TEXT NOT NULL,
                kind TEXT NOT NULL CHECK(kind IN ('response', 'vital')),
                postal TEXT NOT NULL DEFAULT '',
                event_type TEXT NOT NULL DEFAULT '',
                responders TEXT NOT NULL DEFAULT '',
                details TEXT NOT NULL DEFAULT '',
                image_path TEXT NOT NULL DEFAULT '',
                created_at TEXT NOT NULL
            );

            CREATE TABLE IF NOT EXISTS settings (
                key TEXT PRIMARY KEY,
                value TEXT NOT NULL
            );
            """
        )
        columns = {
            row["name"] for row in self.conn.execute("PRAGMA table_info(logs)").fetchall()
        }
        if "image_path" not in columns:
            self.conn.execute("ALTER TABLE logs ADD COLUMN image_path TEXT NOT NULL DEFAULT ''")
        if "responders" not in columns:
            self.conn.execute("ALTER TABLE logs ADD COLUMN responders TEXT NOT NULL DEFAULT ''")
        self.conn.commit()

    def close(self) -> None:
        self.conn.close()

    def get_setting(self, key: str, default: str = "") -> str:
        row = self.conn.execute("SELECT value FROM settings WHERE key = ?", (key,)).fetchone()
        return row["value"] if row else default

    def set_setting(self, key: str, value: str) -> None:
        self.conn.execute(
            """
            INSERT INTO settings (key, value)
            VALUES (?, ?)
            ON CONFLICT(key) DO UPDATE SET value = excluded.value
            """,
            (key, value),
        )
        self.conn.commit()
        log_event("setting_saved", key=key, value=value)

    def get_active_shift(self) -> Shift | None:
        row = self.conn.execute(
            "SELECT * FROM shifts WHERE end_ts IS NULL ORDER BY start_ts DESC LIMIT 1"
        ).fetchone()
        return self._row_to_shift(row) if row else None

    def start_shift(self, start: datetime) -> None:
        if self.get_active_shift() is not None:
            raise ValueError("There is already an active shift.")
        cursor = self.conn.execute("INSERT INTO shifts (start_ts) VALUES (?)", (format_db_dt(start),))
        self.conn.commit()
        log_event(
            "shift_started",
            shift_id=cursor.lastrowid,
            start_ts=format_db_dt(start),
            database=str(self.path),
        )

    def add_shift(self, start: datetime, end: datetime | None) -> None:
        if end is None:
            self.start_shift(start)
            return
        inserted_ids: list[int] = []
        segments = split_shift_segments(start, end)
        for seg_start, seg_end in segments:
            cursor = self.conn.execute(
                "INSERT INTO shifts (start_ts, end_ts) VALUES (?, ?)",
                (format_db_dt(seg_start), format_db_dt(seg_end)),
            )
            inserted_ids.append(cursor.lastrowid)
        self.conn.commit()
        log_event(
            "shift_added",
            shift_ids=inserted_ids,
            requested_start_ts=format_db_dt(start),
            requested_end_ts=format_db_dt(end),
            segment_count=len(segments),
            segments=[
                {"start_ts": format_db_dt(seg_start), "end_ts": format_db_dt(seg_end)}
                for seg_start, seg_end in segments
            ],
            database=str(self.path),
        )

    def close_shift(self, shift_id: int, start: datetime, end: datetime) -> None:
        segments = split_shift_segments(start, end)
        first_start, first_end = segments[0]
        cursor = self.conn.execute(
            "UPDATE shifts SET start_ts = ?, end_ts = ? WHERE id = ?",
            (format_db_dt(first_start), format_db_dt(first_end), shift_id),
        )
        if cursor.rowcount == 0:
            self.conn.rollback()
            raise ValueError("Shift not found.")
        inserted_ids: list[int] = []
        for seg_start, seg_end in segments[1:]:
            extra_cursor = self.conn.execute(
                "INSERT INTO shifts (start_ts, end_ts) VALUES (?, ?)",
                (format_db_dt(seg_start), format_db_dt(seg_end)),
            )
            inserted_ids.append(extra_cursor.lastrowid)
        self.conn.commit()
        log_event(
            "shift_closed",
            shift_id=shift_id,
            inserted_shift_ids=inserted_ids,
            requested_start_ts=format_db_dt(start),
            requested_end_ts=format_db_dt(end),
            segment_count=len(segments),
            segments=[
                {"start_ts": format_db_dt(seg_start), "end_ts": format_db_dt(seg_end)}
                for seg_start, seg_end in segments
            ],
            database=str(self.path),
        )

    def list_shifts_for_range(self, start_day: date, end_day: date) -> list[Shift]:
        range_start = datetime.combine(start_day, time(0, 0))
        range_end = datetime.combine(end_day, time(23, 59))
        rows = self.conn.execute(
            """
            SELECT * FROM shifts
            WHERE start_ts <= ?
              AND COALESCE(end_ts, ?) >= ?
            ORDER BY start_ts
            """,
            (format_db_dt(range_end), format_db_dt(local_now()), format_db_dt(range_start)),
        ).fetchall()
        return [self._row_to_shift(row) for row in rows]

    def list_shifts_for_day(self, day: date) -> list[Shift]:
        return self.list_shifts_for_range(day, day)

    def update_shift(self, shift_id: int, start: datetime, end: datetime | None) -> None:
        if end is not None and end < start:
            raise ValueError("Clock-out cannot be earlier than time-in.")
        if end is None:
            active = self.get_active_shift()
            if active is not None and active.id != shift_id:
                raise ValueError("There is already an active shift.")
            cursor = self.conn.execute(
                "UPDATE shifts SET start_ts = ?, end_ts = NULL WHERE id = ?",
                (format_db_dt(start), shift_id),
            )
            if cursor.rowcount == 0:
                self.conn.rollback()
                raise ValueError("Shift not found.")
            self.conn.commit()
            log_event(
                "shift_updated",
                shift_id=shift_id,
                start_ts=format_db_dt(start),
                end_ts=None,
                active=True,
                database=str(self.path),
            )
            return

        segments = split_shift_segments(start, end)
        first_start, first_end = segments[0]
        cursor = self.conn.execute(
            "UPDATE shifts SET start_ts = ?, end_ts = ? WHERE id = ?",
            (format_db_dt(first_start), format_db_dt(first_end), shift_id),
        )
        if cursor.rowcount == 0:
            self.conn.rollback()
            raise ValueError("Shift not found.")
        inserted_ids: list[int] = []
        for seg_start, seg_end in segments[1:]:
            extra_cursor = self.conn.execute(
                "INSERT INTO shifts (start_ts, end_ts) VALUES (?, ?)",
                (format_db_dt(seg_start), format_db_dt(seg_end)),
            )
            inserted_ids.append(extra_cursor.lastrowid)
        self.conn.commit()
        log_event(
            "shift_updated",
            shift_id=shift_id,
            inserted_shift_ids=inserted_ids,
            requested_start_ts=format_db_dt(start),
            requested_end_ts=format_db_dt(end),
            segment_count=len(segments),
            segments=[
                {"start_ts": format_db_dt(seg_start), "end_ts": format_db_dt(seg_end)}
                for seg_start, seg_end in segments
            ],
            database=str(self.path),
        )

    def delete_shift(self, shift_id: int) -> None:
        existing = self.conn.execute("SELECT * FROM shifts WHERE id = ?", (shift_id,)).fetchone()
        cursor = self.conn.execute("DELETE FROM shifts WHERE id = ?", (shift_id,))
        self.conn.commit()
        log_event(
            "shift_deleted",
            shift_id=shift_id,
            deleted=cursor.rowcount,
            start_ts=existing["start_ts"] if existing else None,
            end_ts=existing["end_ts"] if existing else None,
            database=str(self.path),
        )

    def add_log(
        self,
        kind: str,
        event_date: date,
        postal: str,
        event_type: str,
        responders: str,
        details: str,
        image_path: str,
    ) -> None:
        if kind not in config.LOG_KINDS:
            raise ValueError("Log kind must be response or vital.")
        cursor = self.conn.execute(
            """
            INSERT INTO logs (
                event_date, kind, postal, event_type, responders, details, image_path, created_at
            )
            VALUES (?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                event_date.strftime(config.DATE_FMT),
                kind,
                postal.strip(),
                event_type.strip().upper(),
                responders.strip(),
                details.strip(),
                image_path.strip(),
                format_db_dt(local_now()),
            ),
        )
        self.conn.commit()
        log_event(
            "log_added",
            log_id=cursor.lastrowid,
            kind=kind,
            event_date=event_date.strftime(config.DATE_FMT),
            postal=postal.strip(),
            event_type=event_type.strip().upper(),
            responders=responders.strip(),
            attachment_count=len(parse_image_paths(image_path)),
            image_path=image_path.strip(),
            database=str(self.path),
        )

    def update_log(
        self,
        log_id: int,
        event_date: date,
        postal: str,
        event_type: str,
        responders: str,
        details: str,
        image_path: str,
    ) -> None:
        cursor = self.conn.execute(
            """
            UPDATE logs
               SET event_date = ?, postal = ?, event_type = ?, responders = ?, details = ?, image_path = ?
             WHERE id = ?
            """,
            (
                event_date.strftime(config.DATE_FMT),
                postal.strip(),
                event_type.strip().upper(),
                responders.strip(),
                details.strip(),
                image_path.strip(),
                log_id,
            ),
        )
        if cursor.rowcount == 0:
            self.conn.rollback()
            raise ValueError("Log not found.")
        self.conn.commit()
        log_event(
            "log_updated",
            log_id=log_id,
            event_date=event_date.strftime(config.DATE_FMT),
            postal=postal.strip(),
            event_type=event_type.strip().upper(),
            responders=responders.strip(),
            attachment_count=len(parse_image_paths(image_path)),
            image_path=image_path.strip(),
            database=str(self.path),
        )

    def delete_log(self, log_id: int) -> None:
        existing = self.get_log(log_id)
        cursor = self.conn.execute("DELETE FROM logs WHERE id = ?", (log_id,))
        self.conn.commit()
        log_event(
            "log_deleted",
            log_id=log_id,
            deleted=cursor.rowcount,
            kind=existing.kind if existing else None,
            event_date=existing.event_date.strftime(config.DATE_FMT) if existing else None,
            postal=existing.postal if existing else None,
            event_type=existing.event_type if existing else None,
            responders=existing.responders if existing else None,
            attachment_count=len(parse_image_paths(existing.image_path)) if existing else 0,
            database=str(self.path),
        )

    def list_logs(self, kind: str, start_day: date, end_day: date) -> list[LogEntry]:
        if kind not in config.LOG_KINDS:
            raise ValueError("Log kind must be response or vital.")
        rows = self.conn.execute(
            """
            SELECT * FROM logs
             WHERE kind = ? AND event_date BETWEEN ? AND ?
             ORDER BY event_date, id
            """,
            (kind, start_day.strftime(config.DATE_FMT), end_day.strftime(config.DATE_FMT)),
        ).fetchall()
        return [self._row_to_log(row) for row in rows]

    def list_logs_for_day(self, kind: str, day: date) -> list[LogEntry]:
        return self.list_logs(kind, day, day)

    def get_log(self, log_id: int) -> LogEntry | None:
        row = self.conn.execute("SELECT * FROM logs WHERE id = ?", (log_id,)).fetchone()
        return self._row_to_log(row) if row else None

    def list_saved_weeks(self) -> list[date]:
        week_starts: set[date] = set()
        for row in self.conn.execute("SELECT start_ts, end_ts FROM shifts").fetchall():
            start = parse_dt(row["start_ts"]).date()
            end = parse_dt(row["end_ts"]).date() if row["end_ts"] else start
            current = week_start_for(start)
            final = week_start_for(end)
            while current <= final:
                week_starts.add(current)
                current += timedelta(days=7)
        for row in self.conn.execute("SELECT event_date FROM logs").fetchall():
            event_date = datetime.strptime(row["event_date"], config.DATE_FMT).date()
            week_starts.add(week_start_for(event_date))
        current_week = week_start_for(date.today())
        for offset in range(12):
            week_starts.add(current_week - timedelta(days=offset * 7))
        return sorted(week_starts, reverse=True)

    @staticmethod
    def _row_to_shift(row: sqlite3.Row) -> Shift:
        return Shift(
            id=row["id"],
            start=parse_dt(row["start_ts"]),
            end=parse_dt(row["end_ts"]) if row["end_ts"] else None,
        )

    @staticmethod
    def _row_to_log(row: sqlite3.Row) -> LogEntry:
        return LogEntry(
            id=row["id"],
            event_date=datetime.strptime(row["event_date"], config.DATE_FMT).date(),
            kind=row["kind"],
            postal=row["postal"],
            event_type=row["event_type"],
            responders=row["responders"],
            details=row["details"],
            image_path=row["image_path"],
            created_at=parse_dt(row["created_at"]),
        )


