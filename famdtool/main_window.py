from __future__ import annotations

from datetime import date, timedelta
from pathlib import Path
import tkinter as tk
from tkinter import filedialog, messagebox, ttk

from .attachments import parse_image_paths
from .backup import export_app_backup, import_app_backup
from .config import (
    APP_TITLE,
    CONFIG_PATH,
    DATE_FMT,
    DB_PATH,
    DEFAULT_RESPONDERS,
    EXPORT_DIR,
    ICON_PATH,
    NON_DETAILED_LOGS,
    UPDATE_CHECK_ON_STARTUP,
    UPDATES_ENABLED,
    RESPONSE_TYPES,
    VITAL_TYPES,
)
from .database import FamdDatabase
from .dialogs import LogDialog
from .event_log import flush_logs, log_event
from .managers import HistoryWindow, LogDetailWindow, LogManager, ShiftManager
from .models import LogEntry, Shift
from .reports import (
    build_weekly_export_text,
    display_shifts_for_day as report_display_shifts_for_day,
    total_minutes as report_total_minutes,
)
from .tasks import run_background
from .time_utils import (
    format_hours,
    format_short_date,
    format_time,
    local_now,
    minutes_between,
    week_start_for,
)
from .updater import UpdateInfo, check_for_update, download_update, run_installer


class FamdToolApp(tk.Tk):
    def __init__(self) -> None:
        super().__init__()
        self.title(APP_TITLE)
        self.set_window_icon()
        self.geometry("940x760")
        self.minsize(780, 640)

        self.db = FamdDatabase(DB_PATH)
        today = date.today()
        self.week_start = week_start_for(today)
        self.selected_day = today
        self.responder_name_var = tk.StringVar(
            value=self.db.get_setting("responder_name", DEFAULT_RESPONDERS)
        )
        self.refresh_job: str | None = None
        self.old_week_edit_confirmed = False
        self._build_style()
        self._build_ui()
        self.protocol("WM_DELETE_WINDOW", self.on_close)
        self.refresh()
        log_event(
            "app_started",
            database=str(DB_PATH),
            week_start=self.week_start.strftime(DATE_FMT),
            selected_day=self.selected_day.strftime(DATE_FMT),
        )
        if UPDATES_ENABLED and UPDATE_CHECK_ON_STARTUP:
            self.after(1500, self.start_update_check)

    def set_window_icon(self) -> None:
        if not ICON_PATH.exists():
            return
        try:
            self.iconbitmap(str(ICON_PATH))
        except tk.TclError:
            pass

    def start_update_check(self) -> None:
        log_event("update_check_started")
        run_background(self, check_for_update, self.finish_update_check, self.fail_update_check)

    def finish_update_check(self, update: UpdateInfo | None) -> None:
        if update is None:
            log_event("update_check_finished", update_available=False)
            return
        log_event(
            "update_check_finished",
            update_available=True,
            version=update.version,
            asset_name=update.asset_name,
        )
        should_install = messagebox.askyesno(
            "Update available",
            (
                f"FAMD Tool {update.version} is available.\n\n"
                "Download and install it now? The app will close after starting the installer."
            ),
            parent=self,
        )
        if should_install:
            self.configure(cursor="watch")
            run_background(
                self,
                lambda: self.download_and_run_update(update),
                self.finish_update_install,
                self.fail_update_install,
            )

    def fail_update_check(self, exc: Exception) -> None:
        log_event("update_check_failed", error=str(exc))

    def download_and_run_update(self, update: UpdateInfo) -> str:
        installer_path = download_update(update)
        run_installer(installer_path)
        return str(installer_path)

    def finish_update_install(self, installer_path: str) -> None:
        self.configure(cursor="")
        log_event("update_installer_started", path=installer_path)
        self.on_close()

    def fail_update_install(self, exc: Exception) -> None:
        self.configure(cursor="")
        log_event("update_install_failed", error=str(exc))
        messagebox.showerror("Update failed", str(exc), parent=self)

    def _build_style(self) -> None:
        style = ttk.Style(self)
        style.theme_use("clam")
        style.configure("Title.TLabel", font=("Segoe UI", 20, "bold"))
        style.configure("Section.TLabel", font=("Segoe UI", 11, "bold"))
        style.configure("StatusOn.TLabel", foreground="#0a7a35", font=("Segoe UI", 11, "bold"))
        style.configure("StatusOff.TLabel", foreground="#9b1c1c", font=("Segoe UI", 11, "bold"))
        style.configure("StatusOld.TLabel", foreground="#8a5a00", font=("Segoe UI", 11, "bold"))
        style.configure("Primary.TButton", font=("Segoe UI", 10, "bold"))
        style.configure("CounterNumber.TEntry", font=("Segoe UI", 18, "bold"), justify="center")
        style.configure("Selected.TButton", background="#3f5f8f", foreground="white")
        style.map(
            "Selected.TButton",
            background=[("active", "#344f78"), ("pressed", "#2d4569")],
            foreground=[("active", "white"), ("pressed", "white")],
        )

    def _build_ui(self) -> None:
        self.columnconfigure(0, weight=1)
        self.rowconfigure(4, weight=1)

        header = ttk.Frame(self, padding=(18, 14, 18, 8))
        header.grid(row=0, column=0, sticky="ew")
        header.columnconfigure(0, weight=1)
        ttk.Label(header, text=APP_TITLE, style="Title.TLabel").grid(row=0, column=0, sticky="w")
        name_frame = ttk.Frame(header)
        name_frame.grid(row=0, column=1, sticky="e", padx=(8, 12))
        ttk.Label(name_frame, text="Name").pack(side="left", padx=(0, 4))
        name_entry = ttk.Entry(name_frame, textvariable=self.responder_name_var, width=26)
        name_entry.pack(side="left")
        name_entry.bind("<FocusOut>", lambda _event: self.save_responder_name())
        name_entry.bind("<Return>", lambda _event: self.save_responder_name())
        ttk.Button(header, text="History", command=self.open_history).grid(
            row=0, column=2, sticky="e", padx=(0, 10)
        )
        self.status_label = ttk.Label(header, text="Off Duty", style="StatusOff.TLabel")
        self.status_label.grid(row=0, column=3, sticky="e")

        totals = ttk.Frame(self, padding=(18, 4, 18, 10))
        totals.grid(row=1, column=0, sticky="ew")
        totals.columnconfigure((0, 1), weight=1)
        self.weekly_var = tk.StringVar()
        self.daily_var = tk.StringVar()
        ttk.Label(totals, textvariable=self.weekly_var, justify="left").grid(
            row=0, column=0, sticky="w"
        )
        ttk.Label(totals, textvariable=self.daily_var, justify="left").grid(
            row=0, column=1, sticky="w"
        )

        day_bar = ttk.Frame(self, padding=(18, 4, 18, 10))
        day_bar.grid(row=2, column=0, sticky="ew")
        day_bar.columnconfigure(1, weight=1)
        ttk.Button(day_bar, text="<<", width=5, command=self.previous_day).grid(
            row=0, column=0, sticky="w"
        )
        self.day_label = ttk.Label(day_bar, text="", anchor="center", font=("Segoe UI", 14, "bold"))
        self.day_label.grid(row=0, column=1, sticky="ew")
        ttk.Button(day_bar, text=">>", width=5, command=self.next_day).grid(
            row=0, column=2, sticky="e"
        )

        lists = ttk.Frame(self, padding=(18, 0, 18, 8))
        lists.grid(row=4, column=0, sticky="nsew")
        lists.columnconfigure(0, weight=1)

        self.shift_list = self._build_list_section(
            lists, 0, "SAVED SHIFTS", "Edit Shifts", self.open_shift_manager
        )
        self.shift_list.bind("<Double-1>", lambda _event: self.open_shift_manager())
        if NON_DETAILED_LOGS:
            lists.rowconfigure(1, weight=1)
            lists.rowconfigure(2, weight=0)
            self._build_simple_counter_panel(lists, 2)
        else:
            lists.rowconfigure((1, 3, 5), weight=1)
            self.response_list = self._build_list_section(
                lists, 2, "ROBBERY/DISTRESS RESPONSES", "Edit Responses", self.open_response_manager
            )
            self.response_list.bind("<Double-1>", lambda _event: self.open_main_log_detail("response"))
            self.vital_list = self._build_list_section(
                lists, 4, "VITALS LOGS", "Edit Vitals", self.open_vital_manager
            )
            self.vital_list.bind("<Double-1>", lambda _event: self.open_main_log_detail("vital"))

        actions = ttk.Frame(self, padding=(18, 6, 18, 16))
        actions.grid(row=5, column=0, sticky="ew")
        column_count = 2 if NON_DETAILED_LOGS else 4
        actions.columnconfigure(tuple(range(column_count)), weight=1)
        self.time_button = ttk.Button(
            actions, text="TIME IN", style="Primary.TButton", command=self.toggle_shift
        )
        self.time_button.grid(row=0, column=0, padx=4, sticky="ew")
        if NON_DETAILED_LOGS:
            ttk.Button(actions, text="EXPORT", command=self.export_week).grid(
                row=0, column=1, padx=4, sticky="ew"
            )
        else:
            ttk.Button(actions, text="ADD ROBBERY", command=self.add_response).grid(
                row=0, column=1, padx=4, sticky="ew"
            )
            ttk.Button(actions, text="ADD VITALS", command=self.add_vital).grid(
                row=0, column=2, padx=4, sticky="ew"
            )
            ttk.Button(actions, text="EXPORT", command=self.export_week).grid(
                row=0, column=3, padx=4, sticky="ew"
            )

    def _build_list_section(
        self, parent: ttk.Frame, row: int, label: str, button_text: str, command
    ) -> tk.Listbox:
        heading = ttk.Frame(parent)
        heading.grid(row=row, column=0, sticky="ew", pady=(8, 3))
        heading.columnconfigure(0, weight=1)
        ttk.Label(heading, text=label, style="Section.TLabel").grid(row=0, column=0, sticky="w")
        ttk.Button(heading, text=button_text, command=command).grid(row=0, column=1, sticky="e")

        box_frame = ttk.Frame(parent)
        box_frame.grid(row=row + 1, column=0, sticky="nsew")
        box_frame.columnconfigure(0, weight=1)
        box_frame.rowconfigure(0, weight=1)
        listbox = tk.Listbox(box_frame, height=5, activestyle="none")
        listbox.grid(row=0, column=0, sticky="nsew")
        scrollbar = ttk.Scrollbar(box_frame, orient="vertical", command=listbox.yview)
        scrollbar.grid(row=0, column=1, sticky="ns")
        listbox.configure(yscrollcommand=scrollbar.set)
        return listbox

    def _build_simple_counter_panel(self, parent: ttk.Frame, row: int) -> None:
        panel = ttk.Frame(parent, padding=(0, 16, 0, 8))
        panel.grid(row=row, column=0, sticky="nsew")
        panel.columnconfigure((0, 1), weight=1)
        self.response_count_var = tk.StringVar(value="0")
        self.vital_count_var = tk.StringVar(value="0")
        self._build_counter_group(panel, 0, "RESPONSES", "response", self.response_count_var)
        self._build_counter_group(panel, 1, "VITALS", "vital", self.vital_count_var)

    def _build_counter_group(
        self, parent: ttk.Frame, column: int, label: str, kind: str, variable: tk.StringVar
    ) -> None:
        group = ttk.Frame(parent, padding=10)
        group.grid(row=0, column=column, sticky="nsew", padx=8)
        group.columnconfigure(1, weight=1)
        ttk.Label(group, text=label, style="Section.TLabel", anchor="center").grid(
            row=0, column=0, columnspan=3, sticky="ew", pady=(0, 8)
        )
        ttk.Button(group, text="<<", width=5, command=lambda: self.adjust_simple_log(kind, -1)).grid(
            row=1, column=0, sticky="e", padx=(0, 8)
        )
        count_entry = ttk.Entry(
            group,
            textvariable=variable,
            style="CounterNumber.TEntry",
            justify="center",
            width=8,
        )
        count_entry.grid(row=1, column=1, sticky="ew")
        count_entry.bind("<Return>", lambda _event: self.commit_simple_log_count(kind, variable))
        count_entry.bind("<FocusOut>", lambda _event: self.commit_simple_log_count(kind, variable))
        ttk.Button(group, text=">>", width=5, command=lambda: self.adjust_simple_log(kind, 1)).grid(
            row=1, column=2, sticky="w", padx=(8, 0)
        )

    def previous_day(self) -> None:
        index = (self.selected_day - self.week_start).days
        self.selected_day = self.week_start + timedelta(days=(index - 1) % 7)
        log_event(
            "day_selected",
            direction="previous",
            selected_day=self.selected_day.strftime(DATE_FMT),
            week_start=self.week_start.strftime(DATE_FMT),
        )
        self.refresh()

    def next_day(self) -> None:
        index = (self.selected_day - self.week_start).days
        self.selected_day = self.week_start + timedelta(days=(index + 1) % 7)
        log_event(
            "day_selected",
            direction="next",
            selected_day=self.selected_day.strftime(DATE_FMT),
            week_start=self.week_start.strftime(DATE_FMT),
        )
        self.refresh()

    def refresh(self) -> None:
        if self.refresh_job:
            self.after_cancel(self.refresh_job)
            self.refresh_job = None

        active = self.db.get_active_shift()
        is_on_duty = active is not None
        if self.is_viewing_old_week():
            self.status_label.configure(text="VIEWING OLD LOGS", style="StatusOld.TLabel")
        else:
            self.status_label.configure(
                text="On Duty" if is_on_duty else "Off Duty",
                style="StatusOn.TLabel" if is_on_duty else "StatusOff.TLabel",
            )
        self.time_button.configure(text="TIME OUT" if is_on_duty else "TIME IN")

        week_end = self.week_start + timedelta(days=6)
        weekly_minutes = self.total_minutes(self.week_start, week_end)
        weekly_responses = len(self.db.list_logs("response", self.week_start, week_end))
        weekly_vitals = len(self.db.list_logs("vital", self.week_start, week_end))
        self.weekly_var.set(
            "WEEKLY TOTAL:\n"
            f"  Duty Hours: {format_hours(weekly_minutes)} on Duty\n"
            f"  Responses: {weekly_responses} Responses\n"
            f"  Vitals: {weekly_vitals} Logs"
        )

        daily_minutes = self.total_minutes(self.selected_day, self.selected_day)
        daily_responses = len(self.db.list_logs_for_day("response", self.selected_day))
        daily_vitals = len(self.db.list_logs_for_day("vital", self.selected_day))
        self.daily_var.set(
            "DAILY TOTAL:\n"
            f"  Duty Hours: {format_hours(daily_minutes)} on Duty\n"
            f"  Responses: {daily_responses} Responses\n"
            f"  Vitals: {daily_vitals} Logs"
        )

        day_number = (self.selected_day - self.week_start).days + 1
        self.day_label.configure(
            text=f"Day {day_number} - {self.selected_day.strftime('%A')}     {format_short_date(self.selected_day)}"
        )
        self.populate_lists()
        self.refresh_job = self.after(30_000, self.refresh)

    def populate_lists(self) -> None:
        self.shift_list.delete(0, "end")
        for shift in self.display_shifts_for_day(self.selected_day):
            end_text = format_time(shift.end) if shift.end else "On Duty"
            duration_end = shift.end if shift.end else local_now()
            self.shift_list.insert(
                "end",
                f"- {format_time(shift.start)} - {end_text} (TOTAL: {format_hours(minutes_between(shift.start, duration_end))})",
            )
        if self.shift_list.size() == 0:
            self.shift_list.insert("end", "- No saved shifts")

        self.response_entries = self.db.list_logs_for_day("response", self.selected_day)
        self.vital_entries = self.db.list_logs_for_day("vital", self.selected_day)
        if NON_DETAILED_LOGS:
            self.response_count_var.set(str(len(self.response_entries)))
            self.vital_count_var.set(str(len(self.vital_entries)))
            return

        self.response_list.delete(0, "end")
        for entry in self.response_entries:
            self.response_list.insert("end", self.log_display_text(entry))
        if self.response_list.size() == 0:
            self.response_list.insert("end", "- No responses")

        self.vital_list.delete(0, "end")
        for entry in self.vital_entries:
            self.vital_list.insert("end", self.log_display_text(entry))
        if self.vital_list.size() == 0:
            self.vital_list.insert("end", "- No vitals")

    def display_shifts_for_day(self, day: date) -> list[Shift]:
        return report_display_shifts_for_day(self.db, day)

    def total_minutes(self, start_day: date, end_day: date) -> int:
        return report_total_minutes(self.db, start_day, end_day)

    def toggle_shift(self) -> None:
        if self.is_viewing_old_week():
            messagebox.showinfo(
                "Viewing old logs",
                "Time In/Out is only available on the current week. Open the current week to clock in or out.",
                parent=self,
            )
            return
        active = self.db.get_active_shift()
        now = local_now()
        log_event(
            "time_toggle_clicked",
            active_shift_id=active.id if active else None,
            timestamp=now.strftime("%Y-%m-%d %H:%M:%S"),
        )
        try:
            if active:
                self.db.close_shift(active.id, active.start, now)
                messagebox.showinfo("Time out", f"Clocked out at {format_time(now)}.", parent=self)
            else:
                self.db.start_shift(now)
                messagebox.showinfo("Time in", f"Clocked in at {format_time(now)}.", parent=self)
        except ValueError as exc:
            log_event("time_toggle_failed", error=str(exc))
            messagebox.showerror("Shift error", str(exc), parent=self)
        self.selected_day = now.date()
        self.week_start = week_start_for(self.selected_day)
        self.refresh()

    def add_response(self) -> None:
        if NON_DETAILED_LOGS:
            self.adjust_simple_log("response", 1)
            return
        self.open_log_dialog("response", RESPONSE_TYPES, "Add Response")

    def add_vital(self) -> None:
        if NON_DETAILED_LOGS:
            self.adjust_simple_log("vital", 1)
            return
        self.open_log_dialog("vital", VITAL_TYPES, "Add Vitals")

    def adjust_simple_log(self, kind: str, delta: int) -> None:
        if not self.confirm_editing_selected_history():
            return
        try:
            if delta > 0:
                self.db.add_blank_log(kind, self.selected_day, self.get_responder_name())
            else:
                self.db.delete_latest_log_for_day(kind, self.selected_day)
            new_count = len(self.db.list_logs_for_day(kind, self.selected_day))
        except ValueError as exc:
            messagebox.showerror("Counter error", str(exc), parent=self)
            return
        log_event(
            "simple_log_counter_button_clicked",
            kind=kind,
            selected_day=self.selected_day.strftime(DATE_FMT),
            delta=delta,
            new_count=new_count,
        )
        self.refresh()

    def commit_simple_log_count(self, kind: str, variable: tk.StringVar) -> str:
        current = len(self.db.list_logs_for_day(kind, self.selected_day))
        raw_value = variable.get().strip()
        if not raw_value:
            variable.set(str(current))
            return "break"
        try:
            value = int(raw_value)
        except ValueError:
            variable.set(str(current))
            messagebox.showerror("Counter error", "Use a whole number for the counter.", parent=self)
            return "break"
        if value < 0:
            variable.set(str(current))
            messagebox.showerror("Counter error", "Counter cannot be lower than zero.", parent=self)
            return "break"
        if value == current:
            variable.set(str(current))
            return "break"
        if not self.confirm_editing_selected_history():
            variable.set(str(current))
            return "break"
        try:
            if value > current:
                for _ in range(value - current):
                    self.db.add_blank_log(kind, self.selected_day, self.get_responder_name())
            else:
                for _ in range(current - value):
                    self.db.delete_latest_log_for_day(kind, self.selected_day)
        except ValueError as exc:
            messagebox.showerror("Counter error", str(exc), parent=self)
            variable.set(str(current))
            return "break"
        log_event(
            "simple_log_counter_set",
            kind=kind,
            selected_day=self.selected_day.strftime(DATE_FMT),
            old_count=current,
            new_count=value,
        )
        self.refresh()
        return "break"

    def open_log_dialog(self, kind: str, options: tuple[str, ...], title: str) -> None:
        if not self.confirm_editing_selected_history():
            return
        log_event(
            "log_dialog_requested",
            kind=kind,
            selected_day=self.selected_day.strftime(DATE_FMT),
            title=title,
        )
        dialog = LogDialog(
            self,
            title,
            self.selected_day,
            options,
            default_responders=self.get_responder_name(),
        )
        if dialog.result_data:
            self.db.add_log(kind, *dialog.result_data)
            self.refresh()

    def open_shift_manager(self) -> None:
        log_event("window_opened", window="shift_manager", selected_day=self.selected_day.strftime(DATE_FMT))
        ShiftManager(self, self.db, self.selected_day, self.refresh)

    def get_responder_name(self) -> str:
        return self.responder_name_var.get().strip() or DEFAULT_RESPONDERS

    def save_responder_name(self) -> str:
        self.db.set_setting("responder_name", self.get_responder_name())
        return "break"

    def is_viewing_old_week(self) -> bool:
        return self.week_start != week_start_for(date.today())

    def confirm_editing_selected_history(self) -> bool:
        if not self.is_viewing_old_week() or self.old_week_edit_confirmed:
            return True
        week_end = self.week_start + timedelta(days=6)
        confirmed = messagebox.askyesno(
            "Edit old logs?",
            (
                "You are viewing old logs.\n\n"
                f"Selected week: {format_short_date(self.week_start)} - {format_short_date(week_end)}\n\n"
                "Edit this saved week anyway? I will only ask once until the app is restarted."
            ),
            parent=self,
        )
        if confirmed:
            self.old_week_edit_confirmed = True
            log_event("old_week_edit_confirmed", week_start=self.week_start.strftime(DATE_FMT))
        else:
            log_event("old_week_edit_cancelled", week_start=self.week_start.strftime(DATE_FMT))
        return confirmed

    def open_history(self) -> None:
        log_event("window_opened", window="history", week_start=self.week_start.strftime(DATE_FMT))
        HistoryWindow(self, self.db, self.select_week, self.export_backup, self.import_backup)

    def select_week(self, week_start: date) -> None:
        self.week_start = week_start
        self.selected_day = week_start
        log_event("week_selected", week_start=week_start.strftime(DATE_FMT))
        self.refresh()

    def open_response_manager(self) -> None:
        if NON_DETAILED_LOGS:
            messagebox.showinfo(
                "Detailed logs hidden",
                "Set non_detailed_logs = false in config.cfg to view and edit individual response logs.",
                parent=self,
            )
            return
        log_event("window_opened", window="response_manager", selected_day=self.selected_day.strftime(DATE_FMT))
        LogManager(
            self,
            self.db,
            self.selected_day,
            "response",
            RESPONSE_TYPES,
            "Responses",
            self.refresh,
        )

    def open_vital_manager(self) -> None:
        if NON_DETAILED_LOGS:
            messagebox.showinfo(
                "Detailed logs hidden",
                "Set non_detailed_logs = false in config.cfg to view and edit individual vital logs.",
                parent=self,
            )
            return
        log_event("window_opened", window="vital_manager", selected_day=self.selected_day.strftime(DATE_FMT))
        LogManager(self, self.db, self.selected_day, "vital", VITAL_TYPES, "Vitals", self.refresh)

    def open_main_log_detail(self, kind: str) -> None:
        if NON_DETAILED_LOGS:
            return
        listbox = self.response_list if kind == "response" else self.vital_list
        entries = self.response_entries if kind == "response" else self.vital_entries
        selected = listbox.curselection()
        if not selected or selected[0] >= len(entries):
            return
        options = RESPONSE_TYPES if kind == "response" else VITAL_TYPES
        log_event("log_detail_opened", kind=kind, log_id=entries[selected[0]].id)
        LogDetailWindow(
            self,
            self.db,
            entries[selected[0]],
            kind,
            options,
            self.refresh,
            self.refresh,
            self.get_responder_name,
            self.confirm_editing_selected_history,
        )

    def log_display_text(self, entry: LogEntry) -> str:
        postal = entry.postal if entry.postal else "N/A"
        details = f" - {entry.details}" if entry.details else ""
        image_count = len(parse_image_paths(entry.image_path))
        image = f" [{image_count} IMG]" if image_count else ""
        return f"- POSTAL {postal} ({entry.event_type}){details}{image}"

    def export_week(self) -> None:
        text = self.build_export_text()
        week_end = self.week_start + timedelta(days=6)
        try:
            EXPORT_DIR.mkdir(exist_ok=True)
            file_path = EXPORT_DIR / (
                f"FAMD_Attendance_{self.week_start.strftime(DATE_FMT)}_to_{week_end.strftime(DATE_FMT)}.txt"
            )
            file_path.write_text(text, encoding="utf-8")
        except OSError as exc:
            log_event(
                "weekly_export_failed",
                week_start=self.week_start.strftime(DATE_FMT),
                week_end=week_end.strftime(DATE_FMT),
                error=str(exc),
            )
            messagebox.showerror("Export failed", str(exc), parent=self)
            return

        self.clipboard_clear()
        self.clipboard_append(text)
        self.update()
        log_event(
            "weekly_export_completed",
            week_start=self.week_start.strftime(DATE_FMT),
            week_end=week_end.strftime(DATE_FMT),
            file_path=str(file_path),
            character_count=len(text),
        )
        messagebox.showinfo(
            "Export complete",
            f"Copied to clipboard and saved to:\n{file_path}",
            parent=self,
        )

    def build_export_text(self) -> str:
        return build_weekly_export_text(self.db, self.week_start)

    def export_backup(self) -> None:
        try:
            result = export_app_backup(DB_PATH, CONFIG_PATH, EXPORT_DIR)
        except (OSError, ValueError) as exc:
            log_event("backup_export_failed", error=str(exc))
            messagebox.showerror("Backup failed", str(exc), parent=self)
            return
        messagebox.showinfo(
            "Backup exported",
            f"Saved configuration and database backup to:\n{result.path}",
            parent=self,
        )

    def import_backup(self) -> None:
        archive = filedialog.askopenfilename(
            title="Import FAMD backup",
            filetypes=(("FAMD backup", "*.zip"), ("All files", "*.*")),
            parent=self,
        )
        if not archive:
            return
        if not messagebox.askyesno(
            "Import backup?",
            (
                "Importing a backup will replace the current database and config.cfg.\n\n"
                "A copy of the current database will be kept beside it before import. Continue?"
            ),
            parent=self,
        ):
            return
        try:
            self.save_responder_name()
            self.db.close()
            restore_path = import_app_backup(Path(archive), DB_PATH, CONFIG_PATH)
            self.db = FamdDatabase(DB_PATH)
            self.responder_name_var.set(self.db.get_setting("responder_name", DEFAULT_RESPONDERS))
            self.week_start = week_start_for(date.today())
            self.selected_day = date.today()
            self.old_week_edit_confirmed = False
            self.refresh()
        except (OSError, ValueError) as exc:
            self.db = FamdDatabase(DB_PATH)
            log_event("backup_import_failed", error=str(exc))
            messagebox.showerror("Import failed", str(exc), parent=self)
            return
        messagebox.showinfo(
            "Backup imported",
            (
                "Imported database and config.cfg.\n\n"
                f"Previous database copy:\n{restore_path}\n\n"
                "Restart the app to apply any imported config changes."
            ),
            parent=self,
        )

    def on_close(self) -> None:
        if self.refresh_job:
            self.after_cancel(self.refresh_job)
            self.refresh_job = None
        self.save_responder_name()
        log_event("app_closed")
        self.db.close()
        flush_logs(timeout=0.5)
        self.destroy()




def main() -> None:
    app = FamdToolApp()
    app.mainloop()
