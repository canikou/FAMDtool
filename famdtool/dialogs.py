from __future__ import annotations

import subprocess
from datetime import date, datetime, time
from pathlib import Path
import tkinter as tk
from tkinter import filedialog, messagebox, simpledialog, ttk

from .attachments import (
    copy_images_to_attachments,
    parse_image_paths,
    save_clipboard_image_to_file,
)
from .config import DATE_FMT, DEFAULT_RESPONDERS
from .event_log import log_event
from .image_preview import load_thumbnail
from .models import LogEntry, Shift
from .tasks import run_background
from .time_utils import clamp_int, format_time, local_now, minute_after_scroll
from .windowing import place_window_near_main


class LogDialog(simpledialog.Dialog):
    def __init__(
        self,
        parent: tk.Misc,
        title: str,
        selected_day: date,
        type_options: tuple[str, ...],
        entry: LogEntry | None = None,
        default_responders: str = DEFAULT_RESPONDERS,
    ) -> None:
        self.dialog_parent = parent
        self.dialog_title = title
        self.selected_day = selected_day
        self.type_options = type_options
        self.entry = entry
        self.default_responders = default_responders
        self.image_paths = parse_image_paths(entry.image_path) if entry else []
        self.preview_images: list[tk.PhotoImage] = []
        self.result_data: tuple[date, str, str, str, str, str] | None = None
        log_event(
            "log_dialog_opened",
            title=title,
            selected_day=selected_day.strftime(DATE_FMT),
            type_options=list(type_options),
            editing_log_id=entry.id if entry else None,
        )
        super().__init__(parent, title)

    def destroy(self) -> None:
        self.unbind_all("<Control-v>")
        self.unbind_all("<Control-V>")
        super().destroy()

    def body(self, master: tk.Frame) -> tk.Widget:
        ttk.Label(master, text="Date").grid(row=0, column=0, sticky="w", padx=6, pady=4)
        self.date_var = tk.StringVar(
            value=(self.entry.event_date if self.entry else self.selected_day).strftime(DATE_FMT)
        )
        ttk.Entry(master, textvariable=self.date_var, width=24).grid(
            row=0, column=1, sticky="ew", padx=6, pady=4
        )

        ttk.Label(master, text="Postal").grid(row=1, column=0, sticky="w", padx=6, pady=4)
        self.postal_var = tk.StringVar(value=self.entry.postal if self.entry else "")
        ttk.Entry(master, textvariable=self.postal_var, width=24).grid(
            row=1, column=1, sticky="ew", padx=6, pady=4
        )

        ttk.Label(master, text="Type").grid(row=2, column=0, sticky="w", padx=6, pady=4)
        self.type_var = tk.StringVar(
            value=self.entry.event_type if self.entry else self.type_options[0]
        )
        type_frame = ttk.Frame(master)
        type_frame.grid(row=2, column=1, sticky="ew", padx=6, pady=4)
        self.type_buttons: dict[str, ttk.Button] = {}
        for event_type in self.type_options:
            button = ttk.Button(
                type_frame,
                text=event_type,
                command=lambda value=event_type: self.set_type(value),
            )
            button.pack(side="left", padx=(0, 6))
            self.type_buttons[event_type] = button
        self.refresh_type_styles()

        ttk.Label(master, text="Responder/s").grid(row=3, column=0, sticky="w", padx=6, pady=4)
        self.responders_var = tk.StringVar(
            value=self.entry.responders if self.entry else self.default_responders
        )
        ttk.Entry(master, textvariable=self.responders_var, width=32).grid(
            row=3, column=1, sticky="ew", padx=6, pady=4
        )

        ttk.Label(master, text="Details").grid(row=4, column=0, sticky="nw", padx=6, pady=4)
        self.details = tk.Text(master, width=32, height=5)
        self.details.grid(row=4, column=1, sticky="ew", padx=6, pady=4)
        self.details.insert("1.0", self.entry.details if self.entry else "")

        ttk.Label(master, text="Images").grid(row=5, column=0, sticky="nw", padx=6, pady=4)
        image_frame = ttk.Frame(master)
        image_frame.grid(row=5, column=1, sticky="ew", padx=6, pady=4)
        image_frame.columnconfigure(0, weight=1)
        self.image_list = tk.Listbox(image_frame, height=4, activestyle="none")
        self.image_list.grid(row=0, column=0, rowspan=4, sticky="ew")
        ttk.Button(image_frame, text="Attach", command=self.attach_image).grid(
            row=0, column=1, padx=(6, 0)
        )
        ttk.Button(image_frame, text="Paste", command=self.paste_image).grid(
            row=1, column=1, padx=(6, 0), pady=(4, 0)
        )
        ttk.Button(image_frame, text="Remove", command=self.remove_selected_image).grid(
            row=2, column=1, padx=(6, 0), pady=(4, 0)
        )
        ttk.Button(image_frame, text="Clear", command=self.clear_images).grid(
            row=3, column=1, padx=(6, 0), pady=(4, 0)
        )

        self.preview_label = ttk.Label(master, text="[IMAGE PREVIEW]", anchor="center")
        self.preview_label.grid(row=6, column=1, sticky="ew", padx=6, pady=(0, 4))
        self.image_list.bind("<<ListboxSelect>>", lambda _event: self.refresh_image_preview())
        self.refresh_image_list()
        self.bind_all("<Control-v>", self.handle_ctrl_v, add="+")
        self.bind_all("<Control-V>", self.handle_ctrl_v, add="+")
        ttk.Label(master, text="Ctrl+V anywhere here attaches a clipboard image.").grid(
            row=7, column=0, columnspan=2, sticky="w", padx=6, pady=(0, 4)
        )
        master.columnconfigure(1, weight=1)
        self.after_idle(lambda: place_window_near_main(self, self.dialog_parent))
        return master

    def attach_image(self) -> None:
        paths = filedialog.askopenfilenames(
            parent=self,
            title="Attach images",
            filetypes=(
                ("Image files", "*.png *.jpg *.jpeg *.gif *.bmp *.webp"),
                ("All files", "*.*"),
            ),
        )
        if paths:
            log_event(
                "images_attached_from_file_dialog",
                title=self.dialog_title,
                count=len(paths),
                paths=list(paths),
            )
            for path in paths:
                self.add_image_path(path)

    def set_type(self, value: str) -> None:
        self.type_var.set(value)
        self.refresh_type_styles()

    def refresh_type_styles(self) -> None:
        selected = self.type_var.get()
        for event_type, button in self.type_buttons.items():
            button.configure(style="Selected.TButton" if event_type == selected else "TButton")

    def paste_image(self) -> None:
        log_event("clipboard_image_paste_requested", title=self.dialog_title)
        self.configure(cursor="watch")
        try:
            self.update_idletasks()
        except tk.TclError:
            pass
        run_background(self, save_clipboard_image_to_file, self.finish_paste_image, self.fail_paste_image)

    def finish_paste_image(self, path: Path | None) -> None:
        self.configure(cursor="")
        if not path:
            log_event("clipboard_image_paste_empty", title=self.dialog_title)
            messagebox.showinfo("No image", "No image was found on the clipboard.", parent=self)
            return
        log_event("clipboard_image_pasted", title=self.dialog_title, path=str(path))
        self.add_image_path(str(path))

    def fail_paste_image(self, exc: Exception) -> None:
        self.configure(cursor="")
        log_event("clipboard_image_paste_failed", title=self.dialog_title, error=str(exc))
        messagebox.showerror("Clipboard image failed", str(exc), parent=self)

    def handle_ctrl_v(self, event: tk.Event) -> str | None:
        try:
            path = save_clipboard_image_to_file()
        except (subprocess.SubprocessError, OSError):
            log_event("clipboard_image_ctrl_v_failed", title=self.dialog_title)
            return None
        if not path:
            return None
        log_event("clipboard_image_ctrl_v_pasted", title=self.dialog_title, path=str(path))
        self.add_image_path(str(path))
        return "break"

    def add_image_path(self, path: str) -> None:
        if path and path not in self.image_paths:
            self.image_paths.append(path)
            log_event(
                "image_added_to_dialog",
                title=self.dialog_title,
                path=path,
                image_count=len(self.image_paths),
            )
            self.refresh_image_list(select_last=True)

    def remove_selected_image(self) -> None:
        selected = self.image_list.curselection()
        if not selected:
            return
        removed_path = self.image_paths[selected[0]]
        del self.image_paths[selected[0]]
        log_event(
            "image_removed_from_dialog",
            title=self.dialog_title,
            path=removed_path,
            image_count=len(self.image_paths),
        )
        self.refresh_image_list()

    def clear_images(self) -> None:
        previous_count = len(self.image_paths)
        self.image_paths.clear()
        log_event("images_cleared_from_dialog", title=self.dialog_title, previous_count=previous_count)
        self.refresh_image_list()

    def refresh_image_list(self, select_last: bool = False) -> None:
        self.image_list.delete(0, "end")
        for path in self.image_paths:
            self.image_list.insert("end", Path(path).name)
        if self.image_paths:
            index = len(self.image_paths) - 1 if select_last else 0
            self.image_list.selection_set(index)
        self.refresh_image_preview()

    def refresh_image_preview(self) -> None:
        self.preview_images.clear()
        selected = self.image_list.curselection()
        path = self.image_paths[selected[0]] if selected else (self.image_paths[0] if self.image_paths else "")
        image = load_thumbnail(path, 260, 140) if path else None
        if image is not None:
            self.preview_images.append(image)
            self.preview_label.configure(image=image, text="")
            return
        self.preview_label.configure(image="", text="[IMAGE PREVIEW]")

    def validate(self) -> bool:
        try:
            event_date = datetime.strptime(self.date_var.get().strip(), DATE_FMT).date()
        except ValueError:
            log_event(
                "log_dialog_invalid",
                title=self.dialog_title,
                reason="invalid_date",
                value=self.date_var.get().strip(),
            )
            messagebox.showerror("Invalid input", "Use date format YYYY-MM-DD.", parent=self)
            return False
        try:
            image_path = copy_images_to_attachments(self.image_paths)
        except OSError as exc:
            log_event("log_dialog_invalid", title=self.dialog_title, reason="image_error", error=str(exc))
            messagebox.showerror("Image error", str(exc), parent=self)
            return False
        except ValueError as exc:
            log_event("log_dialog_invalid", title=self.dialog_title, reason="image_error", error=str(exc))
            messagebox.showerror("Image error", str(exc), parent=self)
            return False
        self.result_data = (
            event_date,
            self.postal_var.get(),
            self.type_var.get(),
            self.responders_var.get(),
            self.details.get("1.0", "end").strip(),
            image_path,
        )
        log_event(
            "log_dialog_validated",
            title=self.dialog_title,
            event_date=event_date.strftime(DATE_FMT),
            postal=self.postal_var.get().strip(),
            event_type=self.type_var.get(),
            responders=self.responders_var.get().strip(),
            attachment_count=len(parse_image_paths(image_path)),
            image_path=image_path,
        )
        return True


class TimeInputFrame(ttk.Frame):
    def __init__(self, master: tk.Misc, value: datetime | None) -> None:
        super().__init__(master)
        value = value or local_now()
        hour = value.hour % 12 or 12
        self.hour_var = tk.StringVar(value=str(hour))
        self.minute_var = tk.StringVar(value=f"{value.minute:02d}")
        self.ampm_var = tk.StringVar(value="PM" if value.hour >= 12 else "AM")

        self.hour_spin = tk.Spinbox(
            self,
            from_=1,
            to=12,
            wrap=True,
            width=3,
            textvariable=self.hour_var,
            command=self.normalize,
        )
        self.hour_spin.grid(row=0, column=0, sticky="w")
        ttk.Label(self, text=":").grid(row=0, column=1, padx=2)
        self.minute_spin = tk.Spinbox(
            self,
            from_=0,
            to=59,
            wrap=True,
            width=3,
            textvariable=self.minute_var,
            format="%02.0f",
            command=self.normalize,
        )
        self.minute_spin.grid(row=0, column=2, sticky="w")
        self.am_button = ttk.Button(self, text="AM", width=4, command=lambda: self.set_ampm("AM"))
        self.am_button.grid(row=0, column=3, padx=(8, 2))
        self.pm_button = ttk.Button(self, text="PM", width=4, command=lambda: self.set_ampm("PM"))
        self.pm_button.grid(row=0, column=4)
        self.refresh_ampm_style()

        for widget in (self.hour_spin, self.minute_spin):
            widget.bind("<FocusOut>", lambda _event: self.normalize())
            widget.bind("<Return>", lambda _event: self.normalize())
            widget.bind("<KeyPress-a>", lambda _event: self.set_ampm("AM"))
            widget.bind("<KeyPress-A>", lambda _event: self.set_ampm("AM"))
            widget.bind("<KeyPress-p>", lambda _event: self.set_ampm("PM"))
            widget.bind("<KeyPress-P>", lambda _event: self.set_ampm("PM"))
        self.minute_spin.bind("<MouseWheel>", self.on_minute_mousewheel)

    def on_minute_mousewheel(self, event: tk.Event) -> str:
        direction = 1 if event.delta > 0 else -1
        self.minute_var.set(minute_after_scroll(self.minute_var.get(), direction, bool(event.state & 0x0001)))
        self.normalize()
        return "break"

    def set_ampm(self, value: str) -> str:
        self.ampm_var.set(value)
        self.refresh_ampm_style()
        return "break"

    def refresh_ampm_style(self) -> None:
        self.am_button.configure(style="Selected.TButton" if self.ampm_var.get() == "AM" else "TButton")
        self.pm_button.configure(style="Selected.TButton" if self.ampm_var.get() == "PM" else "TButton")

    def normalize(self) -> None:
        self.hour_var.set(str(clamp_int(self.hour_var.get(), 1, 12)))
        self.minute_var.set(f"{clamp_int(self.minute_var.get(), 0, 59):02d}")


    def get_time(self) -> time:
        self.normalize()
        hour = int(self.hour_var.get())
        minute = int(self.minute_var.get())
        if self.ampm_var.get() == "AM":
            hour = 0 if hour == 12 else hour
        else:
            hour = 12 if hour == 12 else hour + 12
        return time(hour, minute)


class ShiftDialog(simpledialog.Dialog):
    def __init__(self, parent: tk.Misc, title: str, shift: Shift) -> None:
        self.dialog_parent = parent
        self.dialog_title = title
        self.shift = shift
        self.result_data: tuple[datetime, datetime | None] | None = None
        log_event(
            "shift_dialog_opened",
            title=title,
            shift_id=shift.id,
            start_ts=shift.start.strftime("%Y-%m-%d %H:%M:%S"),
            end_ts=shift.end.strftime("%Y-%m-%d %H:%M:%S") if shift.end else None,
        )
        super().__init__(parent, title)

    def body(self, master: tk.Frame) -> tk.Widget:
        ttk.Label(master, text="Time-in date").grid(row=0, column=0, sticky="w", padx=6, pady=4)
        self.start_date_var = tk.StringVar(value=self.shift.start.date().strftime(DATE_FMT))
        ttk.Entry(master, textvariable=self.start_date_var, width=24).grid(
            row=0, column=1, sticky="ew", padx=6, pady=4
        )

        ttk.Label(master, text="Time-in").grid(row=1, column=0, sticky="w", padx=6, pady=4)
        self.start_time_input = TimeInputFrame(master, self.shift.start)
        self.start_time_input.grid(
            row=1, column=1, sticky="ew", padx=6, pady=4
        )

        ttk.Label(master, text="Clock-out date").grid(row=2, column=0, sticky="w", padx=6, pady=4)
        end_date = self.shift.end.date() if self.shift.end else self.shift.start.date()
        self.end_date_var = tk.StringVar(value=end_date.strftime(DATE_FMT))
        ttk.Entry(master, textvariable=self.end_date_var, width=24).grid(
            row=2, column=1, sticky="ew", padx=6, pady=4
        )

        ttk.Label(master, text="Clock-out").grid(row=3, column=0, sticky="w", padx=6, pady=4)
        end_time_value = self.shift.end if self.shift.end else self.shift.start
        self.end_enabled_var = tk.BooleanVar(value=self.shift.end is not None)
        end_frame = ttk.Frame(master)
        end_frame.grid(row=3, column=1, sticky="ew", padx=6, pady=4)
        ttk.Checkbutton(
            end_frame,
            text="Set clock-out",
            variable=self.end_enabled_var,
            command=self.toggle_end_inputs,
        ).grid(row=0, column=0, sticky="w", padx=(0, 8))
        self.end_time_input = TimeInputFrame(end_frame, end_time_value)
        self.end_time_input.grid(row=0, column=1, sticky="w")

        ttk.Label(master, text="Leave clock-out disabled for active shift.").grid(
            row=4, column=0, columnspan=2, sticky="w", padx=6, pady=4
        )
        self.toggle_end_inputs()
        master.columnconfigure(1, weight=1)
        self.after_idle(lambda: place_window_near_main(self, self.dialog_parent))
        return master

    def toggle_end_inputs(self) -> None:
        state = "normal" if self.end_enabled_var.get() else "disabled"
        for child in self.end_time_input.winfo_children():
            try:
                child.configure(state=state)
            except tk.TclError:
                pass

    def validate(self) -> bool:
        try:
            start_date = datetime.strptime(self.start_date_var.get().strip(), DATE_FMT).date()
            start = datetime.combine(start_date, self.start_time_input.get_time())
            end = None
            if self.end_enabled_var.get():
                end_date = datetime.strptime(self.end_date_var.get().strip(), DATE_FMT).date()
                end = datetime.combine(end_date, self.end_time_input.get_time())
                if end < start:
                    raise ValueError("Clock-out cannot be earlier than time-in.")
        except ValueError as exc:
            log_event(
                "shift_dialog_invalid",
                title=self.dialog_title,
                reason=str(exc),
                start_date=self.start_date_var.get().strip(),
                end_date=self.end_date_var.get().strip(),
            )
            messagebox.showerror("Invalid shift", str(exc), parent=self)
            return False
        self.result_data = (start, end)
        log_event(
            "shift_dialog_validated",
            title=self.dialog_title,
            shift_id=self.shift.id,
            start_ts=start.strftime("%Y-%m-%d %H:%M:%S"),
            end_ts=end.strftime("%Y-%m-%d %H:%M:%S") if end else None,
        )
        return True


