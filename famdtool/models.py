from __future__ import annotations

from dataclasses import dataclass
from datetime import date, datetime


@dataclass
class Shift:
    id: int
    start: datetime
    end: datetime | None


@dataclass
class LogEntry:
    id: int
    event_date: date
    kind: str
    postal: str
    event_type: str
    responders: str
    details: str
    image_path: str
    created_at: datetime
