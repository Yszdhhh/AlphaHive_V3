"""Regression tests for 108/109 连续打分标注（2026-08-09，codex 规划 + grok 审查条件）。

锁住：
1. score_vol_at 口径与 213 一致：ratio=1→0、ratio=2→1、log 插值；[0,1]。
2. asof 无前视：事件时点后的 bar 不影响分数。
3. 冻结门控：未 FROZEN → NA；ts<forward_start → NA；非适用 trigger → NA。
4. 异常/缺列/窗口不足 → NA 不抛异常。
5. apply_score_gate：109 端清边界前分数（0 与 NA 不混）。
6. score_vol_report：样本不足 → 明确标注；正常分桶出 uplift，不改原收益列。
"""
from __future__ import annotations

import importlib.util
import sys
from pathlib import Path

import numpy as np
import pandas as pd

PROJECT_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(PROJECT_ROOT))

_spec108 = importlib.util.spec_from_file_location("m108", PROJECT_ROOT / "scripts" / "108_contract_monitor.py")
m108 = importlib.util.module_from_spec(_spec108)
_spec108.loader.exec_module(m108)

_spec109 = importlib.util.spec_from_file_location("m109", PROJECT_ROOT / "scripts" / "109_forward_replay.py")
m109 = importlib.util.module_from_spec(_spec109)
_spec109.loader.exec_module(m109)

HOUR_MS = 3_600_000
T0 = 1_700_000_000_000 - (1_700_000_000_000 % HOUR_MS)
EV = T0 + 800 * HOUR_MS  # 事件在第 800 根 bar（基线 720 窗充足）
FROZEN_SPEC = {
    "spec_id": "FAM-001", "status": "FROZEN", "applicable_triggers": ["wash_cvd"],
    "forward_start": pd.Timestamp(EV, unit="ms", tz="UTC").isoformat(),
    "form": "capped_hinge", "qv_window_hours": 24, "baseline_window_hours": 720,
    "baseline_min_periods": 24, "lo": 1.0, "hi": 2.0,
}
PARK_SPEC = {**FROZEN_SPEC, "status": "PARK"}


def _kl_vol(pre_vol: float, ev_vol: float, n=1000, t0=T0) -> pd.DataFrame:
    """基线期量=pre_vol，事件前 24h 量=ev_vol（其余同基线）。"""
    ts = np.arange(t0, t0 + n * HOUR_MS, HOUR_MS, dtype=np.int64)
    qv = np.full(n, pre_vol, dtype=float)
    qv[(ts > EV - 24 * HOUR_MS) & (ts <= EV)] = ev_vol
    return pd.DataFrame({"timestamp": ts, "quote_volume": qv})


def test_ratio_boundaries():
    # ev_vol=2×pre → ratio≈2 → score≈1；ev_vol=pre → ratio≈1 → score≈0
    s = m108.score_vol_at(_kl_vol(1e6, 2e6), EV, "wash_cvd", FROZEN_SPEC)
    assert s is not None and 0.9 <= s <= 1.0
    s2 = m108.score_vol_at(_kl_vol(1e6, 1e6), EV, "wash_cvd", FROZEN_SPEC)
    assert s2 is not None and abs(s2) < 1e-9


def test_score_in_unit_interval():
    s = m108.score_vol_at(_kl_vol(1e6, 5e6), EV, "wash_cvd", FROZEN_SPEC)
    assert s is not None and 0.0 <= s <= 1.0


def test_asof_no_future_leak():
    kl = _kl_vol(1e6, 2e6)
    kl.loc[kl["timestamp"] > EV, "quote_volume"] = 1e9  # 事件后巨量
    s = m108.score_vol_at(kl, EV, "wash_cvd", FROZEN_SPEC)
    assert s is not None and 0.9 <= s <= 1.0


def test_gate_unfrozen_na():
    kl = _kl_vol(1e6, 2e6)
    assert m108.score_vol_at(kl, EV, "wash_cvd", PARK_SPEC) is None
    assert m108.score_vol_at(kl, EV, "wash_cvd", None) is None


def test_gate_before_forward_start_na():
    kl = _kl_vol(1e6, 2e6)
    assert m108.score_vol_at(kl, T0, "wash_cvd", FROZEN_SPEC) is None  # < forward_start
    assert m108.score_vol_at(kl, EV, "cvd_bear_divergence", FROZEN_SPEC) is None  # 非适用 trigger


def test_missing_data_na_no_exception():
    kl = _kl_vol(1e6, 2e6, n=10)  # 窗口不足
    assert m108.score_vol_at(kl, T0 + 5 * HOUR_MS, "wash_cvd", FROZEN_SPEC) is None
    kl2 = pd.DataFrame({"timestamp": [T0], "close": [1.0]})  # 缺 quote_volume
    assert m108.score_vol_at(kl2, T0, "wash_cvd", FROZEN_SPEC) is None
    assert m108.score_vol_at(None, T0, "wash_cvd", FROZEN_SPEC) is None


def test_apply_score_gate_unfrozen():
    df = pd.DataFrame({"timestamp_ms": [T0, EV], "score_vol": [0.3, 0.7]})
    out = m109.apply_score_gate(df)
    assert out["score_vol"].isna().all()  # 真实 config 当前 PARK → 全 NA


def test_score_report_insufficient():
    cf = pd.DataFrame({
        "score_vol": [np.nan, np.nan, np.nan],
        "direction": ["Long"] * 3, "ret_24h": [1.0, 2.0, 3.0],
    })
    lines = m109.score_vol_report(cf)
    assert any("INSUFFICIENT_VARIATION" in l or "NOT_ENOUGH_DATA" in l for l in lines)


def test_score_report_buckets_dont_touch_raw():
    rng = np.random.default_rng(7)
    cf = pd.DataFrame({
        "score_vol": rng.uniform(0, 1, 60),
        "direction": ["Short"] * 30 + ["Long"] * 30,
        "ret_24h": rng.normal(0, 2, 60),
    })
    raw_before = cf["ret_24h"].copy()
    lines = m109.score_vol_report(cf)
    assert any("最高−最低桶 uplift" in l for l in lines)
    assert cf["ret_24h"].equals(raw_before)  # 原收益列不动
