"""Regression tests for 108_contract_monitor vix_gate（wash_cvd VIX 门控标注，v3）。

锁住四件事：
1. q75 口径：最近 quantile_window_days 天滚动分位（min_periods=窗口/3，至少 60）。
2. 无前视：候选时点 asof 日-1 的 VIX 收盘（当天值不可见）。
3. 缺数据/窗口不足 → NA（不硬判，不阻断候选流）。
4. 边界：close_at > q75 → high（门控建议跳过）；否则 low。
"""
from __future__ import annotations

import importlib.util
import sys
from pathlib import Path

import numpy as np
import pandas as pd

PROJECT_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(PROJECT_ROOT))
SPEC_PATH = PROJECT_ROOT / "scripts" / "108_contract_monitor.py"
DAY_MS = 86_400_000
T0 = 1_700_000_000_000  # 2023-11-14 附近，任意锚点


def _load():
    spec = importlib.util.spec_from_file_location("monitor_mod", SPEC_PATH)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


def _vix_series(n: int, base: float = 20.0, step: float = 0.0) -> pd.Series:
    idx = np.arange(n, dtype=np.int64) * DAY_MS + T0
    vals = base + step * np.arange(n, dtype=float)
    return pd.Series(vals, index=pd.Index(idx))


CFG = {"enabled": True, "quantile_window_days": 365, "quantile": 0.75, "asof_days_back": 1}


def test_q75_uses_trailing_window():
    m = _load()
    n = 400
    # 前 300 天恒 20，后 100 天恒 30 → asof 窗口尾部 100 天全 30 → q75=30
    vals = np.full(n, 20.0)
    vals[300:] = 30.0
    vix = pd.Series(vals, index=pd.Index(np.arange(n, dtype=np.int64) * DAY_MS + T0))
    ts = T0 + (n - 1) * DAY_MS  # 第 n 天，asof = 第 n-1 天（值 30）
    r = m.vix_gate_state(vix, ts, CFG)
    assert r["status"] == "low", r          # close_at=30, q75=30 → 不 > → low
    assert abs(r["close"] - 30.0) < 1e-9
    assert abs(r["q75"] - 30.0) < 1e-9


def test_asof_no_lookahead():
    m = _load()
    n = 400
    vix = _vix_series(n, base=10.0, step=0.05)  # 单调上升 10 → 30
    # 第 200 天 ts；asof = 第 199 天 VIX；q75 用 ≤ asof 的历史
    ts = T0 + 200 * DAY_MS
    r = m.vix_gate_state(vix, ts, CFG)
    idx = vix.index.to_numpy(dtype=np.int64)
    pos = int(np.searchsorted(idx, ts - DAY_MS, side="right") - 1)
    assert pos == 199, pos
    # 单调上升 → close_at(第199天) 是该窗口最高值 → high
    assert r["status"] == "high", r
    assert abs(r["close"] - float(vix.iloc[199])) < 1e-9


def test_low_when_below_quantile():
    m = _load()
    n = 400
    # 前 300 天恒 30，后 100 天恒 10 → asof 值 10 << q75 30 → low
    vals = np.full(n, 30.0)
    vals[300:] = 10.0
    vix = pd.Series(vals, index=pd.Index(np.arange(n, dtype=np.int64) * DAY_MS + T0))
    ts = T0 + (n - 1) * DAY_MS
    r = m.vix_gate_state(vix, ts, CFG)
    assert r["status"] == "low", r
    # 365d 窗口覆盖第 35-399 天：265 天值 30 + 100 天值 10 → q75=30；close_at=10 < 30 → low
    assert abs(r["q75"] - 30.0) < 1e-9


def test_insufficient_window_returns_na():
    m = _load()
    vix = _vix_series(50, base=20.0)  # 50 天 < min_periods=120
    ts = T0 + 49 * DAY_MS
    r = m.vix_gate_state(vix, ts, CFG)
    assert r["status"] == "NA"
    assert np.isnan(r["q75"])


def test_empty_series_returns_na():
    m = _load()
    r = m.vix_gate_state(pd.Series(dtype=float), T0, CFG)
    assert r["status"] == "NA"
    assert np.isnan(r["close"])


def test_disabled_cfg_returns_na():
    m = _load()
    vix = _vix_series(400, base=20.0)
    r = m.vix_gate_state(vix, T0 + 399 * DAY_MS, {"enabled": False})
    assert r["status"] == "NA"


def test_ts_before_first_vix_point_returns_na():
    m = _load()
    vix = _vix_series(400, base=20.0)
    r = m.vix_gate_state(vix, T0 - 5 * DAY_MS, CFG)
    assert r["status"] == "NA"
