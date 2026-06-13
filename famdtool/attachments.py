from __future__ import annotations

import ctypes
import json
import os
import shutil
import subprocess
import tempfile
from datetime import datetime
from io import BytesIO
from pathlib import Path

from . import config
from .models import LogEntry
from .time_utils import format_log_timestamp

try:
    from PIL import Image, ImageDraw, ImageFont, ImageGrab
except ImportError:
    Image = None
    ImageDraw = None
    ImageFont = None
    ImageGrab = None


def ps_quote(value: str | Path) -> str:
    return "'" + str(value).replace("'", "''") + "'"


def save_clipboard_image_to_file() -> Path | None:
    config.ATTACH_DIR.mkdir(exist_ok=True)
    output_path = config.ATTACH_DIR / f"clipboard_{datetime.now().strftime('%Y%m%d_%H%M%S')}.png"
    if ImageGrab is not None:
        grabbed = ImageGrab.grabclipboard()
        if Image is not None and isinstance(grabbed, Image.Image):
            grabbed.save(output_path, "PNG")
            return output_path
        if isinstance(grabbed, list):
            for item in grabbed:
                source = Path(item)
                if source.suffix.lower() in {".png", ".jpg", ".jpeg", ".gif", ".bmp", ".webp"}:
                    return Path(copy_image_to_attachments(str(source)))
            return None

    script = f"""
Add-Type -AssemblyName System.Windows.Forms
Add-Type -AssemblyName System.Drawing
if ([System.Windows.Forms.Clipboard]::ContainsImage()) {{
    $image = [System.Windows.Forms.Clipboard]::GetImage()
    $image.Save({ps_quote(output_path)}, [System.Drawing.Imaging.ImageFormat]::Png)
    $image.Dispose()
    Write-Output "OK"
}} else {{
    Write-Output "NO_IMAGE"
}}
"""
    result = subprocess.run(
        ["powershell", "-NoProfile", "-Command", script],
        capture_output=True,
        text=True,
        timeout=10,
        check=False,
    )
    if result.returncode == 0 and "OK" in result.stdout and output_path.exists():
        return output_path
    return None


def set_windows_clipboard(text: str, image_path: str = "") -> bool:
    if os.name != "nt":
        return False

    user32 = ctypes.windll.user32
    kernel32 = ctypes.windll.kernel32
    cf_unicode_text = 13
    cf_dib = 8
    gmem_moveable = 0x0002
    user32.OpenClipboard.argtypes = [ctypes.c_void_p]
    user32.OpenClipboard.restype = ctypes.c_bool
    user32.EmptyClipboard.argtypes = []
    user32.EmptyClipboard.restype = ctypes.c_bool
    user32.CloseClipboard.argtypes = []
    user32.CloseClipboard.restype = ctypes.c_bool
    user32.SetClipboardData.argtypes = [ctypes.c_uint, ctypes.c_void_p]
    kernel32.GlobalAlloc.restype = ctypes.c_void_p
    kernel32.GlobalAlloc.argtypes = [ctypes.c_uint, ctypes.c_size_t]
    kernel32.GlobalLock.restype = ctypes.c_void_p
    kernel32.GlobalLock.argtypes = [ctypes.c_void_p]
    kernel32.GlobalUnlock.argtypes = [ctypes.c_void_p]
    kernel32.GlobalUnlock.restype = ctypes.c_bool
    user32.SetClipboardData.restype = ctypes.c_void_p

    if not user32.OpenClipboard(None):
        return False
    try:
        if not user32.EmptyClipboard():
            return False

        text_bytes = text.encode("utf-16-le") + b"\x00\x00"
        text_handle = kernel32.GlobalAlloc(gmem_moveable, len(text_bytes))
        if not text_handle:
            return False
        text_pointer = kernel32.GlobalLock(text_handle)
        if not text_pointer:
            return False
        ctypes.memmove(text_pointer, text_bytes, len(text_bytes))
        kernel32.GlobalUnlock(text_handle)
        if not user32.SetClipboardData(cf_unicode_text, text_handle):
            return False

        clipboard_image = first_image_path(image_path)
        if clipboard_image and Image is not None and Path(clipboard_image).exists():
            with Image.open(clipboard_image) as image:
                output = BytesIO()
                image.convert("RGB").save(output, "BMP")
                dib_bytes = output.getvalue()[14:]
            image_handle = kernel32.GlobalAlloc(gmem_moveable, len(dib_bytes))
            if not image_handle:
                return False
            image_pointer = kernel32.GlobalLock(image_handle)
            if not image_pointer:
                return False
            ctypes.memmove(image_pointer, dib_bytes, len(dib_bytes))
            kernel32.GlobalUnlock(image_handle)
            if not user32.SetClipboardData(cf_dib, image_handle):
                return False
        return True
    finally:
        user32.CloseClipboard()


def image_to_dib_bytes(image_path: str) -> bytes:
    if Image is None:
        raise RuntimeError("Pillow is required for image clipboard support.")
    with Image.open(image_path) as image:
        output = BytesIO()
        image.convert("RGB").save(output, "BMP")
        return output.getvalue()[14:]


def set_windows_image_clipboard(image_path: str) -> bool:
    if os.name != "nt" or not image_path or Image is None or not Path(image_path).exists():
        return False

    user32 = ctypes.windll.user32
    kernel32 = ctypes.windll.kernel32
    cf_dib = 8
    gmem_moveable = 0x0002
    user32.OpenClipboard.argtypes = [ctypes.c_void_p]
    user32.OpenClipboard.restype = ctypes.c_bool
    user32.EmptyClipboard.argtypes = []
    user32.EmptyClipboard.restype = ctypes.c_bool
    user32.CloseClipboard.argtypes = []
    user32.CloseClipboard.restype = ctypes.c_bool
    user32.SetClipboardData.argtypes = [ctypes.c_uint, ctypes.c_void_p]
    user32.SetClipboardData.restype = ctypes.c_void_p
    kernel32.GlobalAlloc.argtypes = [ctypes.c_uint, ctypes.c_size_t]
    kernel32.GlobalAlloc.restype = ctypes.c_void_p
    kernel32.GlobalLock.argtypes = [ctypes.c_void_p]
    kernel32.GlobalLock.restype = ctypes.c_void_p
    kernel32.GlobalUnlock.argtypes = [ctypes.c_void_p]
    kernel32.GlobalUnlock.restype = ctypes.c_bool

    try:
        dib_bytes = image_to_dib_bytes(image_path)
    except (OSError, RuntimeError):
        return False

    if not user32.OpenClipboard(None):
        return False
    try:
        if not user32.EmptyClipboard():
            return False
        image_handle = kernel32.GlobalAlloc(gmem_moveable, len(dib_bytes))
        if not image_handle:
            return False
        image_pointer = kernel32.GlobalLock(image_handle)
        if not image_pointer:
            return False
        ctypes.memmove(image_pointer, dib_bytes, len(dib_bytes))
        kernel32.GlobalUnlock(image_handle)
        return bool(user32.SetClipboardData(cf_dib, image_handle))
    finally:
        user32.CloseClipboard()


def parse_image_paths(value: str) -> list[str]:
    raw = value.strip()
    if not raw:
        return []
    try:
        parsed = json.loads(raw)
    except json.JSONDecodeError:
        return [raw]
    if isinstance(parsed, list):
        return [item.strip() for item in parsed if isinstance(item, str) and item.strip()]
    if isinstance(parsed, str) and parsed.strip():
        return [parsed]
    return []


def serialize_image_paths(paths: list[str]) -> str:
    clean_paths = [path for path in paths if path.strip()]
    if not clean_paths:
        return ""
    return json.dumps(clean_paths)


def first_image_path(value: str) -> str:
    paths = parse_image_paths(value)
    return paths[0] if paths else ""


def copy_image_to_attachments(source_path: str) -> str:
    if not source_path.strip():
        return ""
    source = Path(source_path)
    if not source.exists():
        raise ValueError(f"Image file not found: {source}")
    config.ATTACH_DIR.mkdir(exist_ok=True)
    if source.resolve().parent == config.ATTACH_DIR.resolve():
        return str(source)
    suffix = source.suffix.lower() if source.suffix else ".png"
    target = config.ATTACH_DIR / f"log_{datetime.now().strftime('%Y%m%d_%H%M%S_%f')}{suffix}"
    if source.resolve() != target.resolve():
        shutil.copy2(source, target)
    return str(target)


def copy_images_to_attachments(source_paths: list[str]) -> str:
    copied_paths: list[str] = []
    seen_sources: set[Path] = set()
    for source_path in source_paths:
        if not source_path.strip():
            continue
        source = Path(source_path)
        try:
            resolved_source = source.resolve()
        except OSError:
            resolved_source = source
        if resolved_source in seen_sources:
            continue
        seen_sources.add(resolved_source)
        copied = copy_image_to_attachments(source_path)
        if copied and copied not in copied_paths:
            copied_paths.append(copied)
    return serialize_image_paths(copied_paths)


def copy_text_and_image_to_clipboard(text: str, image_path: str) -> bool:
    if set_windows_clipboard(text, image_path):
        return True

    with tempfile.NamedTemporaryFile("w", delete=False, suffix=".txt", encoding="utf-8") as handle:
        handle.write(text)
        text_path = Path(handle.name)
    try:
        image_script = ""
        clipboard_image = first_image_path(image_path)
        if clipboard_image and Path(clipboard_image).exists():
            image_script = f"""
$image = [System.Drawing.Image]::FromFile({ps_quote(clipboard_image)})
$bitmap = New-Object System.Drawing.Bitmap($image)
$image.Dispose()
$data.SetImage($bitmap)
"""
        script = f"""
Add-Type -AssemblyName System.Windows.Forms
Add-Type -AssemblyName System.Drawing
$text = Get-Content -LiteralPath {ps_quote(text_path)} -Raw
$data = New-Object System.Windows.Forms.DataObject
$data.SetText($text, [System.Windows.Forms.TextDataFormat]::UnicodeText)
{image_script}
[System.Windows.Forms.Clipboard]::SetDataObject($data, $true)
"""
        result = subprocess.run(
            ["powershell", "-NoProfile", "-Command", script],
            capture_output=True,
            text=True,
            timeout=10,
            check=False,
        )
        return result.returncode == 0
    finally:
        try:
            text_path.unlink()
        except OSError:
            pass


def build_individual_log_text(entry: LogEntry) -> str:
    responders = entry.responders.strip() or DEFAULT_RESPONDERS
    postal = entry.postal.strip()
    timestamp = format_log_timestamp(entry.created_at)
    if entry.kind == "vital":
        return "\n".join(
            [
                f"Timestamp: {timestamp}",
                f"Postal: {postal}",
                f"Specify: {entry.event_type}",
                f"Responder/s: {responders}",
                "Vital ss:",
            ]
        )
    return "\n".join(
        [
            f"Timestamp: {timestamp}",
            f"Type: {entry.event_type}",
            f"Postal: {postal}",
            f"Responder/s: {responders}",
            "Screenshot:",
        ]
    )


def load_card_font(size: int):
    if ImageFont is None:
        return None
    for font_path in (
        r"C:\Windows\Fonts\arial.ttf",
        r"C:\Windows\Fonts\segoeui.ttf",
    ):
        if Path(font_path).exists():
            return ImageFont.truetype(font_path, size)
    return ImageFont.load_default()


def text_size(draw, text: str, font) -> tuple[int, int]:
    box = draw.textbbox((0, 0), text, font=font)
    return box[2] - box[0], box[3] - box[1]


def build_discord_card_image(entry: LogEntry) -> Path:
    if Image is None or ImageDraw is None or ImageFont is None:
        raise RuntimeError("Pillow is required to build a Discord card.")

    config.ATTACH_DIR.mkdir(exist_ok=True)
    width = 900
    padding = 28
    line_gap = 10
    section_gap = 22
    font = load_card_font(26)
    small_font = load_card_font(20)
    text_lines = build_individual_log_text(entry).splitlines()

    measure = Image.new("RGB", (width, 100), "white")
    draw = ImageDraw.Draw(measure)
    line_height = max(text_size(draw, line or " ", font)[1] for line in text_lines) + line_gap
    text_height = (line_height * len(text_lines)) + section_gap

    prepared_images: list[tuple[Image.Image, str]] = []
    max_image_width = width - (padding * 2)
    total_image_height = 0
    for image_path in parse_image_paths(entry.image_path):
        source = Path(image_path)
        if not source.exists():
            total_image_height += 34
            prepared_images.append((None, f"Missing image: {source.name}"))
            continue
        try:
            image = Image.open(source).convert("RGB")
        except OSError:
            total_image_height += 34
            prepared_images.append((None, f"Unreadable image: {source.name}"))
            continue
        if image.width > max_image_width:
            ratio = max_image_width / image.width
            image = image.resize((max_image_width, max(1, int(image.height * ratio))))
        prepared_images.append((image, ""))
        total_image_height += image.height + section_gap

    if not prepared_images:
        total_image_height = 42

    height = padding + text_height + total_image_height + padding
    card = Image.new("RGB", (width, height), "white")
    draw = ImageDraw.Draw(card)

    y = padding
    for line in text_lines:
        draw.text((padding, y), line, fill="black", font=font)
        y += line_height
    y += section_gap // 2

    if prepared_images:
        for image, error_text in prepared_images:
            if image is None:
                draw.text((padding, y), error_text, fill="#9b1c1c", font=small_font)
                y += 34
                continue
            x = (width - image.width) // 2
            card.paste(image, (x, y))
            y += image.height + section_gap
            image.close()
    else:
        draw.text((padding, y), "No image attached.", fill="#555555", font=small_font)

    output_path = config.ATTACH_DIR / f"discord_card_{entry.id}_{datetime.now().strftime('%Y%m%d_%H%M%S_%f')}.png"
    card.save(output_path, "PNG")
    return output_path


