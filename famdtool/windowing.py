from __future__ import annotations

import tkinter as tk


def main_window_for(widget: tk.Misc | None) -> tk.Misc | None:
    current = widget
    while current is not None:
        if isinstance(current, tk.Tk):
            return current
        current = getattr(current, "master", None)
    return None


def place_window_near_main(window: tk.Misc, parent: tk.Misc | None) -> None:
    main = main_window_for(parent) or parent
    if main is None:
        return
    window.update_idletasks()
    main.update_idletasks()

    window_width = max(window.winfo_width(), window.winfo_reqwidth())
    window_height = max(window.winfo_height(), window.winfo_reqheight())
    main_width = max(main.winfo_width(), main.winfo_reqwidth())
    main_height = max(main.winfo_height(), main.winfo_reqheight())

    x = main.winfo_rootx() + max(0, (main_width - window_width) // 2)
    y = main.winfo_rooty() + max(0, (main_height - window_height) // 2)

    screen_width = window.winfo_screenwidth()
    screen_height = window.winfo_screenheight()
    x = min(max(0, x), max(0, screen_width - window_width))
    y = min(max(0, y), max(0, screen_height - window_height))
    window.geometry(f"+{x}+{y}")


