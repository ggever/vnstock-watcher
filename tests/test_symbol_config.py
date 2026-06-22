from app.core.symbol_config import SymbolConfig, normalize_side, clean_symbol


def test_normalize_side_maps_legacy_codes():
    assert normalize_side("BU") == "Mua"
    assert normalize_side("SD") == "Bán"
    assert normalize_side("BOTH") == "Cả hai"


def test_normalize_side_defaults_to_both_when_invalid():
    assert normalize_side("garbage") == "Cả hai"
    assert normalize_side("") == "Cả hai"


def test_normalize_side_passthrough_valid():
    assert normalize_side("Mua") == "Mua"
    assert normalize_side("Bán") == "Bán"


def test_clean_symbol_upper_and_strip():
    assert clean_symbol("  vnm ") == "VNM"
