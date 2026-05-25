from __future__ import annotations

import argparse
import sys
from pathlib import Path


CURRENT_DIR = Path(__file__).resolve().parent
if str(CURRENT_DIR) not in sys.path:
    sys.path.insert(0, str(CURRENT_DIR))

from gui import AppWindow
from tray import build_tray


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="VNStock big-order watcher")
    parser.add_argument("--tray", action="store_true", help="Start hidden in the system tray")
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    app = AppWindow(start_hidden=args.tray)
    tray_icon = build_tray(app, app.monitor, app.quit_app)
    app.set_tray_icon(tray_icon)
    if tray_icon is None:
        app.protocol("WM_DELETE_WINDOW", app.quit_app)
    if args.tray and tray_icon is None:
        app.show()
    app.mainloop()


if __name__ == "__main__":
    main()
