from __future__ import annotations

import atexit
import json
import os
import queue
import sys
import threading
from datetime import datetime
from pathlib import Path
from typing import Any

from . import config

_QUEUE: queue.Queue[dict[str, Any] | None] = queue.Queue()
_THREAD: threading.Thread | None = None
_LOCK = threading.Lock()
_SHUTTING_DOWN = False
_DEFAULT_LOG_DIR = config.LOG_DIR


def log_event(event: str, **data: Any) -> None:
    """Queue an app event for async logging without raising into callers."""
    if _SHUTTING_DOWN or not _logging_enabled():
        return
    try:
        _ensure_thread()
        _QUEUE.put_nowait(
            {
                "timestamp": datetime.now().isoformat(timespec="seconds"),
                "event": event,
                "data": data,
                "process_id": os.getpid(),
                "source_thread": threading.current_thread().name,
            }
        )
    except Exception:
        pass


def flush_logs(timeout: float = 2.0) -> bool:
    """Wait briefly until queued log records have been written."""
    if _THREAD is None:
        return True
    if not _THREAD.is_alive():
        if _SHUTTING_DOWN:
            return True
        _ensure_thread()
    marker = threading.Event()
    try:
        _QUEUE.put_nowait({"flush_marker": marker})
    except Exception:
        return False
    return marker.wait(timeout)


def shutdown_logger(timeout: float = 2.0) -> None:
    global _SHUTTING_DOWN
    _SHUTTING_DOWN = True
    if _THREAD is None:
        return
    try:
        _QUEUE.put_nowait(None)
        _THREAD.join(timeout)
    except Exception:
        pass


def _ensure_thread() -> None:
    global _THREAD
    with _LOCK:
        if _THREAD is not None and _THREAD.is_alive():
            return
        _THREAD = threading.Thread(
            target=_writer_loop,
            name="famd-event-log-writer",
            daemon=True,
        )
        _THREAD.start()


def _logging_enabled() -> bool:
    if os.environ.get("FAMD_DISABLE_EVENT_LOGS") == "1":
        return False
    if _running_under_unittest() and _same_path(config.LOG_DIR, _DEFAULT_LOG_DIR):
        return False
    return True


def _running_under_unittest() -> bool:
    return any("unittest" in value for value in sys.argv[:2])


def _same_path(left: Path, right: Path) -> bool:
    try:
        return left.resolve() == right.resolve()
    except OSError:
        return left == right


def _writer_loop() -> None:
    while True:
        item = _QUEUE.get()
        try:
            if item is None:
                return
            marker = item.get("flush_marker")
            if isinstance(marker, threading.Event):
                marker.set()
                continue
            _write_record(item)
        except Exception:
            pass
        finally:
            _QUEUE.task_done()


def _write_record(record: dict[str, Any]) -> None:
    config.LOG_DIR.mkdir(parents=True, exist_ok=True)
    timestamp = _record_timestamp(record)
    log_path = config.LOG_DIR / f"famd_tool_{timestamp:%Y-%m-%d}.log"
    line = json.dumps(record, ensure_ascii=False, default=_json_default, sort_keys=True)
    with log_path.open("a", encoding="utf-8") as handle:
        handle.write(f"{line}\n")


def _record_timestamp(record: dict[str, Any]) -> datetime:
    value = record.get("timestamp")
    if isinstance(value, str):
        try:
            return datetime.fromisoformat(value)
        except ValueError:
            pass
    return datetime.now()


def _json_default(value: Any) -> str:
    if isinstance(value, Path):
        return str(value)
    if isinstance(value, datetime):
        return value.isoformat(timespec="seconds")
    return str(value)


atexit.register(flush_logs)
