from __future__ import annotations

from collections.abc import Callable
from threading import Thread
from typing import TypeVar
import tkinter as tk


T = TypeVar("T")


def run_background(
    widget: tk.Misc,
    work: Callable[[], T],
    on_success: Callable[[T], None],
    on_error: Callable[[Exception], None] | None = None,
) -> None:
    def dispatch(callback: Callable[[], None]) -> None:
        try:
            widget.after(0, callback)
        except tk.TclError:
            pass

    def runner() -> None:
        try:
            result = work()
        except Exception as exc:
            if on_error:
                dispatch(lambda exc=exc: on_error(exc))
            return
        dispatch(lambda result=result: on_success(result))

    Thread(target=runner, daemon=True).start()
