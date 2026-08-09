"""Regression tests for the contract anomaly feature layer (Phase 1)."""
from __future__ import annotations

import numpy as np
import pandas as pd
import pytest

from harness.lib.contract_anomaly_features import (
    DIMENSION_LAYOUT,
    FeatureWindow,
    _sanitize_close,
    build_feature_table,
    rolling_rank,
    rolling_z,
    sign_streak,
)

HOUR_MS = 3_600_000


def _ts(n: int, start: int = 1_700_000_000_000) -> np.ndarray:
    return start + np.arange(n, dtype=np.int64) * HOUR_MS


def _frame(ts: np.ndarray, cols: dict[str, list]) -> pd.DataFrame:
    out = {"timestamp": ts}
    out.update(cols)
    return pd.DataFrame(out)


def test_rolling_z_centered_on_constant_then_spike():
    n = 2000
    vals = np.full(n, 10.0)
    vals[-1] = 12.0  # 最终点 +20%
    s = pd.Series(vals)
    z = rolling_z(s, window=100, min_periods=50)
    assert np.isnan(z.iloc[49])  # 常数段 std=0 → NaN（非 0，防除零）
    assert np.isnan(z.iloc[50])
    assert np.isnan(z.iloc[-2])  # 尾窗前最后一个点仍是全常数窗
    assert z.iloc[-1] > 5.0  # 尖峰应有大 z（窗口含 1 个 spike + 99 个常数）


def test_rolling_z_constant_series_gives_nan():
    s = pd.Series(np.full(500, 5.0))
    z = rolling_z(s, window=100, min_periods=50)
    assert z.tail(100).isna().all()  # std=0 → NaN，防止除零


def test_rolling_rank_bounds_and_direction():
    n = 2000
    vals = np.arange(n, dtype=float)  # 单调递增 → 当前值恒为窗口内最大
    s = pd.Series(vals)
    r = rolling_rank(s, window=100, min_periods=50)
    assert r.tail(500).between(0.99, 1.0).all()
    decreasing = pd.Series(np.arange(n, dtype=float)[::-1])
    r2 = rolling_rank(decreasing, window=100, min_periods=50)
    assert r2.tail(500).between(0.0, 0.01).all()


def test_sign_streak_positive_negative_reset():
    s = pd.Series([1.0, 1.0, -1.0, -1.0, -1.0, 0.0, 1.0, -1.0, -1.0])
    streak = sign_streak(s)
    assert streak.tolist() == [1.0, 2.0, -1.0, -2.0, -3.0, 0.0, 1.0, -1.0, -2.0]


def test_sign_streak_nan_resets():
    s = pd.Series([1.0, np.nan, 1.0, 1.0])
    streak = sign_streak(s)
    assert streak.tolist()[:2] == [1.0, 0.0]
    assert streak.tolist()[2:] == [1.0, 2.0]


def _make_dims(n: int = 3000, start: int = 1_700_000_000_000) -> dict[str, pd.DataFrame]:
    ts = _ts(n, start)
    close = 100.0 + np.sin(np.arange(n) / 50.0) * 2.0
    rng = np.random.default_rng(42)
    short_liq = np.zeros(n)
    short_liq[n // 2] = 5_000_000.0  # 单点强平尖峰
    long_liq = rng.uniform(0, 100_000, n)
    cum_delta = np.cumsum(rng.normal(0, 1, n))
    top_ratio = rng.uniform(0.5, 1.5, n)
    net_cum = np.cumsum(rng.normal(0, 1, n))
    funding = np.tile([0.0001, 0.0001, -0.0001, -0.0001, 0.0001], n // 5 + 1)[:n]
    qv = 1_000_000.0 + rng.normal(0, 50_000, n)
    return {
        "klines": _frame(ts, {"close": close, "quote_volume": qv}),
        "liquidation": _frame(ts, {"long_liquidation_usd": long_liq, "short_liquidation_usd": short_liq}),
        "cvd": _frame(ts, {"cum_vol_delta": cum_delta}),
        "ls_top_trader": _frame(ts, {"top_position_long_short_ratio": top_ratio}),
        "net_position": _frame(ts, {"net_position_change_cum": net_cum}),
        "funding_ohlc": _frame(ts, {"close": funding}),
    }


def test_build_feature_table_shape_and_columns():
    dims = _make_dims()
    win = FeatureWindow(z_bars=720, rank_bars=720, vol_baseline_bars=720, vol_agg_bars=72)
    table = build_feature_table(dims, win)
    assert len(table) == 3000
    expected = {
        "close", "ret_24h", "liq_short_z", "liq_long_z", "liq_short_share",
        "price_z", "cvd_z", "cvd_divergence", "top_ratio_rank",
        "top_ratio_chg_24h", "net_pos_chg_24h", "vol_72h_ratio", "funding_streak",
    }
    assert expected.issubset(set(table.columns))
    # 无 ±inf（NaN 是正常缺失，允许）
    assert not table.isin([np.inf, -np.inf]).any().any()


def test_build_feature_table_liq_spike_detected():
    dims = _make_dims()
    win = FeatureWindow(z_bars=720, rank_bars=720, vol_baseline_bars=720, vol_agg_bars=72)
    table = build_feature_table(dims, win)
    spike_idx = 1500
    assert table["liq_short_z"].iloc[spike_idx] == table["liq_short_z"].max()


def test_build_feature_table_missing_dimension_tolerated():
    dims = _make_dims()
    del dims["cvd"]
    table = build_feature_table(dims, FeatureWindow(z_bars=720, rank_bars=720, vol_baseline_bars=720, vol_agg_bars=72))
    assert table["cvd_z"].isna().all()  # 缺 cvd → 特征全 NaN，不崩溃
    assert table["price_z"].notna().any()  # 其余特征仍计算


def test_sanitize_close_kills_fake_bar_keeps_real_price():
    # 模拟 coinglass 停更断点假 bar：正常 ~100，中间一个 0.001（偏离 1e5x）
    n = 3000
    close = 100.0 + np.sin(np.arange(n) / 50.0)
    fake_idx = 1500
    close = close.copy()
    close[fake_idx] = 0.001
    s = pd.Series(close)
    cleaned = _sanitize_close(s, window=720)
    assert np.isnan(cleaned.iloc[fake_idx])  # 假 bar 被抹掉
    assert cleaned.dropna().between(90, 110).all()  # 正常价格保留
    # 真实剧烈波动（±5%）不误伤（跳过前 500 点预热窗口）
    vol = pd.Series(100.0 + np.sin(np.arange(n) / 10.0) * 5.0)
    med = vol.rolling(720, min_periods=360).median()
    assert ((vol / med).iloc[500:].between(0.02, 50.0)).all()


def test_build_feature_table_washout_boolean():
    # 尾部 24h 深跌 → washout=1；头部预热期（price_z/ret_24h 均 NaN）→ washout=NaN
    n = 3000
    close = 100.0 + 0.5 * np.sin(np.arange(n) / 50.0)  # 轻微波动 → price_z 有限
    close = close.copy()
    close[-25:] = 80.0  # 最后一根 bar 相对 24h 前 -20%
    dims = {
        "klines": _frame(_ts(n), {"close": close, "quote_volume": np.full(n, 1e6)}),
    }
    table = build_feature_table(dims, FeatureWindow(z_bars=720, rank_bars=720, vol_baseline_bars=720, vol_agg_bars=72))
    assert table["washout"].iloc[-1] == 1.0
    assert pd.isna(table["washout"].iloc[0])  # 预热期无判定
    # 平静段 washout=0（不误触发）
    mid_idx = 2000
    assert table["washout"].iloc[mid_idx] == 0.0


def test_layout_uses_confirmed_coinglass_columns():
    assert DIMENSION_LAYOUT["liquidation"]["cols"] == ["long_liquidation_usd", "short_liquidation_usd"]
    assert DIMENSION_LAYOUT["cvd"]["cols"] == ["cum_vol_delta"]
    assert DIMENSION_LAYOUT["ls_top_trader"]["cols"] == ["top_position_long_short_ratio"]
    assert DIMENSION_LAYOUT["net_position"]["cols"] == ["net_position_change_cum"]
