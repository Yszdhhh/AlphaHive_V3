"""Regression tests for the additive CoinGlass/Binance canonical adapters."""
from __future__ import annotations

import pandas as pd
import pytest

from harness.lib.canonical_data import (
    CanonicalSchemaError,
    canonicalize_funding,
    canonicalize_klines,
    canonicalize_oi,
    canonicalize_taker,
)


def test_klines_map_to_same_field_names_without_source_switch() -> None:
    cg = pd.DataFrame({
        "_symbol": ["BTCUSDT"], "open_time": [1780000000000],
        "open": [100.0], "high": [101.0], "low": [99.0], "close": [100.5],
        "volume": [10.0], "quote_volume": [1000.0], "taker_buy_volume": [5.0],
    })
    bn = pd.DataFrame({
        "symbol": ["BTCUSDT"], "open_time": [1780000000000],
        "open": [100.0], "high": [101.0], "low": [99.0], "close": [100.5],
        "volume": [10.0], "quote_volume": [1000.0], "taker_buy_vol": [5.0],
    })

    cg_out = canonicalize_klines(cg, "coinglass")
    bn_out = canonicalize_klines(bn, "binance")

    assert cg_out.loc[0, "taker_buy_volume"] == bn_out.loc[0, "taker_buy_volume"] == 5.0
    assert cg_out.loc[0, "source"] == "coinglass"
    assert bn_out.loc[0, "source"] == "binance"


def test_verified_binance_kline_fields_map_without_legacy_field_guessing() -> None:
    frame = pd.DataFrame({
        "symbol": ["BTCUSDT"], "open_time": [1_780_000_000_000],
        "open": [100.0], "high": [101.0], "low": [99.0], "close": [100.5],
        "volume": [10.0], "close_time": [1_780_003_599_999],
        "quote_volume": [1_005.0], "trades": [12],
        "taker_buy_vol": [5.0], "taker_buy_quote_vol": [502.5],
        "turnover_usd": [1_005.0],
    })

    out = canonicalize_klines(frame, "binance")

    assert out.loc[0, "quote_volume"] == pytest.approx(1_005.0)
    assert out.loc[0, "turnover_usd"] == pytest.approx(1_005.0)
    assert "quote_asset_volume" not in out.columns


@pytest.mark.parametrize(
    ("frame", "message"),
    [
        (
            pd.DataFrame({
                "symbol": ["BTCUSDT"], "open_time": [1_780_000_000_000],
                "open": [100.0], "high": [99.0], "low": [98.0], "close": [100.0], "volume": [1.0],
            }),
            "inconsistent OHLC",
        ),
        (
            pd.DataFrame({
                "symbol": ["BTCUSDT"], "open_time": [1_780_000_000_000],
                "open": [100.0], "high": [101.0], "low": [99.0], "close": [float("inf")], "volume": [1.0],
            }),
            "non-numeric",
        ),
        (
            pd.DataFrame({
                "symbol": ["BTCUSDT", "BTCUSDT"], "open_time": [1_780_000_000_000, 1_780_000_000_000],
                "open": [100.0, 100.0], "high": [101.0, 101.0], "low": [99.0, 99.0], "close": [100.0, 100.0], "volume": [1.0, 1.0],
            }),
            "duplicate symbol/timestamp",
        ),
    ],
)
def test_klines_fail_closed_for_malformed_or_duplicate_rows(frame: pd.DataFrame, message: str) -> None:
    with pytest.raises(CanonicalSchemaError, match=message):
        canonicalize_klines(frame, "binance")


def test_funding_preserves_decimal_and_contract_percent_views() -> None:
    cg = canonicalize_funding(pd.DataFrame({"_symbol": ["BTCUSDT"], "time": [1780000000000], "close": [0.0041725]}), "coinglass")
    bn = canonicalize_funding(pd.DataFrame({"symbol": ["BTCUSDT"], "fundingTime": [1780000000000], "fundingRate_raw": [0.0041725], "fundingRate_decimal": [4.1725e-05]}), "binance")

    assert cg.loc[0, "funding_rate_decimal"] == pytest.approx(4.1725e-05)
    assert bn.loc[0, "funding_rate_decimal"] == pytest.approx(4.1725e-05)
    assert bn.loc[0, "funding_rate_raw_percent"] == pytest.approx(0.0041725)
    assert bn.loc[0, "source_unit"] == "decimal_with_percent_raw"


def test_funding_equal_raw_decimal_columns_are_marked_as_aliases() -> None:
    frame = pd.DataFrame({
        "symbol": ["BTCUSDT"], "fundingTime": [1780000000000],
        "fundingRate_raw": [4.1725e-05], "fundingRate_decimal": [4.1725e-05],
    })
    out = canonicalize_funding(frame, "binance")
    assert out.loc[0, "funding_rate_decimal"] == pytest.approx(4.1725e-05)
    assert out.loc[0, "funding_rate_raw_percent"] == pytest.approx(0.0041725)
    assert out.loc[0, "source_unit"] == "decimal_alias_columns"


def test_funding_rejects_disagreeing_binance_unit_columns() -> None:
    frame = pd.DataFrame({
        "symbol": ["BTCUSDT"], "fundingTime": [1780000000000],
        "fundingRate_raw": [0.004], "fundingRate_decimal": [0.0002],
    })
    with pytest.raises(CanonicalSchemaError, match="disagree"):
        canonicalize_funding(frame, "binance")


def test_oi_unit_remains_undeclared_for_both_sources() -> None:
    cg = canonicalize_oi(pd.DataFrame({"_symbol": ["BTCUSDT"], "time": [1780000000000], "close": [100.0]}), "coinglass")
    bn = canonicalize_oi(pd.DataFrame({"symbol": ["BTCUSDT"], "timestamp": [1780000000000], "sumOpenInterest": [100.0], "sumOpenInterestValue": [1000.0]}), "binance")
    assert cg.loc[0, "absolute_unit_status"] == "UNDECLARED"
    assert bn.loc[0, "absolute_unit_status"] == "UNDECLARED"


def test_taker_ratio_provenance_is_explicit() -> None:
    cg = canonicalize_taker(pd.DataFrame({"_symbol": ["BTCUSDT"], "time": [1780000000000], "taker_buy_volume_usd": [120.0], "taker_sell_volume_usd": [100.0]}), "coinglass")
    bn = canonicalize_taker(pd.DataFrame({"symbol": ["BTCUSDT"], "timestamp": [1780000000000], "buySellRatio": [1.2], "buyVol": [12.0], "sellVol": [10.0]}), "binance")
    assert cg.loc[0, "taker_buy_sell_ratio"] == pytest.approx(1.2)
    assert cg.loc[0, "ratio_source"] == "derived_from_buy_sell"
    assert bn.loc[0, "ratio_source"] == "source"
