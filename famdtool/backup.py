from __future__ import annotations

import shutil
import sqlite3
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from tempfile import TemporaryDirectory
from zipfile import ZIP_DEFLATED, BadZipFile, ZipFile

from . import config
from .event_log import log_event

MANIFEST_NAME = "manifest.txt"
DATABASE_NAME = "famd_data.sqlite3"
CONFIG_NAME = "config.cfg"


@dataclass(frozen=True)
class BackupExport:
    path: Path
    database_bytes: int
    config_bytes: int


def _timestamp() -> str:
    return datetime.now().strftime("%Y%m%d_%H%M%S_%f")


def export_app_backup(
    database_path: Path = config.DB_PATH,
    config_path: Path = config.CONFIG_PATH,
    export_dir: Path = config.EXPORT_DIR,
) -> BackupExport:
    if not database_path.exists():
        raise FileNotFoundError(f"Database file not found: {database_path}")
    if not config_path.exists():
        raise FileNotFoundError(f"Config file not found: {config_path}")

    export_dir.mkdir(parents=True, exist_ok=True)
    backup_path = export_dir / f"FAMD_Backup_{_timestamp()}.zip"
    with TemporaryDirectory() as temp_dir:
        temp_db = Path(temp_dir) / DATABASE_NAME
        _copy_sqlite_database(database_path, temp_db)
        with ZipFile(backup_path, "w", ZIP_DEFLATED) as archive:
            archive.write(temp_db, DATABASE_NAME)
            archive.write(config_path, CONFIG_NAME)
            archive.writestr(
                MANIFEST_NAME,
                "\n".join(
                    [
                        "FAMD Tool ni Yeol backup",
                        f"created_at={datetime.now().isoformat(timespec='seconds')}",
                        f"app_version={config.APP_VERSION}",
                    ]
                )
                + "\n",
            )

    result = BackupExport(
        path=backup_path,
        database_bytes=database_path.stat().st_size,
        config_bytes=config_path.stat().st_size,
    )
    log_event(
        "backup_exported",
        path=str(result.path),
        database_bytes=result.database_bytes,
        config_bytes=result.config_bytes,
    )
    return result


def _copy_sqlite_database(source: Path, target: Path) -> None:
    target.parent.mkdir(parents=True, exist_ok=True)
    source_conn = sqlite3.connect(source)
    try:
        target_conn = sqlite3.connect(target)
        try:
            source_conn.backup(target_conn)
        finally:
            target_conn.close()
    finally:
        source_conn.close()


def validate_backup_archive(archive_path: Path) -> None:
    if not archive_path.exists():
        raise FileNotFoundError(f"Backup file not found: {archive_path}")
    try:
        with ZipFile(archive_path, "r") as archive:
            names = set(archive.namelist())
            missing = {DATABASE_NAME, CONFIG_NAME} - names
            if missing:
                raise ValueError(
                    "Backup is missing required file(s): " + ", ".join(sorted(missing))
                )
            if archive.getinfo(DATABASE_NAME).file_size <= 0:
                raise ValueError("Backup database is empty.")
    except BadZipFile as exc:
        raise ValueError("Selected file is not a valid FAMD backup zip.") from exc


def import_app_backup(
    archive_path: Path,
    database_path: Path = config.DB_PATH,
    config_path: Path = config.CONFIG_PATH,
) -> Path:
    validate_backup_archive(archive_path)
    restore_backup_path = database_path.with_name(f"{database_path.stem}_pre_import_{_timestamp()}.sqlite3")
    with TemporaryDirectory() as temp_dir:
        temp_root = Path(temp_dir)
        with ZipFile(archive_path, "r") as archive:
            archive.extract(DATABASE_NAME, temp_root)
            archive.extract(CONFIG_NAME, temp_root)
        imported_db = temp_root / DATABASE_NAME
        imported_config = temp_root / CONFIG_NAME

        _validate_sqlite_database(imported_db)
        database_path.parent.mkdir(parents=True, exist_ok=True)
        config_path.parent.mkdir(parents=True, exist_ok=True)
        if database_path.exists():
            shutil.copy2(database_path, restore_backup_path)
        shutil.copy2(imported_db, database_path)
        shutil.copy2(imported_config, config_path)

    log_event(
        "backup_imported",
        archive_path=str(archive_path),
        database_path=str(database_path),
        config_path=str(config_path),
        restore_backup_path=str(restore_backup_path) if restore_backup_path.exists() else "",
    )
    return restore_backup_path


def _validate_sqlite_database(path: Path) -> None:
    conn = sqlite3.connect(path)
    try:
        result = conn.execute("PRAGMA integrity_check").fetchone()
        if not result or result[0] != "ok":
            raise ValueError("Imported database failed SQLite integrity check.")
        tables = {
            row[0]
            for row in conn.execute(
                "SELECT name FROM sqlite_master WHERE type = 'table'"
            ).fetchall()
        }
        missing = {"shifts", "logs", "settings"} - tables
        if missing:
            raise ValueError(
                "Imported database is missing required table(s): " + ", ".join(sorted(missing))
            )
    finally:
        conn.close()
