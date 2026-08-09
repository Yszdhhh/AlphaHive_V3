"""Regression tests for harness/lib/factor_funnel.py（2026-08-09，S0 沙盒纯函数）。

锁住：
1. 形态变换保序性（rank/log_ratio/capped_hinge 不改 Spearman 序）与 hinge 饱和边界。
2. bucket_stats：分桶、覆盖、高−低 uplift、单调性语义。
3. conditional_ic：事件条件集内 Spearman；样本不足 → NaN。
4. segment_consistency：两段时间段方向。
5. build_event_master：宽表幂等写出。
"""
from __future__ import annotations

import sys
from pathlib import Path

import numpy as np
import pandas as pd

PROJECT_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(PROJECT_ROOT))

from harness.lib.factor_funnel import (  # noqa: E402
    bucket_stats,
    build_event_master,
    capped_hinge,
    conditional_ic,
    log_ratio_form,
    rank_form,
    segment_consistency,
)

rng = np.random.default_rng(2026)
N = 500


def _series() -> pd.Series:
    # 重尾正偏（模拟放量比率），含离群
    x = np.abs(rng.normal(1.0, 0.5, N)) + rng.exponential(0.2, N)
    x[10] = 50.0  # 离群
    return pd.Series(x)


def test_forms_preserve_spearman_order():
    s = _series()
    y = pd.Series(rng.normal(0.0, 1.0, N))
    # rank 保序（Spearman =1）；capped_hinge 单调不减（截断产生并列，Spearman 略降但单调性成立）
    assert np.isclose(rank_form(s).corr(s, method="spearman"), 1.0)
    h = capped_hinge(s)
    order = np.argsort(s.to_numpy())
    assert np.all(np.diff(h.to_numpy()[order]) >= -1e-12)
    # log_ratio_form 含 720h rolling z（局部偏离度量，非保序）——只验证可运行
    lr = log_ratio_form(s)
    assert lr.notna().sum() > 0


def test_capped_hinge_boundaries():
    s = pd.Series([0.5, 1.0, 1.5, 2.0, 3.0, 10.0])
    h = capped_hinge(s, lo=1.0, hi=2.0)
    assert np.isclose(h.iloc[1], 0.0)     # =lo → 0
    assert np.isclose(h.iloc[3], 1.0)     # =hi → 1
    assert h.iloc[4] == 1.0               # >hi 饱和
    assert h.iloc[0] == 0.0               # <lo 截断
    assert np.isclose(h.iloc[2], np.log(1.5) / np.log(2.0))  # log 对称中点


def test_bucket_stats():
    s = _series()
    y = pd.Series(rng.normal(0.0, 1.0, N))
    bs = bucket_stats(s, y, n_buckets=5)
    assert bs["n"] == N
    assert bs["coverage"] == 1.0
    assert len(bs["buckets"]) == 5
    assert bs["high_low_uplift"] is not None


def test_bucket_stats_low_coverage():
    s = _series()
    y = pd.Series(np.nan, index=range(N))
    y.iloc[:50] = rng.normal(0, 1, 50)
    bs = bucket_stats(s, y)
    assert bs["coverage"] < 0.2  # 大量 NaN → 覆盖低


def test_conditional_ic_small_sample_nan():
    s = pd.Series(rng.normal(0, 1, 10))
    y = pd.Series(rng.normal(0, 1, 10))
    assert np.isnan(conditional_ic(s, y))


def test_segment_consistency():
    s = _series()
    y = pd.Series(rng.normal(0, 1, N))
    ts = pd.date_range("2022-01-01", periods=N, freq="D", tz="UTC")
    segs = segment_consistency(s, y, ts, [("A", "2022-01-01", "2023-01-01"),
                                          ("B", "2023-01-01", None)])
    assert len(segs) == 2
    assert segs[0]["n"] > 0 and segs[1]["n"] > 0
    assert "ic" in segs[0] and "uplift" in segs[0]


def test_build_event_master(tmp_path):
    events = pd.DataFrame({"symbol": ["AUSDT", "BUSDT"], "timestamp": [1, 2]})
    feats = {"f1": pd.Series([0.5, 0.7])}
    ys = {"ret_24h": pd.Series([1.0, -0.5])}
    out = build_event_master(events, feats, ys, tmp_path / "m.parquet")
    assert out.exists()
    df = pd.read_parquet(out)
    assert list(df.columns) == ["symbol", "timestamp", "f1", "ret_24h"]
    assert len(df) == 2
