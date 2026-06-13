# FAMD Tool ni Yeol

Simple Python desktop app for tracking EMS attendance, responses, vitals, and weekly manual attendance exports.

## Features

- One-button time in/time out with automatic total calculation.
- Manual shift entry and editing, including previous days.
- Alarm-style shift time controls with bounded hour/minute fields and AM/PM buttons.
- Overnight shifts are split at the manual attendance boundary.
- Robbery/distress and vitals logs with direct type buttons.
- Persistent responder name field for log exports.
- Optional multiple image attachments for response and vitals logs.
- Attached images are copied into `attachments/` so logs survive if the original file is deleted.
- Ctrl+V in the log prompt attaches clipboard images, with a preview and remove button before saving.
- Individual logs support a two-step Discord flow: `Copy Log Details` for text, then `Copy Image` for the first attached screenshot.
- History window for opening saved and recent weekly data.
- Export copies the weekly manual format to clipboard and saves a `.txt` file.
- Verbose event logs are written asynchronously to `logs/`.

## Setup

Create and use the local virtual environment:

```powershell
python -m venv .venv
.\.venv\Scripts\Activate.ps1
python -m pip install --upgrade pip
```

The runner installs dependencies into `.venv` when needed. Pillow is used for faster clipboard image paste/export.

## Run

```powershell
.\.venv\Scripts\python.exe famd_tool.py
```

For quick testing on Windows, double-click `run.bat` or run:

```powershell
.\run.bat
```

## Project Structure

- `famd_tool.py` is a compatibility launcher and public re-export layer.
- `famdtool/config.py` stores paths, labels, and fixed option lists.
- `famdtool/models.py` stores shared dataclasses.
- `famdtool/time_utils.py` stores date/time parsing, formatting, and shift splitting.
- `famdtool/attachments.py` stores clipboard, image, and Discord-card helpers.
- `famdtool/database.py` stores SQLite persistence.
- `famdtool/event_log.py` stores async verbose event logging.
- `famdtool/reports.py` stores weekly totals and manual export generation.
- `famdtool/tasks.py` stores Tk-safe background task dispatch.
- `famdtool/image_preview.py` stores thumbnail loading for UI previews.
- `famdtool/windowing.py` stores popup placement helpers.
- `famdtool/dialogs.py` stores modal input dialogs and reusable time controls.
- `famdtool/managers.py` stores shift/log/history manager windows and log detail views.
- `famdtool/main_window.py` stores the main Tkinter app window and launcher.
- `famdtool/app.py` re-exports UI classes for compatibility.

## Test

```powershell
.\.venv\Scripts\python.exe -m unittest discover -s tests
```

Optional Tk smoke tests are disabled by default. Run them manually with:

```powershell
$env:FAMD_RUN_GUI_TESTS='1'
.\.venv\Scripts\python.exe -m unittest tests.test_ui_smoke -v
```

## Data

- Persistent app data is stored in `famd_data.sqlite3`.
- Copied/pasted log images are stored in `attachments/`.
- Exported attendance text files are saved in `exports/`.
- Verbose app event logs are saved in `logs/`.
- These are intentionally ignored by git because they are local user data.
