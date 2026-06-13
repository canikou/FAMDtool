from famdtool.app import (
    FamdToolApp,
    HistoryWindow,
    LogDetailWindow,
    LogDialog,
    LogManager,
    ShiftDialog,
    ShiftManager,
    TimeInputFrame,
    main,
)
from famdtool.attachments import (
    Image,
    build_discord_card_image,
    build_individual_log_text,
    copy_image_to_attachments,
    copy_images_to_attachments,
    copy_text_and_image_to_clipboard,
    first_image_path,
    parse_image_paths,
    save_clipboard_image_to_file,
    serialize_image_paths,
    set_windows_image_clipboard,
    set_windows_clipboard,
)
from famdtool.config import (
    APP_TITLE,
    ATTACH_DIR,
    DATE_FMT,
    DB_PATH,
    DEFAULT_RESPONDERS,
    DT_FMT,
    EXPORT_DIR,
    LOG_DIR,
    LOG_KINDS,
    RESPONSE_TYPES,
    VITAL_TYPES,
)
from famdtool.database import FamdDatabase
from famdtool.event_log import flush_logs, log_event, shutdown_logger
from famdtool.image_preview import load_thumbnail
from famdtool.models import LogEntry, Shift
from famdtool.reports import (
    build_weekly_export_text,
    display_shifts_for_day,
    total_minutes,
)
from famdtool.tasks import run_background
from famdtool.time_utils import (
    format_day,
    format_db_dt,
    format_hours,
    format_log_timestamp,
    format_short_date,
    format_time,
    local_now,
    minute_after_scroll,
    minutes_between,
    parse_dt,
    parse_user_datetime,
    split_shift_for_view,
    split_shift_segments,
    week_start_for,
)
from famdtool.windowing import main_window_for, place_window_near_main


if __name__ == "__main__":
    main()
