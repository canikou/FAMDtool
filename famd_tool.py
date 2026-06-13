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
    APP_VERSION,
    ATTACH_DIR,
    CONFIG_PATH,
    DATE_FMT,
    DB_PATH,
    DEFAULT_RESPONDERS,
    DT_FMT,
    EXPORT_DIR,
    ICON_PATH,
    LOG_DIR,
    LOG_KINDS,
    NON_DETAILED_LOGS,
    RESPONSE_TYPES,
    UPDATE_ASSET_PATTERN,
    UPDATE_CHECK_ON_STARTUP,
    UPDATE_LATEST_API_URL,
    UPDATE_REPO,
    UPDATE_SILENT_INSTALL,
    UPDATE_INSTALLER_ARGS,
    UPDATES_ENABLED,
    VERBOSE_EVENT_LOGS,
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
from famdtool.updater import (
    UpdateInfo,
    check_for_update,
    download_update,
    is_newer_version,
    run_installer,
    select_update_asset,
    version_tuple,
)
from famdtool.windowing import main_window_for, place_window_near_main


if __name__ == "__main__":
    main()
