from __future__ import annotations

from pathlib import Path
from typing import Callable

from paths import resource_path


def build_tray(gui, monitor, quit_callback: Callable[[], None]):
    try:
        import pystray
        from PIL import Image, ImageDraw
    except Exception:
        return None

    def show_window(_icon=None, _item=None):
        gui.run_on_ui(gui.show)

    def start_monitor(_icon=None, _item=None):
        gui.run_on_ui(gui.start_monitoring)

    def stop_monitor(_icon=None, _item=None):
        gui.run_on_ui(gui.stop_monitoring)

    def quit_app(_icon=None, _item=None):
        gui.run_on_ui(quit_callback)

    icon = pystray.Icon(
        "VNStockWatcher",
        _load_icon(Image, ImageDraw),
        "VNStock Watcher",
        pystray.Menu(
            pystray.MenuItem("Hiện cửa sổ", show_window),
            pystray.Menu.SEPARATOR,
            pystray.MenuItem("Start", start_monitor, enabled=lambda item: not monitor.running),
            pystray.MenuItem("Stop", stop_monitor, enabled=lambda item: monitor.running),
            pystray.Menu.SEPARATOR,
            pystray.MenuItem("Thoát", quit_app),
        ),
    )
    icon.run_detached()
    return icon


def _load_icon(image_module, draw_module):
    icon_path = resource_path("assets/icon.ico")
    if Path(icon_path).exists():
        return image_module.open(icon_path)

    image = image_module.new("RGBA", (64, 64), "#0f766e")
    draw = draw_module.Draw(image)
    draw.rectangle((10, 12, 54, 52), outline="white", width=3)
    draw.line((16, 42, 28, 30, 38, 36, 50, 20), fill="white", width=4)
    return image
