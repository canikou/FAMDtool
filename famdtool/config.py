from pathlib import Path

BASE_DIR = Path(__file__).resolve().parent.parent
APP_TITLE = "FAMD Tool ni Yeol"
DB_PATH = BASE_DIR / "famd_data.sqlite3"
EXPORT_DIR = BASE_DIR / "exports"
ATTACH_DIR = BASE_DIR / "attachments"
LOG_DIR = BASE_DIR / "logs"
DATE_FMT = "%Y-%m-%d"
DT_FMT = "%Y-%m-%d %H:%M:%S"
DEFAULT_RESPONDERS = "Yeol Bakunawa"

RESPONSE_TYPES = ("ROBBERY", "DISTRESS", "HEIST")
VITAL_TYPES = ("TREATMENT", "BODYBAG", "REVIVAL")
LOG_KINDS = {"response", "vital"}
