from __future__ import annotations

import os
from datetime import date, datetime, time, timedelta
from pathlib import Path
import tkinter as tk
from tkinter import messagebox, ttk

from .attachments import (
    build_individual_log_text,
    first_image_path,
    parse_image_paths,
    set_windows_image_clipboard,
)
from .config import DATE_FMT
from .database import FamdDatabase
from .dialogs import LogDialog, ShiftDialog
from .event_log import log_event
from .image_preview import load_thumbnail
from .models import LogEntry, Shift
from .tasks import run_background
from .time_utils import (
    format_hours,
    format_log_timestamp,
    format_short_date,
    format_time,
    minutes_between,
    week_start_for,
)
from .windowing import place_window_near_main


class ShiftManager(tk.Toplevel):
    def __init__(self, parent: FamdToolApp, db: FamdDatabase, day: date, on_change) -> None:
        super().__init__(parent)
        self.parent = parent
        self.db = db
        self.day = day
        self.on_change = on_change
        self.title(f"Edit Shifts - {format_short_date(day)}")
        self.geometry("620x360")
        log_event("shift_manager_opened", selected_day=day.strftime(DATE_FMT))
        self.transient(parent)
        place_window_near_main(self, parent)
        self.grab_set()
        self._build()
        self.refresh()

    def _build(self) -> None:
        self.columnconfigure(0, weight=1)
        self.rowconfigure(0, weight=1)
        self.tree = ttk.Treeview(
            self,
            columns=("date", "in", "out", "total"),
            show="headings",
            selectmode="browse",
        )
        for col, label, width in (
            ("date", "Date", 120),
            ("in", "Time-in", 120),
            ("out", "Clock-out", 120),
            ("total", "Total", 120),
        ):
            self.tree.heading(col, text=label)
            self.tree.column(col, width=width, anchor="center")
        self.tree.grid(row=0, column=0, sticky="nsew", padx=12, pady=12)
        self.tree.bind("<Double-1>", lambda _event: self.edit_selected())

        buttons = ttk.Frame(self, padding=(12, 0, 12, 12))
        buttons.grid(row=1, column=0, sticky="ew")
        ttk.Button(buttons, text="Add Shift", command=self.add_shift).pack(side="left")
        ttk.Button(buttons, text="Edit Selected", command=self.edit_selected).pack(side="left")
        ttk.Button(buttons, text="Delete Selected", command=self.delete_selected).pack(
            side="left", padx=8
        )
        ttk.Button(buttons, text="Close", command=self.destroy).pack(side="right")

    def refresh(self) -> None:
        for item in self.tree.get_children():
            self.tree.delete(item)
        for shift in self.db.list_shifts_for_day(self.day):
            end = shift.end
            total = format_hours(minutes_between(shift.start, end)) if end else "On Duty"
            self.tree.insert(
                "",
                "end",
                iid=str(shift.id),
                values=(
                    shift.start.date().strftime(DATE_FMT),
                    format_time(shift.start),
                    format_time(end) if end else "",
                    total,
                ),
            )

    def add_shift(self) -> None:
        default_start = datetime.combine(self.day, time(12, 0))
        default_end = datetime.combine(self.day, time(13, 0))
        dialog = ShiftDialog(self, "Add Shift", Shift(0, default_start, default_end))
        if dialog.result_data:
            start, end = dialog.result_data
            if end is None and self.db.get_active_shift():
                log_event(
                    "shift_add_rejected",
                    reason="active_shift_exists",
                    requested_start_ts=start.strftime("%Y-%m-%d %H:%M:%S"),
                )
                messagebox.showerror(
                    "Active shift exists",
                    "There is already an active shift. Close it before adding another active shift.",
                    parent=self,
                )
                return
            try:
                self.db.add_shift(start, end)
            except ValueError as exc:
                log_event("shift_add_failed", error=str(exc))
                messagebox.showerror("Invalid shift", str(exc), parent=self)
                return
            self.day = start.date()
            self.parent.selected_day = self.day
            self.parent.week_start = week_start_for(self.day)
            self.title(f"Edit Shifts - {format_short_date(self.day)}")
            self.refresh()
            self.on_change()

    def selected_shift(self) -> Shift | None:
        selected = self.tree.selection()
        if not selected:
            messagebox.showwarning("No selection", "Select a shift first.", parent=self)
            return None
        shift_id = int(selected[0])
        for shift in self.db.list_shifts_for_day(self.day):
            if shift.id == shift_id:
                return shift
        return None

    def edit_selected(self) -> None:
        shift = self.selected_shift()
        if not shift:
            return
        dialog = ShiftDialog(self, "Edit Shift", shift)
        if dialog.result_data:
            try:
                start, end = dialog.result_data
                self.db.update_shift(shift.id, start, end)
            except ValueError as exc:
                log_event("shift_edit_failed", shift_id=shift.id, error=str(exc))
                messagebox.showerror("Invalid shift", str(exc), parent=self)
                return
            self.day = start.date()
            self.parent.selected_day = self.day
            self.parent.week_start = week_start_for(self.day)
            self.title(f"Edit Shifts - {format_short_date(self.day)}")
            self.refresh()
            self.on_change()

    def delete_selected(self) -> None:
        shift = self.selected_shift()
        if not shift:
            return
        if messagebox.askyesno("Delete shift", "Delete selected shift?", parent=self):
            self.db.delete_shift(shift.id)
            self.refresh()
            self.on_change()


class LogManager(tk.Toplevel):
    def __init__(
        self,
        parent: FamdToolApp,
        db: FamdDatabase,
        day: date,
        kind: str,
        type_options: tuple[str, ...],
        title: str,
        on_change,
    ) -> None:
        super().__init__(parent)
        self.parent = parent
        self.db = db
        self.day = day
        self.kind = kind
        self.type_options = type_options
        self.on_change = on_change
        self.title(f"Edit {title} - {format_short_date(day)}")
        self.geometry("940x620")
        self.preview_images: list[tk.PhotoImage] = []
        log_event(
            "log_manager_opened",
            kind=kind,
            title=title,
            selected_day=day.strftime(DATE_FMT),
        )
        self.transient(parent)
        place_window_near_main(self, parent)
        self.grab_set()
        self._build()
        self.refresh()

    def _build(self) -> None:
        self.columnconfigure(0, weight=1)
        self.rowconfigure(0, weight=1)
        self.rowconfigure(1, weight=1)
        self.tree = ttk.Treeview(
            self,
            columns=("date", "time", "postal", "type", "responders", "image"),
            show="headings",
            selectmode="browse",
        )
        for col, label, width in (
            ("date", "Date", 100),
            ("time", "Timestamp", 140),
            ("postal", "Postal", 110),
            ("type", "Type", 110),
            ("responders", "Responder/s", 220),
            ("image", "Image", 80),
        ):
            self.tree.heading(col, text=label)
            self.tree.column(col, width=width, anchor="w")
        self.tree.grid(row=0, column=0, sticky="nsew", padx=12, pady=12)
        self.tree.bind("<Double-1>", lambda _event: self.view_selected())

        gallery_box = ttk.LabelFrame(self, text="Gallery")
        gallery_box.grid(row=1, column=0, sticky="nsew", padx=12, pady=(0, 12))
        gallery_box.columnconfigure(0, weight=1)
        gallery_box.rowconfigure(0, weight=1)
        self.gallery_canvas = tk.Canvas(gallery_box, height=170, highlightthickness=0)
        self.gallery_canvas.grid(row=0, column=0, sticky="nsew")
        gallery_scroll = ttk.Scrollbar(
            gallery_box, orient="horizontal", command=self.gallery_canvas.xview
        )
        gallery_scroll.grid(row=1, column=0, sticky="ew")
        self.gallery_canvas.configure(xscrollcommand=gallery_scroll.set)
        self.gallery_frame = ttk.Frame(self.gallery_canvas)
        self.gallery_window = self.gallery_canvas.create_window(
            (0, 0), window=self.gallery_frame, anchor="nw"
        )
        self.gallery_frame.bind(
            "<Configure>",
            lambda _event: self.gallery_canvas.configure(
                scrollregion=self.gallery_canvas.bbox("all")
            ),
        )

        buttons = ttk.Frame(self, padding=(12, 0, 12, 12))
        buttons.grid(row=2, column=0, sticky="ew")
        ttk.Button(buttons, text="Add", command=self.add_entry).pack(side="left")
        ttk.Button(buttons, text="View Selected", command=self.view_selected).pack(
            side="left", padx=8
        )
        ttk.Button(buttons, text="Edit Selected", command=self.edit_selected).pack(side="left")
        ttk.Button(buttons, text="Delete Selected", command=self.delete_selected).pack(side="left")
        ttk.Button(buttons, text="Copy Log Details", command=self.copy_selected_log).pack(
            side="left", padx=8
        )
        ttk.Button(buttons, text="Open Image", command=self.open_selected_image).pack(
            side="left"
        )
        ttk.Button(buttons, text="Close", command=self.destroy).pack(side="right")

    def refresh(self) -> None:
        for item in self.tree.get_children():
            self.tree.delete(item)
        entries = self.db.list_logs_for_day(self.kind, self.day)
        for entry in entries:
            self.tree.insert(
                "",
                "end",
                iid=str(entry.id),
                values=(
                    entry.event_date.strftime(DATE_FMT),
                    format_log_timestamp(entry.created_at),
                    entry.postal,
                    entry.event_type,
                    entry.responders,
                    f"{len(parse_image_paths(entry.image_path))} attached"
                    if entry.image_path
                    else "",
                ),
            )
        self.refresh_gallery(entries)

    def refresh_gallery(self, entries: list[LogEntry]) -> None:
        for child in self.gallery_frame.winfo_children():
            child.destroy()
        self.preview_images.clear()
        for column, entry in enumerate(entries):
            card = ttk.Frame(self.gallery_frame, padding=8, relief="ridge")
            card.grid(row=0, column=column, padx=6, pady=6, sticky="n")
            image_widget = self.build_gallery_image(card, entry)
            image_widget.grid(row=0, column=0, sticky="n")
            ttk.Label(card, text=f"Postal: {entry.postal or 'N/A'}", width=22).grid(
                row=1, column=0, sticky="w", pady=(6, 0)
            )
            ttk.Label(card, text=f"Type: {entry.event_type}", width=22).grid(
                row=2, column=0, sticky="w"
            )
            ttk.Button(card, text="View", command=lambda log=entry: self.open_detail(log)).grid(
                row=3, column=0, sticky="ew", pady=(6, 0)
            )
            card.bind("<Double-1>", lambda _event, log=entry: self.open_detail(log))

    def build_gallery_image(self, parent: tk.Misc, entry: LogEntry) -> ttk.Label:
        first_path = first_image_path(entry.image_path)
        image = load_thumbnail(first_path, 150, 95) if first_path else None
        if image is not None:
            self.preview_images.append(image)
            return ttk.Label(parent, image=image, width=20)
        return ttk.Label(parent, text="[IMAGE]", anchor="center", width=22)

    def selected_entry(self) -> LogEntry | None:
        selected = self.tree.selection()
        if not selected:
            messagebox.showwarning("No selection", "Select an entry first.", parent=self)
            return None
        entry_id = int(selected[0])
        for entry in self.db.list_logs_for_day(self.kind, self.day):
            if entry.id == entry_id:
                return entry
        return None

    def set_day_from_result(self, result_data: tuple[date, str, str, str, str, str]) -> None:
        event_date = result_data[0]
        self.day = event_date
        self.parent.selected_day = event_date
        self.parent.week_start = week_start_for(event_date)
        self.title(f"Edit {self.kind.title()}s - {format_short_date(event_date)}")

    def add_entry(self) -> None:
        dialog = LogDialog(
            self,
            "Add Entry",
            self.day,
            self.type_options,
            default_responders=self.parent.get_responder_name(),
        )
        if dialog.result_data:
            self.db.add_log(self.kind, *dialog.result_data)
            self.set_day_from_result(dialog.result_data)
            self.refresh()
            self.on_change()

    def edit_selected(self) -> None:
        entry = self.selected_entry()
        if not entry:
            return
        dialog = LogDialog(
            self,
            "Edit Entry",
            self.day,
            self.type_options,
            entry,
            self.parent.get_responder_name(),
        )
        if dialog.result_data:
            self.db.update_log(entry.id, *dialog.result_data)
            self.set_day_from_result(dialog.result_data)
            self.refresh()
            self.on_change()

    def view_selected(self) -> None:
        entry = self.selected_entry()
        if entry:
            self.open_detail(entry)

    def open_detail(self, entry: LogEntry) -> None:
        log_event("log_detail_opened", kind=self.kind, log_id=entry.id)
        LogDetailWindow(
            self,
            self.db,
            entry,
            self.kind,
            self.type_options,
            self.refresh,
            self.on_change,
            self.parent.get_responder_name,
        )

    def copy_selected_log(self) -> None:
        entry = self.selected_entry()
        if entry:
            self.copy_log(entry)

    def copy_log(self, entry: LogEntry) -> None:
        text = build_individual_log_text(entry)
        self.clipboard_clear()
        self.clipboard_append(text)
        self.update()
        log_event("log_details_copied", kind=self.kind, log_id=entry.id, character_count=len(text))
        messagebox.showinfo("Log details copied", "Copied log details to clipboard.", parent=self)

    def delete_selected(self) -> None:
        entry = self.selected_entry()
        if not entry:
            return
        if messagebox.askyesno("Delete entry", "Delete selected entry?", parent=self):
            self.db.delete_log(entry.id)
            self.refresh()
            self.on_change()

    def open_selected_image(self) -> None:
        entry = self.selected_entry()
        if not entry:
            return
        image_paths = parse_image_paths(entry.image_path)
        if not image_paths:
            messagebox.showinfo("No image", "This entry does not have an attached image.", parent=self)
            return
        image_path = Path(image_paths[0])
        if not image_path.exists():
            log_event(
                "log_image_open_failed",
                kind=self.kind,
                log_id=entry.id,
                path=str(image_path),
                reason="missing_file",
            )
            messagebox.showerror("Missing image", f"Image file not found:\n{image_path}", parent=self)
            return
        try:
            os.startfile(str(image_path))
            log_event("log_image_opened", kind=self.kind, log_id=entry.id, path=str(image_path))
        except OSError as exc:
            log_event(
                "log_image_open_failed",
                kind=self.kind,
                log_id=entry.id,
                path=str(image_path),
                error=str(exc),
            )
            messagebox.showerror("Open image failed", str(exc), parent=self)


class LogDetailWindow(tk.Toplevel):
    def __init__(
        self,
        parent: tk.Misc,
        db: FamdDatabase,
        entry: LogEntry,
        kind: str,
        type_options: tuple[str, ...],
        manager_refresh,
        app_refresh,
        responder_name_getter,
    ) -> None:
        super().__init__(parent)
        self.parent = parent
        self.db = db
        self.entry = entry
        self.kind = kind
        self.type_options = type_options
        self.manager_refresh = manager_refresh
        self.app_refresh = app_refresh
        self.responder_name_getter = responder_name_getter
        self.preview_image: tk.PhotoImage | None = None
        self.title("Log Details")
        self.geometry("620x620")
        log_event("log_detail_window_opened", kind=kind, log_id=entry.id)
        self.transient(parent)
        place_window_near_main(self, parent)
        self.grab_set()
        self._build()
        self.refresh()

    def _build(self) -> None:
        self.columnconfigure(0, weight=1)
        self.rowconfigure(1, weight=1)

        self.summary_var = tk.StringVar()
        ttk.Label(self, textvariable=self.summary_var, style="Section.TLabel").grid(
            row=0, column=0, sticky="ew", padx=12, pady=(12, 6)
        )

        body = ttk.Frame(self, padding=(12, 0, 12, 8))
        body.grid(row=1, column=0, sticky="nsew")
        body.columnconfigure(0, weight=1)
        body.rowconfigure(1, weight=1)

        self.image_label = ttk.Label(body, text="[IMAGE]", anchor="center")
        self.image_label.grid(row=0, column=0, sticky="ew", pady=(0, 8))

        self.text = tk.Text(body, height=10, wrap="word")
        self.text.grid(row=1, column=0, sticky="nsew")

        self.details_var = tk.StringVar()
        ttk.Label(body, textvariable=self.details_var, wraplength=560).grid(
            row=2, column=0, sticky="ew", pady=(8, 0)
        )

        buttons = ttk.Frame(self, padding=(12, 0, 12, 12))
        buttons.grid(row=2, column=0, sticky="ew")
        ttk.Button(buttons, text="Edit", command=self.edit).pack(side="left")
        ttk.Button(buttons, text="Copy Log Details", command=self.copy_log_details).pack(
            side="left", padx=8
        )
        ttk.Button(buttons, text="Copy Image", command=self.copy_image).pack(side="left")
        ttk.Button(buttons, text="Open Image", command=self.open_image).pack(side="left", padx=8)
        ttk.Button(buttons, text="Delete", command=self.delete_log).pack(side="left", padx=8)
        ttk.Button(buttons, text="Close", command=self.destroy).pack(side="right")

    def refresh(self) -> None:
        latest = self.db.get_log(self.entry.id)
        if latest:
            self.entry = latest
        image_count = len(parse_image_paths(self.entry.image_path))
        self.summary_var.set(
            f"{format_log_timestamp(self.entry.created_at)} | {self.entry.event_type} | "
            f"Postal {self.entry.postal or 'N/A'} | {image_count} image(s)"
        )
        self.text.configure(state="normal")
        self.text.delete("1.0", "end")
        self.text.insert("1.0", build_individual_log_text(self.entry))
        self.text.configure(state="disabled")
        self.details_var.set(f"Details: {self.entry.details}" if self.entry.details else "Details:")
        self.refresh_image()

    def refresh_image(self) -> None:
        self.preview_image = None
        first_path = first_image_path(self.entry.image_path)
        image = load_thumbnail(first_path, 520, 220) if first_path else None
        if image is not None:
            self.preview_image = image
            self.image_label.configure(image=image, text="")
            return
        self.image_label.configure(image="", text="[IMAGE]")

    def edit(self) -> None:
        dialog = LogDialog(
            self,
            "Edit Entry",
            self.entry.event_date,
            self.type_options,
            self.entry,
            self.responder_name_getter(),
        )
        if dialog.result_data:
            self.db.update_log(self.entry.id, *dialog.result_data)
            self.manager_refresh()
            self.app_refresh()
            self.refresh()

    def copy_log_details(self) -> None:
        text = build_individual_log_text(self.entry)
        self.clipboard_clear()
        self.clipboard_append(text)
        self.update()
        log_event(
            "log_details_copied",
            kind=self.kind,
            log_id=self.entry.id,
            character_count=len(text),
        )
        messagebox.showinfo("Log details copied", "Copied log details to clipboard.", parent=self)

    def copy_image(self) -> None:
        image_path = first_image_path(self.entry.image_path)
        if not image_path:
            log_event("log_image_copy_skipped", kind=self.kind, log_id=self.entry.id, reason="no_image")
            messagebox.showinfo("No image", "This entry does not have an attached image.", parent=self)
            return
        if not Path(image_path).exists():
            log_event(
                "log_image_copy_failed",
                kind=self.kind,
                log_id=self.entry.id,
                path=image_path,
                reason="missing_file",
            )
            messagebox.showerror("Missing image", f"Image file not found:\n{image_path}", parent=self)
            return
        log_event("log_image_copy_requested", kind=self.kind, log_id=self.entry.id, path=image_path)
        self.configure(cursor="watch")
        try:
            self.update_idletasks()
        except tk.TclError:
            pass
        run_background(
            self,
            lambda: set_windows_image_clipboard(image_path),
            self.finish_copy_image,
            self.fail_copy_image,
        )

    def finish_copy_image(self, copied: bool) -> None:
        self.configure(cursor="")
        if copied:
            log_event("log_image_copied", kind=self.kind, log_id=self.entry.id)
            messagebox.showinfo("Image copied", "Copied image to clipboard.", parent=self)
            return
        log_event("log_image_copy_failed", kind=self.kind, log_id=self.entry.id, reason="clipboard_rejected")
        messagebox.showerror("Image copy failed", "Could not copy the image to clipboard.", parent=self)

    def fail_copy_image(self, exc: Exception) -> None:
        self.configure(cursor="")
        log_event("log_image_copy_failed", kind=self.kind, log_id=self.entry.id, error=str(exc))
        messagebox.showerror("Image copy failed", str(exc), parent=self)

    def delete_log(self) -> None:
        if not messagebox.askyesno("Delete log", "Delete this log?", parent=self):
            return
        self.db.delete_log(self.entry.id)
        self.manager_refresh()
        self.app_refresh()
        self.destroy()

    def open_image(self) -> None:
        image_paths = parse_image_paths(self.entry.image_path)
        if not image_paths:
            log_event("log_image_open_skipped", kind=self.kind, log_id=self.entry.id, reason="no_image")
            messagebox.showinfo("No image", "This entry does not have an attached image.", parent=self)
            return
        image_path = Path(image_paths[0])
        if not image_path.exists():
            log_event(
                "log_image_open_failed",
                kind=self.kind,
                log_id=self.entry.id,
                path=str(image_path),
                reason="missing_file",
            )
            messagebox.showerror("Missing image", f"Image file not found:\n{image_path}", parent=self)
            return
        try:
            os.startfile(str(image_path))
            log_event("log_image_opened", kind=self.kind, log_id=self.entry.id, path=str(image_path))
        except OSError as exc:
            log_event(
                "log_image_open_failed",
                kind=self.kind,
                log_id=self.entry.id,
                path=str(image_path),
                error=str(exc),
            )
            messagebox.showerror("Open image failed", str(exc), parent=self)


class HistoryWindow(tk.Toplevel):
    def __init__(self, parent: FamdToolApp, db: FamdDatabase, on_select) -> None:
        super().__init__(parent)
        self.parent = parent
        self.db = db
        self.on_select = on_select
        self.title("History")
        self.geometry("640x380")
        log_event("history_window_opened")
        self.transient(parent)
        place_window_near_main(self, parent)
        self.grab_set()
        self._build()
        self.refresh()

    def _build(self) -> None:
        self.columnconfigure(0, weight=1)
        self.rowconfigure(0, weight=1)
        self.tree = ttk.Treeview(
            self,
            columns=("week", "hours", "responses", "vitals"),
            show="headings",
            selectmode="browse",
        )
        for col, label, width in (
            ("week", "Week", 220),
            ("hours", "Duty Hours", 120),
            ("responses", "Responses", 110),
            ("vitals", "Vitals", 100),
        ):
            self.tree.heading(col, text=label)
            self.tree.column(col, width=width, anchor="center")
        self.tree.grid(row=0, column=0, sticky="nsew", padx=12, pady=12)
        self.tree.bind("<Double-1>", lambda _event: self.open_selected())

        buttons = ttk.Frame(self, padding=(12, 0, 12, 12))
        buttons.grid(row=1, column=0, sticky="ew")
        ttk.Button(buttons, text="Open Selected Week", command=self.open_selected).pack(side="left")
        ttk.Button(buttons, text="Close", command=self.destroy).pack(side="right")

    def refresh(self) -> None:
        for item in self.tree.get_children():
            self.tree.delete(item)
        for week_start in self.db.list_saved_weeks():
            week_end = week_start + timedelta(days=6)
            hours = format_hours(self.parent.total_minutes(week_start, week_end))
            responses = len(self.db.list_logs("response", week_start, week_end))
            vitals = len(self.db.list_logs("vital", week_start, week_end))
            self.tree.insert(
                "",
                "end",
                iid=week_start.strftime(DATE_FMT),
                values=(
                    f"{format_short_date(week_start)} - {format_short_date(week_end)}",
                    hours,
                    responses,
                    vitals,
                ),
            )

    def open_selected(self) -> None:
        selected = self.tree.selection()
        if not selected:
            messagebox.showwarning("No selection", "Select a week first.", parent=self)
            return
        week_start = datetime.strptime(selected[0], DATE_FMT).date()
        log_event("history_week_opened", week_start=week_start.strftime(DATE_FMT))
        self.on_select(week_start)
        self.destroy()


