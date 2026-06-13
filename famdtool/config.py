from __future__ import annotations

import configparser
import sys
from pathlib import Path


def app_base_dir() -> Path:
    if getattr(sys, "frozen", False):
        return Path(sys.executable).resolve().parent
    return Path(__file__).resolve().parent.parent


BASE_DIR = app_base_dir()
CONFIG_PATH = BASE_DIR / "config.cfg"

_DEFAULT_CONFIG = {
    "app": {
        "title": "FAMD Tool ni Yeol",
        "version": "1.5.1",
        "default_responders": "Yeol Bakunawa",
    },
    "paths": {
        "database": "famd_data.sqlite3",
        "exports": "exports",
        "attachments": "attachments",
        "logs": "logs",
        "icon": "assets/FAMDTool.ico",
    },
    "logging": {
        "verbose_event_logs": "true",
    },
    "workflow": {
        "non_detailed_logs": "true",
    },
    "updates": {
        "enabled": "true",
        "check_on_startup": "true",
        "repo": "canikou/FAMDtool",
        "latest_api_url": "https://api.github.com/repos/canikou/FAMDtool/releases/latest",
        "asset_pattern": "FAMDTool-v{version}-windows-setup.exe",
        "silent_install": "true",
        "installer_args": "/SILENT /NORESTART /CLOSEAPPLICATIONS",
    },
    "types": {
        "response": "ROBBERY,DISTRESS,HEIST",
        "vital": "TREATMENT,BODYBAG,REVIVAL",
    },
}


def ensure_config_file() -> None:
    if CONFIG_PATH.exists():
        return
    parser = configparser.ConfigParser()
    parser.read_dict(_DEFAULT_CONFIG)
    with CONFIG_PATH.open("w", encoding="utf-8") as handle:
        parser.write(handle)


def load_config() -> configparser.ConfigParser:
    ensure_config_file()
    parser = configparser.ConfigParser()
    parser.read_dict(_DEFAULT_CONFIG)
    parser.read(CONFIG_PATH, encoding="utf-8")
    return parser


def path_from_config(value: str) -> Path:
    path = Path(value).expanduser()
    return path if path.is_absolute() else BASE_DIR / path


def tuple_from_csv(value: str) -> tuple[str, ...]:
    result = tuple(item.strip().upper() for item in value.split(",") if item.strip())
    return result or ("UNKNOWN",)


APP_CONFIG = load_config()

APP_TITLE = APP_CONFIG.get("app", "title")
APP_VERSION = APP_CONFIG.get("app", "version")
DEFAULT_RESPONDERS = APP_CONFIG.get("app", "default_responders")

DB_PATH = path_from_config(APP_CONFIG.get("paths", "database"))
EXPORT_DIR = path_from_config(APP_CONFIG.get("paths", "exports"))
ATTACH_DIR = path_from_config(APP_CONFIG.get("paths", "attachments"))
LOG_DIR = path_from_config(APP_CONFIG.get("paths", "logs"))
ICON_PATH = path_from_config(APP_CONFIG.get("paths", "icon"))

VERBOSE_EVENT_LOGS = APP_CONFIG.getboolean("logging", "verbose_event_logs")
NON_DETAILED_LOGS = APP_CONFIG.getboolean("workflow", "non_detailed_logs")

UPDATES_ENABLED = APP_CONFIG.getboolean("updates", "enabled")
UPDATE_CHECK_ON_STARTUP = APP_CONFIG.getboolean("updates", "check_on_startup")
UPDATE_REPO = APP_CONFIG.get("updates", "repo")
UPDATE_LATEST_API_URL = APP_CONFIG.get("updates", "latest_api_url")
UPDATE_ASSET_PATTERN = APP_CONFIG.get("updates", "asset_pattern")
UPDATE_SILENT_INSTALL = APP_CONFIG.getboolean("updates", "silent_install")
UPDATE_INSTALLER_ARGS = tuple(
    item for item in APP_CONFIG.get("updates", "installer_args").split() if item
)

RESPONSE_TYPES = tuple_from_csv(APP_CONFIG.get("types", "response"))
VITAL_TYPES = tuple_from_csv(APP_CONFIG.get("types", "vital"))

DATE_FMT = "%Y-%m-%d"
DT_FMT = "%Y-%m-%d %H:%M:%S"
LOG_KINDS = {"response", "vital"}
