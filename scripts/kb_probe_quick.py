"""S0 快筛：交易储备知识库提炼方向 × binance klines 快速验证（2026-08-09）。

三级漏斗纪律：历史数据 = development 只参考；本脚本结论仅用于"方向是否有苗头"，
不冻结不激活。最终确认只认前向。

概念（来自三路交叉扫描）：
  C1 TD 九转（close>close[4] 计数至 9，做多耗尽 → 反转？）
  C2 缠论底分型 + 缩量企稳（3K 底分型 且 vol<0.6*MA20）
  C3 TTM 挤压释放（BB20,2σ 收进 KC20,1.5ATR ≥3 根 → 释放）
  C4 Donchian 20 突破（1h high 突破 20 根最高）
  C5 Bias20 极端（|close/MA20-1| > 15% → 反转 vs 动量）
  C6 量价背离（价格新高但 volume 萎缩 <0.6*MA20 → 转势预警）

基线：全体 bar forward 收益分布（同一 symbol 池，随机抽样 bootstrap CI）。
"""
from __future__ import annotations

import glob
import os
import sys
from pathlib import Path

import numpy as np
import pandas as pd

KLINES = Path(r"C:\Users\10639\Desktop\🔒 加密资产\coinglass_db\raw_1h\klines")
FWD = {"24h": 24, "72h": 72}


def load_symbol(name: str) -> pd.DataFrame | None:
    df = pd.read_parquet(KLINES / f"{name}.parquet")
    if "close" not in df.columns:
        return None
    df = pd.DataFrame({
        "ts": pd.to_numeric(df["open_time"], errors="coerce"),
        "close": pd.to_numeric(df["close"], errors="coerce"),
        "high": pd.to_numeric(df["high"], errors="coerce"),
        "low": pd.to_numeric(df["low"], errors="coerce"),
        "vol": pd.to_numeric(df["volume"], errors="coerce"),
    }).dropna().sort_values("ts")
    return df if len(df) > 500 else None


def add_fwd(df: pd.DataFrame) -> pd.DataFrame:
    c = df["close"].to_numpy()
    for label, n in FWD.items():
        fwd = np.full(len(c), np.nan)
        fwd[:-n] = c[n:] / c[:-n] - 1.0
        df[f"fwd_{label}"] = fwd
    return df


def detect(df: pd.DataFrame) -> dict[str, np.ndarray]:
    n = len(df)
    c, h, l, v = (df[c].to_numpy() for c in ["close", "high", "low", "vol"])
    out = {k: np.zeros(n, dtype=bool) for k in ["td9", "fenxing", "squeeze", "donchian", "bias", "vol_div"]}

    # C1 TD 九转：close > close[4] 连续计数（做多耗尽 9）
    up = (c > np.concatenate([[np.nan] * 4, c[:-4]]))
    cnt = np.zeros(n, dtype=int)
    for i in range(4, n):
        cnt[i] = cnt[i - 1] + 1 if up[i] else 0
    out["td9"] = cnt == 9

    # C2 底分型：中间 K 低点最低 + 缩量
    vol_ma20 = pd.Series(v).rolling(20, min_periods=10).mean().to_numpy()
    is_low = (l[1:-1] < l[:-2]) & (l[1:-1] < l[2:])
    out["fenxing"][1:-1] = is_low & (v[1:-1] < 0.6 * vol_ma20[1:-1])

    # C3 TTM 挤压：BB 宽 < KC 宽 连续 3 根
    bb_w = pd.Series(c).rolling(20, min_periods=15).std().to_numpy() * 2 * 2  # 2σ 近似
    tr = np.maximum(h[1:] - l[1:], np.maximum(abs(h[1:] - c[:-1]), abs(l[1:] - c[:-1])))
    tr = np.concatenate([[np.nan], tr])
    kc_w = pd.Series(tr).rolling(20, min_periods=15).mean().to_numpy() * 1.5
    squeeze = bb_w < kc_w
    sq_run = np.zeros(n, dtype=int)
    for i in range(1, n):
        sq_run[i] = sq_run[i - 1] + 1 if squeeze[i] else 0
    release = (sq_run >= 3) & (~squeeze) & (~np.roll(squeeze, 1))
    out["squeeze"] = release

    # C4 Donchian 20 突破
    hi20 = pd.Series(h).rolling(20, min_periods=15).max().shift(1).to_numpy()
    out["donchian"] = c > hi20

    # C5 Bias20 极端
    ma20 = pd.Series(c).rolling(20, min_periods=15).mean().to_numpy()
    bias = c / ma20 - 1.0
    out["bias"] = np.abs(bias) > 0.15

    # C6 量价背离：close 创新高（20 根）但 vol < 0.6*MA20
    hi20c = pd.Series(h).rolling(20, min_periods=15).max().shift(1).to_numpy()
    out["vol_div"] = (c > hi20c) & (v < 0.6 * vol_ma20)

    return out


def bootstrap_ci(x: np.ndarray, n_iter: int = 1000) -> tuple[float, float, float]:
    rng = np.random.default_rng(2026)
    means = np.array([rng.choice(x, size=min(len(x), 2000), replace=True).mean() for _ in range(n_iter)])
    return float(np.percentile(means, 2.5)), float(np.percentile(means, 97.5))


def main() -> None:
    files = sorted(os.path.basename(p).replace(".parquet", "") for p in glob.glob(str(KLINES / "*.parquet")))
    events: dict[str, dict[str, list[float]]] = {k: {f: [] for f in FWD} for k in
                                                  ["td9", "fenxing", "squeeze", "donchian", "bias", "vol_div"]}
    base: dict[str, list[float]] = {f: [] for f in FWD}
    base_n = 0
    for i, name in enumerate(files):
        df = load_symbol(name)
        if df is None:
            continue
        df = add_fwd(df)
        sig = detect(df)
        base_n += len(df)
        for k in events:
            mask = sig[k]
            if mask.any():
                for f in FWD:
                    vals = df[f"fwd_{f}"].to_numpy()[mask]
                    events[k][f].extend(vals[~np.isnan(vals)].tolist())
        # 全体 bar 抽样（每币最多 3000 根，保持可算）
        step = max(1, len(df) // 3000)
        sample = df.iloc[::step]
        for f in FWD:
            vals = sample[f"fwd_{f}"].to_numpy()
            base[f].extend(vals[~np.isnan(vals)].tolist())
        if (i + 1) % 25 == 0:
            print(f"[probe] {i+1}/{len(files)} symbols...", flush=True)

    print(f"\n=== S0 快筛结果（coinglass klines {len(files)} symbols, 2025-09→2026-07, 1h）===")
    print(f"基线全体 bar: n≈{base_n}")
    for f in FWD:
        b = np.array(base[f])
        lo, hi = bootstrap_ci(b)
        print(f"  基线 fwd_{f}: mean={b.mean():+.3%}  CI[{lo:+.3%},{hi:+.3%}]  n={len(b)}")
    print()
    for k in events:
        print(f"--- {k} ---")
        for f in FWD:
            x = np.array(events[k][f])
            if len(x) < 10:
                print(f"  fwd_{f}: n={len(x)} 样本不足")
                continue
            lo, hi = bootstrap_ci(x)
            print(f"  fwd_{f}: mean={x.mean():+.3%} med={np.median(x):+.3%}  CI[{lo:+.3%},{hi:+.3%}]  n={len(x)}")


if __name__ == "__main__":
    sys.exit(main())
