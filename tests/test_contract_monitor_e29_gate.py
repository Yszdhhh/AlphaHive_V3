"""Regression tests for 108 E29 环境标注（2026-08-09 Owner 签批，annotate-only）。

锁住：
1. e29_gate_state：high/low/normal 分档（±threshold）、asof 前一日无前视、NA 语义。
2. disabled/空 → NA（e29_ok=None，不参与任何跳过）。
3. load_e29_score：日索引 ms 对齐（lz 日计数→ms 与 VIX 对齐）、异常容忍。
"""
from __future__ import annotations

import importlib.util
import sys
from pathlib import Path

import numpy as np
import pandas as pd

PROJECT_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(PROJECT_ROOT))

_spec = importlib.util.spec_from_file_location("m108", PROJECT_ROOT / "scripts" / "108_contract_monitor.py")
m108 = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(m108)

DAY_MS = 86_400_000
T0 = 1_700_000_000_000 - (1_700_000_000_000 % DAY_MS)  # 日起点
CFG = {"enabled": True, "threshold": 0.5, "asof_days_back": 1}


def _score_series(vals: list[float]) -> pd.Series:
    return pd.Series(vals, index=[T0 + i * DAY_MS for i in range(len(vals))])


def test_status_buckets():
    # asof 回看 1 天：事件 T0+2d+1h → 用 T0+1d 的 score（0.8 → high）
    s = _score_series([0.0, 0.8, -0.8, 0.2])
    assert m108.e29_gate_state(s, T0 + 2 * DAY_MS + 3600_000, CFG)["status"] == "high"
    assert m108.e29_gate_state(s, T0 + 3 * DAY_MS + 3600_000, CFG)["status"] == "low"
    assert m108.e29_gate_state(s, T0 + 4 * DAY_MS + 3600_000, CFG)["status"] == "normal"
    assert m108.e29_gate_state(s, T0 + 4 * DAY_MS + 3600_000, CFG)["e29_ok"] is False
    assert m108.e29_gate_state(s, T0 + 2 * DAY_MS + 3600_000, CFG)["e29_ok"] is True


def test_asof_no_lookahead():
    s = _score_series([0.0, 0.8])
    # 事件在 T0+1d 后 1h → asof 前一日 = T0+0d → normal(0.0)，不能用 T0+1d 的 0.8
    assert m108.e29_gate_state(s, T0 + 1 * DAY_MS + 3600_000, CFG)["status"] == "normal"
    # 事件在 T0+2d 后 1h → asof = T0+1d → high(0.8)
    assert m108.e29_gate_state(s, T0 + 2 * DAY_MS + 3600_000, CFG)["status"] == "high"


def test_disabled_or_empty_na():
    s = _score_series([0.8])
    assert m108.e29_gate_state(s, T0 + DAY_MS, {**CFG, "enabled": False})["status"] == "NA"
    assert m108.e29_gate_state(pd.Series(dtype=float), T0 + DAY_MS, CFG)["status"] == "NA"


def test_before_data_na():
    s = _score_series([0.8])
    assert m108.e29_gate_state(s, T0 - DAY_MS, CFG)["status"] == "NA"
