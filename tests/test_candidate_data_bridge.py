"""Tests for the non-active Binance-preferred candidate price bridge."""
from __future__ import annotations

import pandas as pd
import pytest

from harness.lib.candidate_data_bridge import CandidateBridgeError, HOUR_MS, build_price_snapshot


BASE = 1_780_000_000_000


def _binance(times: list[int], closes: list[float]) -> pd.DataFrame:
    return pd.DataFrame({
        "symbol": ["BTCUSDT"] * len(times), "open_time": times,
        "open": [100.0] * len(times), "high": [110.0] * len(times),
        "low": [90.0] * len(times), "close": closes, "volume": [10.0] * len(times),
        "quote_volume": [1_000.0] * len(times), "turnover_usd": [1_000.0] * len(times),
    })


def _coinglass(times: list[int], closes: list[float]) -> pd.DataFrame:
    return pd.DataFrame({
        "_symbol": ["BTCUSDT"] * len(times), "open_time": times,
        "open": [100.0] * len(times), "high": [110.0] * len(times),
        "low": [90.0] * len(times), "close": closes, "volume": [10.0] * len(times),
        "quote_volume": [1_000.0] * len(times),
    })


def test_binance_wins_overlap_and_conflict_remains_auditable() -> None:
    snapshot = build_price_snapshot(
        symbol="BTCUSDT",
        binance_klines=_binance([BASE, BASE + HOUR_MS], [101.0, 102.0]),
        coinglass_klines=_coinglass([BASE - HOUR_MS, BASE], [99.0, 99.0]),
    )

    assert snapshot.rows["close"].tolist() == [99.0, 101.0, 102.0]
    assert snapshot.rows["price_source"].tolist() == ["coinglass", "binance", "binance"]
    assert snapshot.manifest["price_precedence"] == "BINANCE_OVER_COINGLASS"
    assert snapshot.manifest["overlap_conflict_count"] == 1
    assert snapshot.manifest["gap_status"] == "CONTIGUOUS"


def test_gap_is_exposed_without_interpolation_or_publication() -> None:
    snapshot = build_price_snapshot(
        symbol="BTCUSDT",
        binance_klines=_binance([BASE, BASE + 2 * HOUR_MS], [101.0, 103.0]),
        coinglass_klines=None,
    )

    assert snapshot.rows["timestamp"].tolist() == [BASE, BASE + 2 * HOUR_MS]
    assert snapshot.manifest["gap_intervals"][0]["missing_bars"] == 1
    assert snapshot.manifest["publication_status"] == "PREPARATION_ONLY_NO_ACTIVE_SCANNER_SWITCH"


def test_only_completed_bars_are_retained() -> None:
    snapshot = build_price_snapshot(
        symbol="BTCUSDT",
        binance_klines=_binance([BASE, BASE + HOUR_MS], [101.0, 102.0]),
        coinglass_klines=None,
        effective_cutoff_ms=BASE + 2 * HOUR_MS,
    )

    assert snapshot.rows["timestamp"].tolist() == [BASE, BASE + HOUR_MS]


def test_no_completed_rows_fails_closed() -> None:
    with pytest.raises(CandidateBridgeError, match="no_completed_price_rows"):
        build_price_snapshot(
            symbol="BTCUSDT",
            binance_klines=_binance([BASE], [101.0]),
            coinglass_klines=None,
            effective_cutoff_ms=BASE,
        )
