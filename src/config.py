from __future__ import annotations

import json
from dataclasses import asdict, dataclass, field
from datetime import datetime
from pathlib import Path
from typing import Any

from paths import data_dir


VALID_SIDES = {"Mua", "Bán", "Cả hai"}
_SIDE_COMPAT = {"BU": "Mua", "SD": "Bán", "Both": "Cả hai", "BOTH": "Cả hai"}


@dataclass
class SymbolConfig:
    symbol: str
    threshold: int
    side: str = "Cả hai"


@dataclass
class AppConfig:
    interval: int = 10
    auto_minimize_on_start: bool = True
    start_with_windows: bool = False
    last_update_check: str | None = None
    symbols: list[SymbolConfig] = field(default_factory=list)


def config_path() -> Path:
    return data_dir() / "config.json"


def default_config() -> AppConfig:
    return AppConfig(
        interval=10,
        auto_minimize_on_start=True,
        start_with_windows=False,
        last_update_check=None,
        symbols=[],
    )


def load_config() -> AppConfig:
    path = config_path()
    if not path.exists():
        config = default_config()
        save_config(config)
        return config

    try:
        raw = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return default_config()

    return parse_config(raw)


def parse_config(raw: dict[str, Any]) -> AppConfig:
    interval = _positive_int(raw.get("interval"), 10)
    symbols = []
    for item in raw.get("symbols", []):
        symbol = str(item.get("symbol", "")).strip().upper()
        threshold = _positive_int(item.get("threshold"), 0)
        side = str(item.get("side", "Cả hai")).strip()
        side = _SIDE_COMPAT.get(side, side)
        if side not in VALID_SIDES:
            side = "Cả hai"
        if symbol and threshold > 0:
            symbols.append(SymbolConfig(symbol=symbol, threshold=threshold, side=side))

    last_update_check = raw.get("last_update_check")
    if last_update_check is not None:
        try:
            datetime.fromisoformat(str(last_update_check))
        except ValueError:
            last_update_check = None

    return AppConfig(
        interval=max(3, interval),
        auto_minimize_on_start=bool(raw.get("auto_minimize_on_start", True)),
        start_with_windows=bool(raw.get("start_with_windows", False)),
        last_update_check=last_update_check,
        symbols=symbols,
    )


def save_config(config: AppConfig) -> None:
    path = config_path()
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        json.dumps(_to_json(config), ensure_ascii=False, indent=2),
        encoding="utf-8",
    )


def _to_json(config: AppConfig) -> dict[str, Any]:
    data = asdict(config)
    data["symbols"] = [asdict(symbol) for symbol in config.symbols]
    return data


def _positive_int(value: Any, fallback: int) -> int:
    try:
        parsed = int(value)
    except (TypeError, ValueError):
        return fallback
    return parsed if parsed > 0 else fallback
