from __future__ import annotations

import json
import subprocess
import tempfile
import urllib.request
from dataclasses import dataclass
from pathlib import Path
from urllib.error import HTTPError, URLError

from . import config


@dataclass(frozen=True)
class UpdateInfo:
    version: str
    tag_name: str
    name: str
    asset_name: str
    asset_url: str
    release_url: str


def version_tuple(value: str) -> tuple[int, ...]:
    cleaned = value.strip().lstrip("vV")
    parts: list[int] = []
    for raw_part in cleaned.split("."):
        number = ""
        for char in raw_part:
            if char.isdigit():
                number += char
            else:
                break
        parts.append(int(number or "0"))
    return tuple(parts)


def is_newer_version(candidate: str, current: str) -> bool:
    candidate_parts = version_tuple(candidate)
    current_parts = version_tuple(current)
    size = max(len(candidate_parts), len(current_parts))
    candidate_parts += (0,) * (size - len(candidate_parts))
    current_parts += (0,) * (size - len(current_parts))
    return candidate_parts > current_parts


def check_for_update() -> UpdateInfo | None:
    if not config.UPDATES_ENABLED:
        return None
    try:
        release = fetch_latest_release()
    except (HTTPError, URLError, TimeoutError, OSError, json.JSONDecodeError):
        return None
    tag_name = str(release.get("tag_name", ""))
    latest_version = tag_name.lstrip("vV")
    if not latest_version or not is_newer_version(latest_version, config.APP_VERSION):
        return None
    asset = select_update_asset(release, latest_version)
    if asset is None:
        return None
    return UpdateInfo(
        version=latest_version,
        tag_name=tag_name,
        name=str(release.get("name") or tag_name),
        asset_name=str(asset["name"]),
        asset_url=str(asset["browser_download_url"]),
        release_url=str(release.get("html_url", "")),
    )


def fetch_latest_release() -> dict:
    request = urllib.request.Request(
        config.UPDATE_LATEST_API_URL,
        headers={
            "Accept": "application/vnd.github+json",
            "User-Agent": f"FAMDTool/{config.APP_VERSION}",
        },
    )
    with urllib.request.urlopen(request, timeout=8) as response:
        return json.loads(response.read().decode("utf-8"))


def select_update_asset(release: dict, version: str) -> dict | None:
    assets = release.get("assets", [])
    wanted_name = config.UPDATE_ASSET_PATTERN.format(version=version)
    for asset in assets:
        if asset.get("name") == wanted_name and asset.get("browser_download_url"):
            return asset
    for asset in assets:
        name = str(asset.get("name", "")).lower()
        if name.endswith("-setup.exe") and asset.get("browser_download_url"):
            return asset
    return None


def download_update(update: UpdateInfo) -> Path:
    target_dir = Path(tempfile.gettempdir()) / "FAMDToolUpdates"
    target_dir.mkdir(parents=True, exist_ok=True)
    target_path = target_dir / update.asset_name
    request = urllib.request.Request(
        update.asset_url,
        headers={"User-Agent": f"FAMDTool/{config.APP_VERSION}"},
    )
    with urllib.request.urlopen(request, timeout=60) as response:
        target_path.write_bytes(response.read())
    return target_path


def run_installer(path: Path) -> None:
    args = [str(path)]
    if config.UPDATE_SILENT_INSTALL:
        args.extend(config.UPDATE_INSTALLER_ARGS)
    subprocess.Popen(args, close_fds=True)
