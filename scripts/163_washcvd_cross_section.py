r"""163_washcvd_cross_section.py — T1：wash_cvd 事件时点横截面精选（Sol 计划阶段1）。

设计（Sol T1）：
- 事件：wash_cvd（115），窗口 2024-06→2026-05（np_z 数据窗）
- 事件时点横截面：对每事件，取事件时点该 symbol 的 cvd_divergence / price_z / np_z，
  与【同时点全 universe asof 值】比 → 截面百分位（横截面排序而非自序列）
- 精选：cvd_div 截面 top30%（卖压枯竭更强）+ np_z≥-1 过滤（大户未流出）
- 对照：全事件等权（s001 基线）/ bottom30% / 随机同数量
- 判定（门槛 G）：168h 超额 + 中位数 + 尾切 + 独立窗口（2024/2025）+ 净增量≥75bps

换手/成本：事件入场持有 168h，无中途重排；54bps round-trip。
输出：reports/washcvd_cross_section.md
用法：python scripts/163_washcvd_cross_section.py
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

from harness.lib.event_study import (  # noqa: E402
    DEFAULT_HORIZONS,
    bootstrap_ci,
    draw_random_events,
    forward_stats,
)

REPORT = PROJECT_ROOT / "reports" / "washcvd_cross_section.md"
LO_MS = int(pd.Timestamp("2024-06-01", tz="UTC").timestamp() * 1000)
HI_MS = int(pd.Timestamp("2026-05-31", tz="UTC").timestamp() * 1000)
MIN_EVENTS = 30
N_BASELINE = 3000
SEED = 2026
COST_BPS = 54.0 / 100.0


def add_np(ctxs: dict[str, pd.DataFrame]) -> None:
    """161 口径：net_position_change_cum 30d z（np_z）。"""
    RAW = m113.COINGLASS_RAW1H
    for sym, t in ctxs.items():
        t["np_z"] = np.nan
        np_p = RAW / "net_position" / f"{sym}.parquet"
        if not np_p.exists():
            continue
        try:
            n = pd.read_parquet(np_p)
            nts = pd.to_numeric(n["time"], errors="coerce").to_numpy(dtype=np.int64)
            nv = pd.to_numeric(n["net_position_change_cum"], errors="coerce").to_numpy(dtype=float)
            ns = pd.Series(nv, index=pd.Index(nts))
            ns = ns[~ns.index.duplicated(keep="last")].sort_index().reindex(t.index)
            t["np_z"] = m113.rolling_z(ns, 720).to_numpy()
        except Exception:
            pass


def main() -> int:
    symbols = m113.load_universe_symbols()
    ctxs = m113.load_price_ctx(symbols)
    add_np(ctxs)
    fundings = m113.load_funding_series(symbols)

    # 事件
    ev_parts = []
    for sym, ctx in ctxs.items():
        ev = m115.detect_events(sym, ctx, fundings.get(sym), "wash_cvd")
        if not ev.empty:
            ev_parts.append(ev)
    events = pd.concat(ev_parts, ignore_index=True) if ev_parts else pd.DataFrame(
        columns=["symbol", "timestamp"])
    events = events[(events["timestamp"] >= LO_MS) & (events["timestamp"] <= HI_MS)].copy()
    fwd_parts = []
    for sym, g in events.groupby("symbol", sort=False):
        if sym in ctxs:
            fwd_parts.append(forward_stats(ctxs[sym], g.copy(), DEFAULT_HORIZONS))
    events = pd.concat(fwd_parts, ignore_index=True) if fwd_parts else events
    print(f"wash_cvd 事件（窗口）: {len(events)}")

    # 事件时点横截面百分位：对每事件 t，全 universe asof 特征
    feats = ["cvd_divergence", "price_z", "np_z"]
    for f in feats:
        events[f"_raw"] = np.nan
        events[f"_pct"] = np.nan
    # 预取每 symbol 的特征数组
    feat_arrays: dict[str, dict[str, np.ndarray]] = {}
    for sym, ctx in ctxs.items():
        axis = ctx.index.to_numpy(dtype=np.int64)
        feat_arrays[sym] = {"axis": axis}
        for f in feats:
            if f in ctx.columns:
                feat_arrays[sym][f] = pd.to_numeric(ctx[f], errors="coerce").to_numpy(dtype=float)
            else:
                feat_arrays[sym][f] = np.full(len(axis), np.nan)

    # 按事件时点分组：对每个唯一 t，全截面 asof 值 → percent rank
    for t, g in events.groupby("timestamp"):
        t = int(t)
        cross: dict[str, dict[str, float]] = {}
        for sym in ctxs:
            fa = feat_arrays.get(sym)
            if fa is None:
                continue
            pos = int(np.searchsorted(fa["axis"], t, side="right")) - 1
            if pos < 0:
                continue
            vals = {}
            for f in feats:
                v = fa[f][pos] if pos < len(fa[f]) else np.nan
                vals[f] = v if np.isfinite(v) else np.nan
            cross[sym] = vals
        for f in feats:
            valid = {s: v[f] for s, v in cross.items() if np.isfinite(v[f])}
            if len(valid) < 10:
                continue
            arr = np.array(list(valid.values()))
            for s, v in valid.items():
                events.loc[(events["timestamp"] == t) & (events["symbol"] == s), f"{f}_pct"] = \
                    (arr < v).mean()
                events.loc[(events["timestamp"] == t) & (events["symbol"] == s), f] = v
    # 合成分（cvd_div 高 + washout 深（price_z 低）+ np_z 高）
    events["score"] = (events["cvd_divergence_pct"].fillna(0.5)
                       + (1 - events["price_z_pct"].fillna(0.5))
                       + events["np_z_pct"].fillna(0.5)) / 3

    rng = np.random.default_rng(SEED)
    base = draw_random_events(ctxs, N_BASELINE, rng, max_forward_hours=168,
                              start_ms=LO_MS, end_ms=HI_MS)
    bparts = []
    for bs, bg in base.groupby("symbol", sort=False):
        if bs in ctxs:
            bparts.append(forward_stats(ctxs[bs], bg.copy(), DEFAULT_HORIZONS))
    base_df = pd.concat(bparts, ignore_index=True) if bparts else pd.DataFrame()
    br168 = pd.to_numeric(base_df["ret_168h"], errors="coerce").dropna().to_numpy()

    lines = ["# T1：wash_cvd 事件时点横截面精选（163，Sol 计划阶段1）\n",
             f"- 生成：{datetime.now(timezone.utc):%Y-%m-%d %H:%M UTC}",
             f"- 事件：wash_cvd（115），窗口 2024-06→2026-05（np_z 数据窗），共 {len(events)}",
             "- 横截面：事件时点全 universe asof 特征的截面百分位（非自序列）",
             "- 合成分 = (cvd_div pct + (1−price_z pct) + np_z pct)/3；精选 = top30% 且 np_z≥−1",
             "- 基线：随机横截面；门槛 G：CI/独立窗口/尾切/净增量≥75bps\n",
             "| 组 | n | 168h 均值 | 168h 超额 | CI | 中位数 | 尾切 | W1(2024) | W2(2025) | 净(减成本) | 判定 |",
             "|---|---|---:|---:|---:|---:|---:|---:|---:|---:|---|"]

    def row(label: str, g: pd.DataFrame) -> None:
        n = len(g)
        if n == 0:
            lines.append(f"| {label} | 0 | - | - | - | - | - | - | - | - | 无事件 |")
            return
        r = pd.to_numeric(g["ret_168h"], errors="coerce").dropna().to_numpy()
        ci = bootstrap_ci(r, br168, n_boot=1000, alpha=0.05, seed=SEED)
        thr = np.quantile(r, 0.95)
        tail = r[r <= thr].mean()
        split = int(pd.Timestamp("2025-01-01", tz="UTC").timestamp() * 1000)
        w1 = r[g["timestamp"].to_numpy() < split]
        w2 = r[g["timestamp"].to_numpy() >= split]
        w1s = f"{w1.mean():+.2f}%({len(w1)})" if len(w1) >= 10 else "n<10"
        w2s = f"{w2.mean():+.2f}%({len(w2)})" if len(w2) >= 10 else "n<10"
        net = ci["mean_diff"] - COST_BPS
        verdict = ("样本不足" if n < MIN_EVENTS else
                   "GO_LONG" if ci["ci_lo"] > 0 else
                   "GO_SHORT" if ci["ci_hi"] < 0 else "NO_GO")
        lines.append(f"| {label} | {n} | {r.mean():+.2f}% | {ci['mean_diff']:+.2f}% "
                     f"| [{ci['ci_lo']:+.2f}, {ci['ci_hi']:+.2f}] | {np.median(r):+.2f}% "
                     f"| {tail:+.2f}% | {w1s} | {w2s} | {net:+.2f}% | **{verdict}** |")
        print(f"[163] {label}: n={n} ex168={ci['mean_diff']:+.2f}% med={np.median(r):+.2f}% {verdict}")

    usable = events[events["score"].notna()]
    top = usable[usable["score"] >= usable["score"].quantile(0.7)]
    bot = usable[usable["score"] <= usable["score"].quantile(0.3)]
    top_np = top[top["np_z_pct"].notna() & (top["np_z"] >= -1)] if "np_z" in top else top
    row("wash_cvd 全（窗口锚）", events)
    row("横截面 top30%（合成分）", top)
    row("横截面 bottom30%", bot)
    row("top30% × np_z≥−1（精选）", top_np)

    # 增量对照
    if len(top_np) >= 10 and len(events) >= 10:
        c = bootstrap_ci(pd.to_numeric(top_np["ret_168h"], errors="coerce").dropna().to_numpy(),
                         pd.to_numeric(events["ret_168h"], errors="coerce").dropna().to_numpy(),
                         n_boot=1000, alpha=0.05, seed=SEED + 1)
        lines.append(f"\n增量对照（精选 − 全事件）：{c['mean_diff']:+.2f}% "
                     f"CI[{c['ci_lo']:+.2f}, {c['ci_hi']:+.2f}]"
                     f"（{'≥75bps ✓' if c['mean_diff'] >= 0.75 else '未达 75bps'}）")

    lines.extend(["\n## 裁决\n",
                   "- 精选组 CI 显著 + 中位数/尾切优于全事件 + 独立窗口同号 → 横截面精选有效（T1 通过）。",
                   "- 精选组不优于全事件 → 事件时点横截面无增量，s001 保持等权（T1 关闭）。",
                   "- bottom30% 显著差 → 横截面有区分度（可用作负向过滤）。"])
    REPORT.parent.mkdir(parents=True, exist_ok=True)
    REPORT.write_text("\n".join(lines) + "\n", encoding="utf-8")
    print(f"wrote {REPORT}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
