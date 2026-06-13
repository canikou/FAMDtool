# FAMD Tool ni Yeol

Version: 1.5.2

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
- `config.cfg` can switch response/vitals entry between simple +/- counters and detailed log capture.
- In simple mode, responses and vitals use compact side-by-side counters with direct number editing.
- History window for opening saved and recent weekly data.
- History window backup tools can export/import the current SQLite database and `config.cfg`.
- Older saved weeks show `VIEWING OLD LOGS` and require confirmation before editing.
- Export copies the weekly manual format to clipboard and saves a `.txt` file.
- Verbose event logs are written asynchronously to `logs/`.
- Startup update checks can download and run the latest GitHub Release installer.

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

## Build Release

Build a Windows distribution zip:

```powershell
.\tools\build_release.ps1
```

Or double-click/run:

```powershell
.\build_release.bat
```

Output:

- `dist/FAMDTool/FAMDTool.exe`
- `dist/FAMDTool/config.cfg`
- `dist/FAMDTool/assets/FAMDTool.ico`
- `release/FAMDTool-v1.5.2-windows.zip`
- `release/FAMDTool-v1.5.2-windows-setup.exe`

The release uses a one-folder layout so `config.cfg`, `famd_data.sqlite3`, `attachments/`, `exports/`, and `logs/` stay beside the executable. This is intentional for operational deployments where the config may need to be edited without rebuilding the app.

The setup installer is a per-user installer built with Inno Setup. It installs under `%LOCALAPPDATA%\FAMDTool`, preserves an existing `config.cfg`, and creates Start Menu shortcuts without requiring administrator rights.

## Project Structure

- `famd_tool.py` is a compatibility launcher and public re-export layer.
- `config.cfg` stores user-editable runtime settings next to the main launcher.
- `famdtool/config.py` loads paths, labels, option lists, and behavior flags from `config.cfg`.
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
- `assets/FAMDTool.ico` and `assets/FAMDTool.png` store the app icon.
- `tools/generate_icon.py` regenerates app icon assets.
- `famd_tool.spec`, `packaging/FAMDTool.iss`, and `tools/build_release.ps1` define Windows executable and installer packaging.

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
- Runtime settings are stored in `config.cfg`.
- The app repairs stale `config.cfg` version metadata on startup so preserved configs from older installs do not cause repeated update prompts.
- Database/config backups exported from History are saved as `FAMD_Backup_YYYYMMDD_HHMMSS_microseconds.zip` in `exports/`.
- Copied/pasted log images are stored in `attachments/`.
- Exported attendance text files are saved in `exports/`.
- Verbose app event logs are saved in `logs/`.
- These are intentionally ignored by git because they are local user data.

## Configuration

Edit `config.cfg` before launching the app:

- `logging.verbose_event_logs`: set to `false` to disable JSON event log files under `logs/`.
- `workflow.non_detailed_logs`: set to `true` for quick stat tracking and manual attendance export. Response/vitals controls become simple increment/decrement buttons, while detailed fields stay hidden.
- Set `workflow.non_detailed_logs` to `false` for department-workflow style detailed response/vitals capture with postal, type, responders, notes, and attachments.
- Simple mode still writes normal blank log rows, so setting it back to `false` later makes those rows visible and editable.
- `types.response` and `types.vital`: comma-separated button options for detailed log entry.
- `paths.icon`: icon file used by the app window.
- `updates.enabled`: enables/disables startup update checks.
- `updates.latest_api_url`: GitHub Releases API endpoint used for update metadata.
- `updates.asset_pattern`: installer asset name pattern. Keep this compatible with release assets, e.g. `FAMDTool-v{version}-windows-setup.exe`.

## Updating And Releases

This app checks GitHub Releases for a newer version on startup. For update checks to work without bundling a private token, the repository or at least the release metadata/assets must be publicly readable. The current updater expects the latest release to include:

- `FAMDTool-vX.Y.Z-windows-setup.exe`
- `FAMDTool-vX.Y.Z-windows.zip`

Release steps for future agents:

1. Update version values in `config.cfg`, `famdtool/config.py`, `packaging/version_info.txt`, `tools/build_release.ps1`, tests, and README.
2. Keep the installer asset name compatible with `updates.asset_pattern`.
3. Run `.\tools\build_release.ps1`.
4. Launch-test `dist\FAMDTool\FAMDTool.exe`.
5. Commit, tag `vX.Y.Z`, push, and create a GitHub Release with both the setup exe and portable zip.

Windows installer best practices used here:

- Per-user install under `%LOCALAPPDATA%` to avoid admin rights.
- Preserve `config.cfg` on upgrades with `onlyifdoesntexist`.
- Do not package user data files like `famd_data.sqlite3`.
- Keep app data folders stable beside the installed executable.
- Embed the app icon in both the exe and installer.
- Prefer signed installers for wider department deployment.

Linux and macOS release recommendations:

- Build on each target OS in CI; do not cross-build from Windows.
- Linux: ship an AppImage for portable use, and optionally `.deb`/`.rpm` packages for managed installs.
- macOS: ship a signed and notarized `.dmg` or `.pkg`; unsigned apps will be blocked or heavily warned by Gatekeeper.
- Keep the updater platform-aware before enabling it outside Windows; each OS should download a native installer/package asset.
- Use GitHub Actions matrix builds once release volume grows.
