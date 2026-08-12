"""Regression tests for 109_forward_replay（Phase 4 前向复核闭环）。

锁住三件事：
1. 收益口径：close@ts+h / close@ts - 1（时间对齐 asof，非 shift 跨 gap）。
2. 数据不足时返回 NaN（绝不虚构远期收益）。
3. 数据 gap 不虚构：事件后无 bar → NaN。
"""
from __future__ import annotations

import importlib.util
import sys
from pathlib import Path

import numpy as np
import pandas as pd

PROJECT_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(PROJECT_ROOT))
SPEC_PATH = PROJECT_ROOT / "scripts" / "109_forward_replay.py"
HOUR_MS = 3_600_000
T0 = 1_700_000_000_000


def _load():
    spec = importlib.util.spec_from_file_location("forward_replay_mod", SPEC_PATH)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


def _table(n: int, vals) -> pd.DataFrame:
    ts = np.arange(T0, T0 + n * HOUR_MS, HOUR_MS, dtype=np.int64)
    return pd.DataFrame({"close": np.asarray(vals, dtype=float)}, index=pd.Index(ts))


def test_forward_returns_known_values():
    m = _load()
    n = 200
    close = 100.0 * (1.01 ** np.arange(n))
    tables = {"TESTUSDT": _table(n, close)}
    events = m._event_frame(["TESTUSDT"], np.array([T0], dtype=np.int64))
    fwd = m.forward_for_events(tables, events)
    row = fwd.iloc[0]
    assert abs(row["ret_4h"] - (100.0 * 1.01 ** 4 / 100.0 - 1.0) * 100.0) < 1e-9
    assert abs(row["ret_24h"] - (100.0 * 1.01 ** 24 / 100.0 - 1.0) * 100.0) < 1e-9
    assert abs(row["ret_168h"] - (100.0 * 1.01 ** 168 / 100.0 - 1.0) * 100.0) < 1e-9


def test_forward_missing_future_is_nan():
    m = _load()
    tables = {"XUSDT": _table(10, np.linspace(100, 110, 10))}  # 仅 10h 数据
    events = m._event_frame(["XUSDT"], np.array([T0], dtype=np.int64))
    fwd = m.forward_for_events(tables, events)
    row = fwd.iloc[0]
    assert np.isfinite(row["ret_4h"])
    assert np.isnan(row["ret_168h"])  # 无 168h 未来数据


def test_forward_gap_not_fabricated():
    m = _load()
    n = 60
    tables = {"YUSDT": _table(n, np.linspace(100, 160, n))}
    ev_ts = T0 + 50 * HOUR_MS  # 事件在倒数第 10 个 bar
    events = m._event_frame(["YUSDT"], np.array([ev_ts], dtype=np.int64))
    fwd = m.forward_for_events(tables, events)
    row = fwd.iloc[0]
    assert np.isfinite(row["ret_4h"])
    assert np.isnan(row["ret_168h"])


def test_summarize_winrate():
    m = _load()
    s = m.summarize(np.array([1.0, 2.0, -1.0, 0.5]), "cand", 24)
    assert s["n"] == 4
    assert abs(s["winrate"] - 0.75) < 1e-9
    assert abs(s["mean_pct"] - 0.625) < 1e-9
    assert s["horizon_h"] == 24


def test_rows_needing_return_backfill_any_horizon():
    """ret_4h 已填但 ret_24h 缺失 → 仍需回填（修复只看 ret_4h 的闭环漏洞）。"""
    m = _load()
    old = pd.DataFrame({
        "symbol": ["A", "B", "C"],
        "timestamp_ms": [T0, T0 + HOUR_MS, T0 + 2 * HOUR_MS],
        "ret_4h": [1.0, np.nan, 2.0],
        "ret_24h": [np.nan, np.nan, 3.0],
        "ret_72h": [4.0, np.nan, 5.0],
        "ret_168h": [6.0, np.nan, 7.0],
    })
    miss = m.rows_needing_return_backfill(old)
    assert set(miss["symbol"]) == {"A", "B"}  # C 全齐；A 缺 24h；B 全缺


def test_rows_needing_return_backfill_complete_skipped():
    m = _load()
    old = pd.DataFrame({
        "symbol": ["X"],
        "timestamp_ms": [T0],
        "ret_4h": [1.0],
        "ret_24h": [2.0],
        "ret_72h": [3.0],
        "ret_168h": [4.0],
    })
    assert m.rows_needing_return_backfill(old).empty
