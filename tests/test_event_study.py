"""Regression tests for the event study core (Phase 2)."""
from __future__ import annotations

import numpy as np
import pandas as pd
import pytest

from harness.lib.event_study import (
    bootstrap_ci,
    detect_events,
    forward_stats,
    draw_random_events,
    HOUR_MS,
)

N = 3000
START = 1_700_000_000_000
TS = START + np.arange(N, dtype=np.int64) * HOUR_MS


def _table(close: np.ndarray | None = None, liq_short: np.ndarray | None = None) -> pd.DataFrame:
    if close is None:
        close = 100.0 + np.sin(np.arange(N) / 100.0)
    if liq_short is None:
        liq_short = np.zeros(N)
        liq_short[1000] = 50_000_000.0  # 一个强平尖峰
    ret24 = pd.Series(close).pct_change(24).to_numpy() * 100.0
    z = np.full(N, 0.1)
    z[1000] = 6.0  # 尖峰对应大 z
    df = pd.DataFrame({
        "close": close,
        "ret_24h": ret24,
        "liq_short_z": z,
        "liq_long_z": z * 0.1,
    })
    df.index = pd.Index(TS, name="timestamp")  # 约定：index 必须是 ms 时间戳
    return df


def test_detect_events_finds_spike_and_applies_cooldown():
    t = _table()
    rule = {"feature": "liq_short_z", "threshold": 2.0, "direction": "above", "cooldown_hours": 48}
    ev = detect_events(t, "SYM", rule, max_forward_hours=168)
    assert len(ev) == 1
    assert ev["timestamp"].iloc[0] == TS[1000]
    assert ev["feature_value"].iloc[0] == pytest.approx(6.0)


def test_detect_events_cooldown_dedups_cluster():
    z = np.full(N, 0.0)
    z[500:510] = 5.0  # 连续 10h 尖峰簇
    t = _table(liq_short=np.where(np.arange(N) == 1000, 1.0, 0.0))
    t["liq_short_z"] = z
    rule = {"feature": "liq_short_z", "threshold": 2.0, "direction": "above", "cooldown_hours": 48}
    ev = detect_events(t, "SYM", rule, max_forward_hours=168)
    # 500-509 是 9h 簇，cooldown 48h → 只保留 1 个
    assert len(ev) == 1
    assert ev["timestamp"].iloc[0] == TS[500]


def test_detect_events_price_filter_blocks_runaway():
    close = np.full(N, 100.0)
    close[900:] = 100.0 + np.arange(N - 900)  # 后期大涨
    t = _table(close=close)
    z = np.full(N, 0.0)
    z[950] = 6.0
    t["liq_short_z"] = z
    rule = {
        "feature": "liq_short_z", "threshold": 2.0, "direction": "above",
        "price_filter": {"feature": "ret_24h", "threshold": 5.0, "direction": "below"},
        "cooldown_hours": 48,
    }
    ev = detect_events(t, "SYM", rule, max_forward_hours=168)
    # 950 处 ret_24h 已 >5% → 被 price_filter 拦截
    assert ev.empty


def test_forward_stats_computes_returns_and_mfe_mae():
    close = 100.0 + np.arange(N, dtype=float) * 0.01  # 稳定上行
    t = _table(close=close)
    ev = pd.DataFrame({
        "symbol": ["S"], "timestamp": [TS[1000]], "feature": ["f"],
        "feature_value": [6.0], "ret_24h_at_event": [0.0],
    })
    out = forward_stats(t, ev, [4, 24])
    # base at i=1000 = 110.00；close=100+i*0.01 → +0.04/110 = +0.0364%
    assert out["ret_4h"].iloc[0] == pytest.approx(0.04 / 110 * 100, abs=1e-9)
    assert out["ret_24h"].iloc[0] == pytest.approx(0.24 / 110 * 100, abs=1e-9)
    assert out["mfe_pct"].iloc[0] >= out["ret_24h"].iloc[0]  # MFE >= 期末收益
    assert out["mae_pct"].iloc[0] <= out["ret_4h"].iloc[0]  # MAE <= 早期收益


def test_bootstrap_ci_separates_signal_from_noise():
    rng = np.random.default_rng(7)
    ev = rng.normal(0.5, 1.0, 500)   # 有信号
    base = rng.normal(0.0, 1.0, 500)  # 纯噪声
    ci = bootstrap_ci(ev, base, n_boot=200, seed=1)
    assert ci["ci_lo"] > 0
    assert ci["ci_hi"] > 0


def test_draw_random_events_aligned_and_bounded():
    tables = {"A": _table(), "B": _table(close=200.0 + np.arange(N) * 0.001)}
    rng = np.random.default_rng(3)
    base = draw_random_events(tables, 100, rng, max_forward_hours=168)
    assert len(base) == 100
    assert set(base["symbol"]).issubset({"A", "B"})
    max_ts = START + (N - 168) * HOUR_MS  # 表尾 - max_forward
    assert base["timestamp"].max() <= max_ts


def test_draw_random_events_respects_start_end_window():
    tables = {"A": _table(), "B": _table(close=200.0 + np.arange(N) * 0.001)}
    rng = np.random.default_rng(5)
    lo = START + 500 * HOUR_MS
    hi = START + 1000 * HOUR_MS
    base = draw_random_events(tables, 100, rng, max_forward_hours=168, start_ms=lo, end_ms=hi)
    assert len(base) == 100
    assert base["timestamp"].min() >= lo
    assert base["timestamp"].max() <= hi


def test_draw_random_events_skips_symbols_with_insufficient_window():
    # 若区间内可用前向样本不足 24，该 symbol 整体跳过
    short = _table().iloc[:100]  # 仅 100 行 → 表尾 - 168h 超出数据起点
    tables = {"LONG": _table(), "SHORT": short}
    rng = np.random.default_rng(9)
    base = draw_random_events(tables, 100, rng, max_forward_hours=168, start_ms=START, end_ms=START + 400 * HOUR_MS)
    assert len(base) == 100
    assert set(base["symbol"]) == {"LONG"}  # SHORT 前向窗口不足 → 不参与
