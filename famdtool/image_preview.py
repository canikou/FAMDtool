from __future__ import annotations

from pathlib import Path
import tkinter as tk

try:
    from PIL import Image, ImageTk
except ImportError:
    Image = None
    ImageTk = None


def load_thumbnail(path: str | Path, max_width: int, max_height: int) -> tk.PhotoImage | None:
    image_path = Path(path)
    if not image_path.exists():
        return None

    if Image is not None and ImageTk is not None:
        try:
            with Image.open(image_path) as image:
                image.thumbnail((max_width, max_height), Image.Resampling.LANCZOS)
                return ImageTk.PhotoImage(image.copy())
        except (OSError, tk.TclError):
            return None

    try:
        image = tk.PhotoImage(file=str(image_path))
        scale = max(1, image.width() // max_width, image.height() // max_height)
        return image.subsample(scale, scale) if scale > 1 else image
    except tk.TclError:
        return None
