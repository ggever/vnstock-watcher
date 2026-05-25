from __future__ import annotations

import subprocess
import sys
from datetime import datetime, timedelta
from pathlib import Path
from typing import Callable

import requests
from packaging.version import Version

from config import AppConfig, save_config
from paths import data_dir
from version import __version__


GITHUB_REPO: str | None = None


class UpdateUnavailable(RuntimeError):
    pass


def should_auto_check(config: AppConfig) -> bool:
    if not GITHUB_REPO:
        return False
    if not config.last_update_check:
        return True
    try:
        last_check = datetime.fromisoformat(config.last_update_check)
    except ValueError:
        return True
    return datetime.now() - last_check >= timedelta(hours=24)


def mark_checked(config: AppConfig) -> None:
    config.last_update_check = datetime.now().replace(microsecond=0).isoformat()
    save_config(config)


def check_update() -> tuple[str, str] | None:
    if not GITHUB_REPO:
        raise UpdateUnavailable("Chưa cấu hình GitHub repo cho auto-update.")

    response = requests.get(
        f"https://api.github.com/repos/{GITHUB_REPO}/releases/latest",
        timeout=10,
    )
    response.raise_for_status()
    release = response.json()
    latest = Version(str(release["tag_name"]).lstrip("v"))
    current = Version(__version__)
    if latest <= current:
        return None

    for asset in release.get("assets", []):
        name = str(asset.get("name", ""))
        if name.lower().endswith(".exe"):
            return str(latest), str(asset["browser_download_url"])

    raise UpdateUnavailable("Release mới không có file .exe.")


ProgressCallback = Callable[[int, int], None]


def download_and_swap(url: str, progress_callback: ProgressCallback | None = None) -> None:
    if not getattr(sys, "frozen", False):
        raise UpdateUnavailable("Chỉ cập nhật tự động khi đang chạy bản .exe.")

    exe_path = Path(sys.executable).resolve()
    new_path = exe_path.with_suffix(exe_path.suffix + ".new")
    batch_path = data_dir() / "updater.bat"

    try:
        with requests.get(url, stream=True, timeout=30) as response:
            response.raise_for_status()
            total = int(response.headers.get("content-length", 0) or 0)
            downloaded = 0
            with new_path.open("wb") as handle:
                for chunk in response.iter_content(chunk_size=1024 * 512):
                    if not chunk:
                        continue
                    handle.write(chunk)
                    downloaded += len(chunk)
                    if progress_callback:
                        progress_callback(downloaded, total)
    except Exception:
        if new_path.exists():
            new_path.unlink()
        raise

    batch_path.write_text(
        "\r\n".join(
            [
                "@echo off",
                "timeout /t 2 /nobreak > nul",
                f':waitloop',
                f'tasklist /fi "imagename eq {exe_path.name}" | find /i "{exe_path.name}" > nul',
                "if not errorlevel 1 (",
                "  timeout /t 1 /nobreak > nul",
                "  goto waitloop",
                ")",
                f'move /y "{new_path}" "{exe_path}"',
                f'start "" "{exe_path}"',
                f'del "%~f0"',
            ]
        ),
        encoding="utf-8",
    )
    subprocess.Popen(
        ["cmd", "/c", str(batch_path)],
        cwd=str(data_dir()),
        creationflags=subprocess.CREATE_NEW_CONSOLE,
    )
