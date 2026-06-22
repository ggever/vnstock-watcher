import pandas as pd
from app.core.ticks import normalize_ticks, filter_big_orders, page_size_for_interval


def _raw(rows):
    return pd.DataFrame(rows)


def test_normalize_maps_match_type_and_types():
    raw = _raw([
        {"time": "2026-06-22 09:15:00", "volume": "1000", "price": "10.5", "match_type": "BU"},
        {"time": "2026-06-22 09:16:00", "volume": "2000", "price": "11", "match_type": "SD"},
    ])
    out = normalize_ticks(raw)
    assert list(out["match_type"]) == ["Mua", "Bán"]
    assert out["volume"].tolist() == [1000, 2000]
    assert "_sort_time" in out.columns
    assert out["_sort_time"].is_monotonic_increasing


def test_filter_big_orders_threshold_and_side():
    ticks = normalize_ticks(_raw([
        {"time": "2026-06-22 09:15:00", "volume": "1000", "price": "10", "match_type": "BU"},
        {"time": "2026-06-22 09:16:00", "volume": "5000", "price": "10", "match_type": "BU"},
        {"time": "2026-06-22 09:17:00", "volume": "9000", "price": "10", "match_type": "SD"},
    ]))
    both = filter_big_orders(ticks, threshold=3000, side="Cả hai")
    assert both["volume"].tolist() == [5000, 9000]
    buy_only = filter_big_orders(ticks, threshold=3000, side="Mua")
    assert buy_only["volume"].tolist() == [5000]


def test_page_size_scales_with_interval():
    assert page_size_for_interval(5) == 100
    assert page_size_for_interval(60) == 600
