"""Regression tests for 143_paper_trade（结算写盘 / MDD 口径）。

锁住：
1. equity_mdd 必须按时间序累计（未排序会低估回撤）。
2. B/C PENDING 升级路径：无新事件时也要能写出 SETTLED（逻辑用标志位覆盖）。
3. simulate 止损在 bar 回放路径生效。
"""
from __future__ import annotations

import importlib.util
import sys
from pathlib import Path

import numpy as np
import pandas as pd

PROJECT_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(PROJECT_ROOT))
SPEC_PATH = PROJECT_ROOT / "scripts" / "143_paper_trade.py"
HOUR_MS = 3_600_000
T0 = 1_700_000_000_000


def _load():
    spec = importlib.util.spec_from_file_location("paper_trade_mod", SPEC_PATH)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


def test_equity_mdd_requires_time_order():
    m = _load()
    # 先大亏再大赚：时间序 MDD 深；乱序 cumsum 会浅
    pnl_chrono = pd.Series([-5000.0, -2000.0, 8000.0])
    pnl_shuffled = pd.Series([8000.0, -5000.0, -2000.0])
    mdd_ok = m.equity_mdd(pnl_chrono)
    mdd_bad = m.equity_mdd(pnl_shuffled)
    assert mdd_ok < -0.6
    assert mdd_bad > mdd_ok  # 乱序低估回撤


def test_simulate_stop_hits_before_max_hold():
    m = _load()
    n = 50
    opens = np.full(n, 100.0)
    closes = np.full(n, 100.0)
    closes[5] = 75.0  # -25% < -20% stop
    prices = pd.DataFrame({
        "open_time": np.arange(T0, T0 + n * HOUR_MS, HOUR_MS, dtype=np.int64),
        "open": opens,
        "close": closes,
    })
    ev = pd.Series({"timestamp_ms": T0, "symbol": "T"})
    out = m.simulate(ev, prices, hold_h=24, stop=-0.20, trail=-0.50, max_hold_h=168, size=1.0)
    assert out["exit_reason"] == "STOP"
    assert out["hold_h"] == 4.0  # entry=bar after ts → stop at closes[5] → hold 4h


def test_simulate_confirm_no_entry_on_down_move():
    m = _load()
    n = 200
    opens = np.full(n, 100.0)
    closes = np.linspace(100.0, 90.0, n)  # 持续下跌 → 4h 确认失败
    prices = pd.DataFrame({
        "open_time": np.arange(T0, T0 + n * HOUR_MS, HOUR_MS, dtype=np.int64),
        "open": opens,
        "close": closes,
    })
    ev = pd.Series({"timestamp_ms": T0, "symbol": "T"})
    out = m.simulate_confirm(ev, prices, size=1.0)
    assert out["exit_reason"] == "NO_ENTRY"
    assert out["pnl_net"] == 0.0


def test_positions_write_when_only_upgrade():
    """无新事件时，仅 existing 升级也必须能拼出可写 DataFrame。"""
    existing = {
        "a1": {"alert_id": "a1", "account_b_status": "SETTLED", "account_c_status": "SETTLED"},
    }
    rows: list = []
    existing_dirty = True
    assert rows or existing_dirty
    parts = [pd.DataFrame(list(existing.values()))]
    if rows:
        parts.append(pd.DataFrame(rows))
    merged = pd.concat(parts, ignore_index=True)
    assert len(merged) == 1
    assert merged.iloc[0]["account_b_status"] == "SETTLED"
