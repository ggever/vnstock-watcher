from __future__ import annotations

import os
import sys
from pathlib import Path


SHORTCUT_NAME = "VNStockWatcher.lnk"


def startup_shortcut_path() -> Path:
    appdata = Path(os.environ["APPDATA"])
    return appdata / "Microsoft" / "Windows" / "Start Menu" / "Programs" / "Startup" / SHORTCUT_NAME


def is_enabled() -> bool:
    return startup_shortcut_path().exists()


def enable() -> None:
    if not getattr(sys, "frozen", False):
        return

    import win32com.client

    shortcut_path = startup_shortcut_path()
    shortcut_path.parent.mkdir(parents=True, exist_ok=True)
    shell = win32com.client.Dispatch("WScript.Shell")
    shortcut = shell.CreateShortcut(str(shortcut_path))
    shortcut.TargetPath = sys.executable
    shortcut.Arguments = "--tray"
    shortcut.WorkingDirectory = str(Path(sys.executable).resolve().parent)
    shortcut.IconLocation = sys.executable
    shortcut.save()


def disable() -> None:
    shortcut_path = startup_shortcut_path()
    if shortcut_path.exists():
        shortcut_path.unlink()
