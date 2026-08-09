r"""212_factor_form_matrix.py — 因子概念 × 数学形态枚举矩阵（问题 3 实证）。

问题：同一个因子概念，用不同数学形态（raw/z/rank/log/分位/二元）表达，
对 wash_cvd 事件前向收益的预测效果会不同吗？

设计（务实版）：
- 3 个因子概念 × 5 种形态 = 15 格
  概念：A. 放量（qv24/30d 中位） B. CVD 背离（cvd_divergence） C. 波动抬升（price_z 绝对值）
  形态：raw / 30d z / 截面 rank(分位) / log / 二元（中位切）
- 度量：每格对事件 24h 前向的 IC（Spearman，事件级）+ 高/低二分档均值差 + bootstrap CI
- 目的：判断"形态是否改变结论"（不是找新因子，不消耗正式预算，探索性）

输出：reports/factor_form_matrix.md
用法：python scripts/212_factor_form_matrix.py
"""
from __future__ import annotations

import importlib.util
import sys
from datetime import datetime, timezone
from pathlib import Path

import numpy as np
import pandas as pd

PROJECT_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(PROJECT_ROOT))

from harness.lib.event_study import forward_stats  # noqa: E402

_spec = importlib.util.spec_from_file_location(
    "m113", str(PROJECT_ROOT / "scripts" / "113_washout_settle_study.py"))
m113 = importlib.util.module_from_spec(_spec)
sys.modules["m113"] = m113
_spec.loader.exec_module(m113)
_spec2 = importlib.util.spec_from_file_location(
    "m115", str(PROJECT_ROOT / "scripts" / "115_short_squeeze_combo_study.py"))
m115 = importlib.util.module_from_spec(_spec2)
sys.modules["m115"] = m115
_spec2.loader.exec_module(m115)

REPORT = PROJECT_ROOT / "reports" / "factor_form_matrix.md"
SEED = 2026
HORIZON = 24


def event_features(ctxs: dict, events: pd.DataFrame) -> pd.DataFrame:
    """事件时点 asof 取 3 个因子概念原始值。"""
    qv_cache: dict[str, pd.Series] = {}
    rows = []
    for sym, g in events.groupby("symbol", sort=False):
        ctx = ctxs[sym]
        idx = ctx.index.to_numpy(dtype=np.int64)
        pos = np.searchsorted(idx, g["timestamp"].to_numpy(dtype=np.int64), side="right") - 1
        pos = np.clip(pos, 0, len(idx) - 1)
        # 放量：coinglass klines quote_volume（113 的 ctx 无 qv，直接读源）
        if sym not in qv_cache:
            p = m113.COINGLASS_RAW1H / "klines" / f"{sym}.parquet"
            if p.exists():
                kl = pd.read_parquet(p)
                ts_col = "time" if "time" in kl.columns else "open_time"
                if "quote_volume" in kl.columns:
                    qv_cache[sym] = pd.Series(
                        pd.to_numeric(kl["quote_volume"], errors="coerce").to_numpy(),
                        index=pd.Index(pd.to_numeric(kl[ts_col], errors="coerce")))
            else:
                qv_cache[sym] = pd.Series(dtype=float)
        qv = qv_cache[sym]
        qv24 = qv.rolling(24).sum()
        med30 = qv24.rolling(30 * 24, min_periods=24).median()
        vol_ratio = (qv24 / med30.replace(0, np.nan))
        for i, (_, e) in enumerate(g.iterrows()):
            p = pos[i]
            ts = int(e["timestamp"])
            vp = int(np.searchsorted(qv.index.to_numpy(dtype=np.int64), ts, side="right")) - 1
            vr = vol_ratio.iloc[vp] if 0 <= vp < len(vol_ratio) else np.nan
            cvd_div = pd.to_numeric(ctx["cvd_divergence"], errors="coerce").iloc[p]
            pz = pd.to_numeric(ctx["price_z"], errors="coerce").iloc[p]
            rows.append({"symbol": sym, "timestamp": ts,
                         "vol_ratio": vr, "cvd_div": cvd_div, "price_z": pz})
    return pd.DataFrame(rows)


def forms(s: pd.Series) -> dict[str, pd.Series]:
    """5 种数学形态。"""
    z = (s - s.rolling(720, min_periods=180).mean()) / s.rolling(720, min_periods=180).std().replace(0, np.nan)
    r = s.rank(pct=True)
    lg = np.sign(s) * np.log1p(np.abs(s))
    med = s.median()
    return {"raw": s, "z30d": z, "rank": r, "log": lg, "binary": (s > med).astype(float)}


def main() -> int:
    symbols = m113.load_universe_symbols()
    ctxs = m113.load_price_ctx(symbols)
    fundings = m113.load_funding_series(symbols)
    ev_parts = []
    for sym, ctx in ctxs.items():
        ev = m115.detect_events(sym, ctx, fundings.get(sym), "wash_cvd")
        if not ev.empty:
            ev_parts.append(ev)
    events = pd.concat(ev_parts, ignore_index=True) if ev_parts else pd.DataFrame(
        columns=["symbol", "timestamp"])
    feat = event_features(ctxs, events)
    ev = events.merge(feat, on=["symbol", "timestamp"], how="left")
    fwd = []
    for sym, g in ev.groupby("symbol", sort=False):
        fwd.append(forward_stats(ctxs[sym], g.copy(), horizons=(HORIZON,)))
    ev = pd.concat(fwd, ignore_index=True) if fwd else ev
    y = pd.to_numeric(ev[f"ret_{HORIZON}h"], errors="coerce")
    print(f"事件 {len(ev)}")

    concepts = {"放量 vol_ratio": "vol_ratio", "CVD背离 cvd_div": "cvd_div", "波动 price_z": "price_z"}
    lines = ["# 因子概念 × 数学形态矩阵（212，问题 3 实证）\n",
             f"- 生成：{datetime.now(timezone.utc):%Y-%m-%d %H:%M UTC}",
             f"- 事件级 IC（Spearman，y=24h 前向）与高/低二分差；探索性，不消耗正式预算\n",
             "| 概念 | 形态 | IC | 高−低差 | bootstrap CI |",
             "|---|---|---:|---:|---:|"]
    results = []
    for cname, col in concepts.items():
        base = pd.to_numeric(ev[col], errors="coerce")
        for fname, fs in forms(base).items():
            valid = pd.DataFrame({"f": fs, "y": y}).dropna()
            if len(valid) < 200:
                continue
            ic = valid["f"].corr(valid["y"], method="spearman")
            med = valid["f"].median()
            hi = valid[valid["f"] >= med]["y"].mean()
            lo = valid[valid["f"] < med]["y"].mean()
            diff = hi - lo
            rng = np.random.default_rng(SEED)
            bs = np.array([(valid["y"].sample(frac=1.0, random_state=int(rng.integers(0, 1e9)))
                            .iloc[:len(valid)//2].mean()) for _ in range(200)])
            # 简单 bootstrap（分档差）
            diffs = []
            for _ in range(500):
                idx2 = rng.integers(0, len(valid), size=len(valid))
                sub = valid.iloc[idx2]
                m2 = sub["f"].median()
                diffs.append(sub[sub["f"] >= m2]["y"].mean() - sub[sub["f"] < m2]["y"].mean())
            diffs = np.array(diffs)
            ci = f"[{np.quantile(diffs, .025):+.2f}, {np.quantile(diffs, .975):+.2f}]"
            results.append((cname, fname, ic, diff, ci))
            lines.append(f"| {cname} | {fname} | {ic:+.3f} | {diff:+.2f}% | {ci} |")
            print(f"  {cname} × {fname}: IC {ic:+.3f} 高−低 {diff:+.2f}%")

    lines += ["\n## 解读\n",
              "- 看同一概念 5 行形态间：IC 符号是否一致、高−低差是否同号、CI 是否同方向。",
              "- 形态一致（同号同显著）→ 结论由机制驱动，形态只是刻度；",
              "- 形态翻转（raw 负 z 正 / CI 跨零）→ 形态选择本身是研究自由度（多重检验风险），需预注册。"]
    REPORT.parent.mkdir(parents=True, exist_ok=True)
    REPORT.write_text("\n".join(lines) + "\n", encoding="utf-8")
    print(f"wrote {REPORT}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
