r"""158_s009_sensitivity.py — E19 阈值敏感性：新币期窗口 × 确认阈值网格。

157 核心组合（新币期 90 天 × 4h 确认 r4>0）通过全部验证。本脚本检验敏感性：
- 新币期窗口：60 / 90 / 120 天
- 确认阈值：r4 > 0% / > 0.5% / > 1%（更严确认 = 更少事件，更强？）
- 成本敏感性：168h 毛利 − 54bps（1×）/ 108bps（2×）/ 162bps（3×）

通过标准：核心格（90 天 × >0%）保持显著；相邻格方向一致不崩溃；净期望 ≥2× 成本仍正。
数据/基线同 157。

输出：reports/s009_sensitivity.md
用法：python scripts/158_s009_sensitivity.py
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

from harness.lib.event_study import (  # noqa: E402
    DEFAULT_HORIZONS,
    bootstrap_ci,
    draw_random_events,
    forward_stats,
)

REPORT = PROJECT_ROOT / "reports" / "s009_sensitivity.md"
LO_MS = int(pd.Timestamp("2022-01-01", tz="UTC").timestamp() * 1000)
HI_MS = int(pd.Timestamp("2026-06-30", tz="UTC").timestamp() * 1000)
N_BASELINE = 3000
SEED = 2026
MIN_EVENTS = 30
NEW_WINDOWS = [60, 90, 120]
CONFIRM_THS = [0.0, 0.5, 1.0]
COST_1X = 54.0 / 100.0


def listing_dates() -> dict[str, int]:
    out: dict[str, int] = {}
    for sym in m113.load_universe_symbols():
        p = m113.COINGLASS_RAW1H / "klines" / f"{sym}.parquet"
        if not p.exists():
            continue
        try:
            df = pd.read_parquet(p, columns=["open_time"])
            if len(df):
                out[sym] = int(df["open_time"].min())
        except Exception:
            continue
    return out


def main() -> int:
    ctxs = m113.load_price_ctx(m113.load_universe_symbols())
    listed = listing_dates()

    ev_parts = []
    for sym, ctx in ctxs.items():
        if sym not in listed:
            continue
        axis = ctx.index.to_numpy(dtype=np.int64)
        close = ctx["close"].to_numpy(dtype=float)
        s = pd.Series(close)
        z = (s - s.rolling(720, min_periods=360).mean()) / s.rolling(720, min_periods=360).std().replace(0, np.nan)
        ret24 = s.pct_change(24) * 100.0
        fired = np.isfinite(z.to_numpy()) & np.isfinite(ret24.to_numpy()) & \
            ((z.to_numpy() < -2.0) | (ret24.to_numpy() < -8.0))
        events = []
        last = -10**18
        for i in np.flatnonzero(fired):
            t = int(axis[i])
            if t - last >= 72 * 3_600_000:
                events.append(t)
                last = t
        if events:
            ev_parts.append(pd.DataFrame({"symbol": sym, "timestamp": events}))
    events = pd.concat(ev_parts, ignore_index=True) if ev_parts else pd.DataFrame(
        columns=["symbol", "timestamp"])
    events = events[(events["timestamp"] >= LO_MS) & (events["timestamp"] <= HI_MS)].copy()
    events["listing_ms"] = events["symbol"].map(listed)
    events["age_days"] = (events["timestamp"] - events["listing_ms"]) / (24 * 3_600_000)

    fwd = []
    for sym, g in events.groupby("symbol", sort=False):
        ctx = ctxs[sym]
        axis = ctx.index.to_numpy(dtype=np.int64)
        close = ctx["close"].to_numpy(dtype=float)
        rows = []
        for _, ev_row in g.iterrows():
            t = int(ev_row["timestamp"])
            pos = int(np.searchsorted(axis, t, side="right")) - 1
            if pos < 0 or pos + 168 >= len(close):
                continue
            r4 = (close[pos + 4] / close[pos] - 1) * 100.0
            r168 = (close[pos + 168] / close[pos] - 1) * 100.0
            if np.isfinite(r4) and np.isfinite(r168):
                rows.append({"symbol": sym, "t": t, "age_days": ev_row["age_days"],
                             "r4": r4, "r168": r168})
        if rows:
            fwd.append(pd.DataFrame(rows))
    ev = pd.concat(fwd, ignore_index=True) if fwd else pd.DataFrame()
    print(f"washout 事件 {len(ev)}")

    rng = np.random.default_rng(SEED)
    base = draw_random_events(ctxs, N_BASELINE, rng, max_forward_hours=168,
                              start_ms=LO_MS, end_ms=HI_MS)
    bparts = []
    for bs, bg in base.groupby("symbol", sort=False):
        if bs in ctxs:
            bparts.append(forward_stats(ctxs[bs], bg.copy(), DEFAULT_HORIZONS))
    base_df = pd.concat(bparts, ignore_index=True) if bparts else pd.DataFrame()
    br168 = pd.to_numeric(base_df["ret_168h"], errors="coerce").dropna().to_numpy()

    lines = ["# s009 阈值敏感性网格（158）\n",
             f"- 生成：{datetime.now(timezone.utc):%Y-%m-%d %H:%M UTC}",
             f"- 网格：新币期 {NEW_WINDOWS} × 确认阈值 {CONFIRM_THS} = 9 格；核心格 = 90 天 × r4>0",
             "- 每格：n / 168h 超额 / CI / 中位数 / 尾切 / 净期望(1×/2×/3× 成本)\n",
             "| 新币期 | 确认阈值 | n | 168h 超额 | CI | 中位数 | 尾切 | 净(2×成本) | 判定 |",
             "|---|---|---:|---:|---:|---:|---:|---:|---|"]

    passed = []
    for nw in NEW_WINDOWS:
        for ct in CONFIRM_THS:
            g = ev[(ev["age_days"] < nw) & (ev["r4"] > ct)]
            n = len(g)
            if n < MIN_EVENTS:
                lines.append(f"| {nw}d | >{ct:.1f}% | {n} | - | - | - | - | - | n<30 |")
                continue
            r = g["r168"].to_numpy(dtype=float)
            ci = bootstrap_ci(r, br168, n_boot=1000, alpha=0.05, seed=SEED)
            thr = np.quantile(r, 0.95)
            tail = r[r <= thr].mean()
            net2 = ci["mean_diff"] - COST_1X * 2
            verdict = ("样本不足" if n < MIN_EVENTS else
                       "GO_LONG" if ci["ci_lo"] > 0 else
                       "GO_SHORT" if ci["ci_hi"] < 0 else "NO_GO")
            ok = verdict == "GO_LONG" and net2 > 0
            if ok:
                passed.append((nw, ct, n, ci["mean_diff"]))
            lines.append(f"| {nw}d | >{ct:.1f}% | {n} | {ci['mean_diff']:+.2f}% "
                         f"| [{ci['ci_lo']:+.2f}, {ci['ci_hi']:+.2f}] | {np.median(r):+.2f}% "
                         f"| {tail:+.2f}% | {net2:+.2f}% | **{verdict}**{' ✅' if ok else ''} |")
            print(f"[158] {nw}d >{ct:.1f}%: n={n} ex168={ci['mean_diff']:+.2f}% med={np.median(r):+.2f}% {verdict}")

    lines.append("\n## 裁决\n")
    if len(passed) >= 5 and (90, 0.0) in [(p[0], p[1]) for p in passed]:
        lines.append(f"- **通过**：9 格中 {len(passed)} 格满足（GO_LONG + 净期望 ≥2× 成本），核心格保持。")
        lines.append(f"- 敏感性稳定：新币期 {sorted(set(p[0] for p in passed))} 天 × 确认 >{min(p[1] for p in passed):.1f}% 均可。")
        lines.append("- → 接线账户 D（新币期 90 天 × r4>0，157 原口径）。")
    else:
        lines.append(f"- **未通过**：仅 {len(passed)}/{9} 格满足（含核心格 {('90d×>0%' in [(f'{p[0]}d×>{p[1]:.0f}%') for p in passed])}）——效应对阈值敏感，需回到 157 重新审视。")
    REPORT.parent.mkdir(parents=True, exist_ok=True)
    REPORT.write_text("\n".join(lines) + "\n", encoding="utf-8")
    print(f"wrote {REPORT}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
