"""Regression tests for harness/lib/data_cleaning.py（2026-08-08，Phase 1/U2 统一清洗管线）。

锁住：
1. hourly_grid：稀疏序列零填充到整点网格（Coinalyze 清算语义）。
2. clean_hourly_klines：整点对齐/去重/软校验（30d 中位数偏离，先于硬校验——
   离群 close 会触发 hard 的 high<close 假违例，2026-08-08 调试确认）/硬校验/vol 截断/ffill。
3. quality_flag 位掩码语义（ffill 会修复 NaN 价格 → 断言 flag 而非 post-ffill NaN）。
4. forward_return_safe：数据断档不虚构远期收益（109 同款语义）。
"""
from __future__ import annotations

import sys
from pathlib import Path

import numpy as np
import pandas as pd

PROJECT_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(PROJECT_ROOT))

from harness.lib.data_cleaning import (  # noqa: E402
    clean_hourly_klines,
    forward_return_safe,
    hourly_grid,
)

HOUR_MS = 3_600_000
# 整点对齐基准（1_700_000_000_000 不在整点；用其向下取整值）
T0 = 1_700_000_000_000 - (1_700_000_000_000 % HOUR_MS)


def _kl(n=200, t0=T0) -> pd.DataFrame:
    ts = np.arange(t0, t0 + n * HOUR_MS, HOUR_MS, dtype=np.int64)
    return pd.DataFrame({
        "t": ts, "o": 100.0, "h": 101.0, "l": 99.0, "c": 100.0,
        "v": 1.0, "qv": 100.0, "tbv": 0.5, "tbqv": 50.0,
    })


def test_hourly_grid_zero_fills_sparse():
    df = pd.DataFrame({"t": [T0, T0 + 3 * HOUR_MS], "l": [10.0, 5.0], "s": [1.0, 2.0]})
    g = hourly_grid(df)
    assert len(g) == 4
    assert g["t"].tolist() == [T0, T0 + HOUR_MS, T0 + 2 * HOUR_MS, T0 + 3 * HOUR_MS]
    assert g["l"].iloc[1] == 0.0 and g["s"].iloc[2] == 0.0


def test_clean_dedup_keep_last():
    df = _kl(5)
    dup = pd.concat([df, df.iloc[[2]]], ignore_index=True)
    dup.loc[dup.index[-1], "c"] = 100.5  # 物理一致（h=101 > 100.5），仅验证 keep=last
    out = clean_hourly_klines(dup)
    assert len(out) == 5
    assert out["c"].iloc[2] == 100.5


def test_clean_hard_invalid_flagged():
    df = _kl(5)
    df.loc[2, "h"] = 90.0  # high < low → 硬违例
    out = clean_hourly_klines(df)
    assert out.loc[2, "quality_flag"] & 8
    assert out.loc[2, "quality_flag"] & 1  # ffill 修复（≤3h gap）


def test_clean_outlier_ratio_flagged():
    df = _kl(300)
    df.loc[100, "c"] = 100.0 * 20  # 20x 中位数偏离 → 软校验（先于硬校验）
    out = clean_hourly_klines(df)
    assert out.loc[100, "quality_flag"] & 2
    assert not (out.loc[100, "quality_flag"] & 8)  # 不应被 hard 误标


def test_clean_zero_vol_truncated():
    df = _kl(5)
    df.loc[3, "v"] = 0.0
    out = clean_hourly_klines(df)
    assert out.loc[3, "quality_flag"] & 8


def test_clean_ffill_limited_to_3h():
    df = _kl(10)
    df.loc[4:6, "c"] = np.nan  # 3h 缺口
    out = clean_hourly_klines(df)
    assert not out.loc[6, "is_unresolved_gap"]
    assert out.loc[6, "quality_flag"] & 1
    # 连续 5h 缺口 → 无法全部 ffill
    df2 = _kl(10)
    df2.loc[4:8, "c"] = np.nan
    out2 = clean_hourly_klines(df2)
    assert out2.loc[8, "is_unresolved_gap"]


def test_forward_return_gap_safe():
    ts = np.arange(T0, T0 + 10 * HOUR_MS, HOUR_MS, dtype=np.int64)
    close = np.full(10, 100.0)
    ev = np.array([T0])
    r = forward_return_safe(ts, close, ev, 2 * HOUR_MS)
    assert np.isclose(r[0], 0.0)
    # 数据提前截止（断档）→ NaN 不虚增
    ts2 = ts[:3]
    close2 = close[:3]
    r2 = forward_return_safe(ts2, close2, ev, 5 * HOUR_MS)
    assert np.isnan(r2[0])
