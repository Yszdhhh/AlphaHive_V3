"""factor_funnel.py — 因子漏斗纯函数模块（2026-08-09 建立，codex/grok 合成版）。

三级漏斗：S0 沙盒（廉价筛选）→ S1 挑战者（一次 holdout 冻结）→ S2 确认（前向）。
本模块只提供纯函数：形态变换、分桶统计、条件 IC、事件宽表构建。无 GO/NO_GO 语义。

纪律（写进代码）：
- 形态词典有限（allowed_forms），S0 每概念 ≤2 预声明形态；
- 统计只做描述（IC/单调/覆盖/两段同向/相关性），不宣布结论；
- 前视防护：特征必须事件时点 asof 取值；rolling 窗口只用历史；
- 历史数据 = development（config/factor_funnel.yaml development_cutoff 前）。

用法：
    from harness.lib.factor_funnel import (rank_form, log_ratio_form, capped_hinge,
                                           bucket_stats, conditional_ic, build_event_master)
"""
from __future__ import annotations

from pathlib import Path

import numpy as np
import pandas as pd

PROJECT_ROOT = Path(__file__).resolve().parents[2]


# ---------- 形态变换（全部保序或明确语义） ----------

def rank_form(s: pd.Series) -> pd.Series:
    """robust percentile：跨币尺度/重尾下稳定。"""
    return s.rank(pct=True)


def log_ratio_form(s: pd.Series, base: float | None = None) -> pd.Series:
    """signed-log + robust z（可选 base 减法：log(s/base)）。"""
    if base is not None:
        s = s / base
    out = np.sign(s) * np.log1p(np.abs(s))
    return (out - out.rolling(720, min_periods=180).mean()) / \
        out.rolling(720, min_periods=180).std().replace(0, np.nan)


def capped_hinge(s: pd.Series, lo: float = 1.0, hi: float = 2.0) -> pd.Series:
    """capped hinge：单调增强后饱和，clip 到 [0,1]。放量 1.0→2.0 的机制版。"""
    eps = np.finfo(float).eps
    with np.errstate(divide="ignore", invalid="ignore"):
        out = (np.log(s) - np.log(lo)) / (np.log(hi) - np.log(lo))
    return out.clip(0.0, 1.0).replace([np.inf, -np.inf], np.nan)


def binary_diag(s: pd.Series, thr: float | None = None) -> pd.Series:
    """二元仅做阈值诊断；thr=None → 中位切。"""
    t = s.median() if thr is None else thr
    return (s > t).astype(float)


FORM_FUNCS = {
    "rank": rank_form,
    "log_ratio": log_ratio_form,
    "capped_hinge": capped_hinge,
    "binary_diag": binary_diag,
}


# ---------- 分桶统计（S0 只输出描述，无 bootstrap CI 升级叙事） ----------

def bucket_stats(factor: pd.Series, y: pd.Series, n_buckets: int = 5,
                 horizon_label: str = "24h") -> dict:
    """分位分桶统计：每桶均值/中位/胜率 + 单调性 + 高−低 uplift + 覆盖率。

    返回 dict（不做任何显著性叙事；显著性留给 S1/S2）。
    """
    valid = pd.DataFrame({"f": factor, "y": y}).dropna()
    if len(valid) == 0:
        return {"n": 0, "coverage": 0.0}
    try:
        valid["bucket"] = pd.qcut(valid["f"], n_buckets, labels=False, duplicates="drop")
    except ValueError:
        valid["bucket"] = 0
    rows = []
    for b, g in valid.groupby("bucket"):
        rows.append({"bucket": int(b), "n": len(g),
                     "mean": float(g["y"].mean()), "median": float(g["y"].median()),
                     "win": float((g["y"] > 0).mean())})
    bdf = pd.DataFrame(rows).sort_values("bucket")
    uplift = None
    if len(bdf) >= 2:
        uplift = float(bdf.iloc[-1]["mean"] - bdf.iloc[0]["mean"])
    # 单调性：相邻桶均值同号变化的占比（允许末端饱和）
    mono = None
    if len(bdf) >= 3:
        diffs = np.sign(np.diff(bdf["mean"].to_numpy()))
        mono = float((diffs != 0).mean())
    return {
        "n": int(len(valid)), "coverage": float(len(valid) / max(len(y), 1)),
        "horizon": horizon_label, "buckets": bdf.to_dict("records"),
        "high_low_uplift": uplift, "monotonicity": mono,
    }


def conditional_ic(factor: pd.Series, y: pd.Series) -> float:
    """条件 Spearman IC（事件条件集内，非日频截面）。"""
    valid = pd.DataFrame({"f": factor, "y": y}).dropna()
    if len(valid) < 30:
        return float("nan")
    return float(valid["f"].corr(valid["y"], method="spearman"))


def segment_consistency(factor: pd.Series, y: pd.Series, ts: pd.Series,
                        splits: list[tuple[str, str | None]]) -> list[dict]:
    """两段时间段方向一致性（如 2022-23 vs 2024-26）：各段 IC + uplift。"""
    out = []
    for name, lo_s, hi_s in splits:
        m = ts >= pd.Timestamp(lo_s, tz="UTC") if lo_s else pd.Series(True, index=ts.index)
        if hi_s:
            m &= ts < pd.Timestamp(hi_s, tz="UTC")
        seg = pd.DataFrame({"f": factor, "y": y})[m].dropna()
        if len(seg) < 30:
            out.append({"segment": name, "n": 0, "ic": None, "uplift": None})
            continue
        med = seg["f"].median()
        hi_m, lo_m = seg["f"] >= med, seg["f"] < med
        out.append({"segment": name, "n": int(len(seg)),
                    "ic": float(seg["f"].corr(seg["y"], method="spearman")),
                    "uplift": float(seg.loc[hi_m, "y"].mean() - seg.loc[lo_m, "y"].mean())})
    return out


# ---------- 事件宽表（grok B 项：一张表取代 21x 脚本反复拼接） ----------

def build_event_master(events: pd.DataFrame, feature_series: dict[str, pd.Series],
                       y_series: dict[str, pd.Series], out_path: Path,
                       extra_cols: dict[str, pd.Series] | None = None) -> Path:
    """把事件表 + 特征 + 前向收益 + 额外列合并成一张宽表（事件键= symbol+timestamp）。

    events: 列 symbol/timestamp；feature_series: 特征名 → 事件 ts 上的 asof 值序列（同长）；
    y_series: horizon → 事件前向收益序列（同长）；extra_cols: 池标签等（同长）。
    输出 parquet，幂等覆盖。
    """
    df = events[["symbol", "timestamp"]].copy()
    for name, s in feature_series.items():
        df[name] = s.to_numpy()
    for name, s in y_series.items():
        df[name] = s.to_numpy()
    for name, s in (extra_cols or {}).items():
        df[name] = s.to_numpy()
    out_path.parent.mkdir(parents=True, exist_ok=True)
    df.to_parquet(out_path, index=False)
    return out_path
