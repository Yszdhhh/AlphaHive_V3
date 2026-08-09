"""Regression tests for the regime engine (Phase 2)."""
from __future__ import annotations

import numpy as np
import pandas as pd

from harness.lib.regime_engine import assign_regime, btc_state, sp500_below_50d


def test_btc_state_drawdown_and_ma():
    n = 1200
    ts = 1_700_000_000_000 + np.arange(n, dtype=np.int64) * 3_600_000
    # 先涨到 100，再急跌到 70（-30%），再收复
    close = np.concatenate([
        np.linspace(50, 100, 600),
        np.linspace(100, 70, 200),
        np.linspace(70, 80, 400),
    ])
    s = pd.Series(close, index=ts)
    dd, above = btc_state(s)
    # 深跌段 drawdown 应 < -15%（距 20d 高点回撤）
    min_dd = np.nanmin(dd)
    assert min_dd < -15.0
    # 收复后 above_5d 应为 True（末尾 close=80 > 5d MA）
    assert bool(above[-1])
    # 早期无 480h 窗口 → NaN
    assert np.isnan(dd[0])


def test_sp500_below_50d():
    n = 200
    ts = pd.date_range("2024-01-01", periods=n, freq="D")
    # 单调上涨 → 恒高于 50d MA → 全 False
    up = pd.Series(np.linspace(100, 200, n), index=ts)
    assert not sp500_below_50d(up).any()
    # 后期暴跌 → 尾部低于 50d MA
    crash = pd.concat([pd.Series(np.linspace(100, 200, n // 2), index=ts[: n // 2]),
                       pd.Series(np.linspace(200, 80, n // 2), index=ts[n // 2:])])
    below = sp500_below_50d(crash)
    assert bool(below[-1])


def _regime_cfg() -> dict:
    return {
        "market_regimes_version": "v1",
        "regimes": {
            "btc_recovery": {
                "conditions": {"btc_drawdown_20d_below": -15.0, "btc_close_above_5d_ma": True},
            },
            "risk_off": {"conditions": {"sp500_below_50d_ma": True}},
            "default": {"conditions": {}},
        },
    }


def test_assign_regime_priorities():
    cfg = _regime_cfg()
    # BTC 状态数组（简短），SP 数组（简短），共用同一时间轴
    ts = np.array([1000, 2000, 3000], dtype=np.int64)
    btc_dd = np.array([-30.0, -5.0, -5.0])    # 事件1 深回撤
    btc_above = np.array([True, True, True])
    sp_below = np.array([False, True, False])  # 事件2 risk_off
    ev_ts = np.array([1000, 2000, 3000], dtype=np.int64)
    labels = assign_regime(ev_ts, btc_dd, btc_above, ts, sp_below, ts, cfg)
    assert labels == ["btc_recovery", "risk_off", "default"]  # 优先级：recovery > risk_off > default


def test_assign_regime_asof_no_lookahead():
    cfg = _regime_cfg()
    ts = np.array([1000, 2000, 3000], dtype=np.int64)
    btc_dd = np.array([-30.0, -5.0, -5.0])
    btc_above = np.array([True, True, True])
    sp_below = np.array([False, False, False])
    # 事件在 ts 之间 → asof 取 ts 前最近状态（1000 → 用 index0）
    ev_ts = np.array([1500], dtype=np.int64)
    labels = assign_regime(ev_ts, btc_dd, btc_above, ts, sp_below, ts, cfg)
    assert labels == ["btc_recovery"]  # 1500 落在 1000 之后、2000 之前 → 用 1000 的状态（深回撤）


def test_assign_regime_unknown_time_uses_default():
    cfg = _regime_cfg()
    ts = np.array([1000, 2000, 3000], dtype=np.int64)
    btc_dd = np.array([-30.0, -5.0, -5.0])
    btc_above = np.array([True, True, True])
    sp_below = np.array([False, False, False])
    ev_ts = np.array([50], dtype=np.int64)  # 早于所有数据 → btc_pos=-1 → default
    labels = assign_regime(ev_ts, btc_dd, btc_above, ts, sp_below, ts, cfg)
    assert labels == ["default"]
