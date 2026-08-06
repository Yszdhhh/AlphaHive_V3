"""Regression tests for the local versioned canonical price publisher."""
from __future__ import annotations

import json

import pandas as pd
import pytest

from harness.lib.canonical_price_snapshot import (
    CanonicalPriceSnapshotError,
    HOUR_MS,
    evaluate_gap_policy,
    load_current_price_snapshot,
    publish_price_snapshot,
)


BASE = 1_780_000_000_000


def _rows() -> pd.DataFrame:
    return pd.DataFrame({
        "timestamp": [BASE, BASE + HOUR_MS], "open": [100.0, 101.0],
        "high": [101.0, 102.0], "low": [99.0, 100.0], "close": [100.5, 101.5],
        "volume": [10.0, 12.0], "turnover_usd": [1000.0, 1200.0],
        "symbol": ["BTCUSDT", "BTCUSDT"], "price_source": ["binance", "binance"],
    })


def _manifest(gaps: list[dict] | None = None) -> dict:
    return {"latest_timestamp_ms": BASE + 100 * HOUR_MS, "gap_intervals": gaps or []}


def test_gap_policy_warns_only_for_bounded_old_gap() -> None:
    decision = evaluate_gap_policy(_manifest([{
        "after_timestamp_ms": BASE, "before_timestamp_ms": BASE + 5 * HOUR_MS, "missing_bars": 4,
    }]))
    assert decision["status"] == "HISTORICAL_GAP_WARNING"


def test_gap_policy_blocks_fresh_or_excessive_gap() -> None:
    fresh = evaluate_gap_policy(_manifest([{
        "after_timestamp_ms": BASE + 99 * HOUR_MS, "before_timestamp_ms": BASE + 101 * HOUR_MS, "missing_bars": 1,
    }]))
    excessive = evaluate_gap_policy(_manifest([{
        "after_timestamp_ms": BASE, "before_timestamp_ms": BASE + 6 * HOUR_MS, "missing_bars": 5,
    }]))
    assert fresh["reason"] == "FRESH_GAP"
    assert excessive["reason"] == "GAP_EXCEEDS_MAXIMUM"


def test_published_snapshot_is_hash_checked_and_tamper_fails_closed(tmp_path) -> None:
    pointer = publish_price_snapshot({"BTCUSDT": (_rows(), _manifest())}, root=tmp_path, published_at_utc="2026-07-18T00:00:00Z")
    loaded, manifest = load_current_price_snapshot(root=tmp_path)
    assert pointer["version"] == "v0001"
    assert manifest["files"]["BTCUSDT"]["rows"] == 2
    assert loaded["price_source"].tolist() == ["binance", "binance"]

    path = tmp_path / "v0001" / "klines" / "BTCUSDT.parquet"
    path.write_bytes(b"tampered")
    with pytest.raises(CanonicalPriceSnapshotError, match="kline_hash_mismatch"):
        load_current_price_snapshot(root=tmp_path)


def test_second_publish_into_same_root_increments_version(tmp_path) -> None:
    """The publish lock must release cleanly so a later publish can succeed."""
    first = publish_price_snapshot({"BTCUSDT": (_rows(), _manifest())}, root=tmp_path, published_at_utc="2026-07-18T00:00:00Z")
    second = publish_price_snapshot({"BTCUSDT": (_rows(), _manifest())}, root=tmp_path, published_at_utc="2026-07-26T00:00:00Z")
    assert first["version"] == "v0001"
    assert second["version"] == "v0002"
    _, manifest = load_current_price_snapshot(root=tmp_path)
    assert manifest["version"] == "v0002"
    assert manifest["published_at_utc"] == "2026-07-26T00:00:00Z"


def test_blocked_gap_cannot_be_published(tmp_path) -> None:
    with pytest.raises(CanonicalPriceSnapshotError, match="blocked_symbol_snapshot"):
        publish_price_snapshot({"BTCUSDT": (_rows(), _manifest([{
            "after_timestamp_ms": BASE + 99 * HOUR_MS,
            "before_timestamp_ms": BASE + 101 * HOUR_MS,
            "missing_bars": 1,
        }]))}, root=tmp_path)
