from __future__ import annotations

from dataclasses import dataclass

VALID_SIDES = {"Mua", "Bán", "Cả hai"}
_SIDE_COMPAT = {"BU": "Mua", "SD": "Bán", "Both": "Cả hai", "BOTH": "Cả hai"}


@dataclass
class SymbolConfig:
    symbol: str
    threshold: int
    side: str = "Cả hai"


def normalize_side(value: str) -> str:
    side = str(value or "").strip()
    side = _SIDE_COMPAT.get(side, side)
    return side if side in VALID_SIDES else "Cả hai"


def clean_symbol(value: str) -> str:
    return str(value or "").strip().upper()
