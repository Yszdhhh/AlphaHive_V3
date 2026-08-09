r"""185_election_cycle.py — 选举周期验证（用户说法："中期大选后 SPX 历史几乎 100% 上涨"）。

两部分：
1. SPX 历史（^GSPC，yfinance 1928+）：中期/总统选举日后 1/3/6/12 个月收益 vs 非选举窗口
   —— 方向性观察（n≈18 中期 + 24 总统，功效低，诚实标注）
2. wash_cvd 事件 × 选举后 6 个月窗口（我们自己的 1348 事件，样本充足）：
   选举后 wash_cvd 是否比选举前（184 发现 -3.42%）更强 → "前避险后反弹"验证

输出：reports/election_cycle.md
用法：python scripts/185_election_cycle.py
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

REPORT = PROJECT_ROOT / "reports" / "election_cycle.md"
LO_MS = int(pd.Timestamp("2022-01-01", tz="UTC").timestamp() * 1000)
HI_MS = int(pd.Timestamp("2026-06-30", tz="UTC").timestamp() * 1000)
MIN_EVENTS = 30
N_BASELINE = 3000
SEED = 2026

# 中期选举（非总统年 11 月）1950-2026
MIDTERM = ["1950-11-07", "1954-11-02", "1958-11-04", "1962-11-06", "1966-11-08",
           "1970-11-03", "1974-11-05", "1978-11-07", "1982-11-02", "1986-11-04",
           "1990-11-06", "1994-11-08", "1998-11-03", "2002-11-05", "2006-11-07",
           "2010-11-02", "2014-11-04", "2018-11-06", "2022-11-08", "2026-11-03"]
# 总统选举（1952-2024）
PRESIDENTIAL = ["1952-11-04", "1956-11-06", "1960-11-08", "1964-11-03", "1968-11-05",
                "1972-11-07", "1976-11-02", "1980-11-04", "1984-11-06", "1988-11-08",
                "1992-11-03", "1996-11-05", "2000-11-07", "2004-11-02", "2008-11-04",
                "2012-11-06", "2016-11-08", "2020-11-03", "2024-11-05"]


def main() -> int:
    # ---------- SPX 历史 ----------
    import yfinance as yf
    spx = yf.download("^GSPC", start="1928-01-01", interval="1d", progress=False,
                      auto_adjust=False)["Close"]
    spx = spx.dropna()
    print(f"SPX 历史：{spx.index.min().date()} → {spx.index.max().date()}（{len(spx)} 日）")

    lines = ["# 选举周期验证（185）\n",
             f"- 生成：{datetime.now(timezone.utc):%Y-%m-%d %H:%M UTC}",
             f"- SPX 历史 {spx.index.min().date()} → {spx.index.max().date()}；中期选举 n={len(MIDTERM)} 总统 n={len(PRESIDENTIAL)}",
             "- ⚠️ 选举样本功效低（n≈20/类），方向性观察；wash_cvd 分层用我们自己的 1348 事件\n",
             "## 1. SPX 选举后收益（历史）\n",
             "| 类型 | 窗口 | n | 上涨概率 | 均值 | 中位 |",
             "|---|---|---:|---:|---:|---|"]

    for label, days in [("中期", MIDTERM), ("总统", PRESIDENTIAL)]:
        for horizon_days, hname in [(21, "1月"), (63, "3月"), (126, "6月"), (252, "12月")]:
            rets = []
            for d in days:
                t0 = pd.Timestamp(d)
                if t0 not in spx.index and t0 > spx.index.min():
                    t0 = spx.index[spx.index.searchsorted(t0) - 1] if spx.index.searchsorted(t0) > 0 else t0
                if t0 < spx.index.min() or t0 > spx.index.max():
                    continue
                i0 = spx.index.searchsorted(t0)
                i1 = spx.index.searchsorted(t0 + pd.Timedelta(days=horizon_days))
                if i1 >= len(spx) or i1 <= i0:
                    continue
                rets.append(spx.iloc[i1] / spx.iloc[i0] - 1)
            if rets:
                r = np.array(rets)
                lines.append(f"| {label}选举后 | {hname} | {len(r)} | {100 * (r > 0).mean():.0f}% "
                             f"| {r.mean() * 100:+.1f}% | {np.median(r) * 100:+.1f}% |")
                print(f"[185] {label}后{hname}: n={len(r)} 上涨 {100 * (r > 0).mean():.0f}% "
                      f"均值 {r.mean() * 100:+.1f}%")

    # ---------- wash_cvd × 选举窗口 ----------
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
    events = events[(events["timestamp"] >= LO_MS) & (events["timestamp"] <= HI_MS)].copy()
    fwd_parts = []
    for sym, g in events.groupby("symbol", sort=False):
        if sym in ctxs:
            fwd_parts.append(forward_stats(ctxs[sym], g.copy(), DEFAULT_HORIZONS))
    events = pd.concat(fwd_parts, ignore_index=True) if fwd_parts else events
    ev_day = pd.to_datetime(events["timestamp"].to_numpy(), unit="ms", utc=True).tz_localize(None).normalize()

    all_elec = pd.to_datetime(MIDTERM + PRESIDENTIAL)
    pre = np.zeros(len(events), dtype=bool)
    post = np.zeros(len(events), dtype=bool)
    for ed in all_elec:
        pre |= (ev_day >= ed - pd.Timedelta(days=182)) & (ev_day < ed)
        post |= (ev_day >= ed) & (ev_day <= ed + pd.Timedelta(days=182))
    events["ELEC_PRE"] = pre.astype(float)
    events["ELEC_POST"] = post.astype(float)

    rng = np.random.default_rng(SEED)
    base = draw_random_events(ctxs, N_BASELINE, rng, max_forward_hours=168,
                              start_ms=LO_MS, end_ms=HI_MS)
    bparts = []
    for bs, bg in base.groupby("symbol", sort=False):
        if bs in ctxs:
            bparts.append(forward_stats(ctxs[bs], bg.copy(), DEFAULT_HORIZONS))
    base_df = pd.concat(bparts, ignore_index=True) if bparts else pd.DataFrame()
    br168 = pd.to_numeric(base_df["ret_168h"], errors="coerce").dropna().to_numpy()

    lines.append("\n## 2. wash_cvd × 选举窗口（我们的 1348 事件）\n")
    lines.append("| 窗口 | n | 168h 超额 | CI | 中位数 | 判定 |")
    lines.append("|---|---|---:|---:|---:|---|")
    for label, g in [("选举前 6 个月", events[events["ELEC_PRE"] == 1]),
                     ("选举后 6 个月", events[events["ELEC_POST"] == 1]),
                     ("非选举窗口", events[(events["ELEC_PRE"] == 0) & (events["ELEC_POST"] == 0)])]:
        n = len(g)
        if n < MIN_EVENTS:
            lines.append(f"| {label} | {n} | - | - | - | 样本不足 |")
            continue
        r = pd.to_numeric(g["ret_168h"], errors="coerce").dropna().to_numpy()
        ci = bootstrap_ci(r, br168, n_boot=1000, alpha=0.05, seed=SEED)
        verdict = ("样本不足" if n < MIN_EVENTS else
                   "GO_LONG" if ci["ci_lo"] > 0 else
                   "GO_SHORT" if ci["ci_hi"] < 0 else "NO_GO")
        lines.append(f"| {label} | {n} | {ci['mean_diff']:+.2f}% "
                     f"| [{ci['ci_lo']:+.2f}, {ci['ci_hi']:+.2f}] | {np.median(r):+.2f}% | **{verdict}** |")
        print(f"[185] {label}: n={n} ex168={ci['mean_diff']:+.2f}% {verdict}")

    lines.extend(["\n## 解读\n",
                  "- SPX 选举后上涨概率（历史）：若中期 6-12 月 ≈90%+ → 用户说法部分成立（方向性）。",
                  "- wash_cvd 选举后窗口显著强于选举前（184 的 -3.42%）→ '前避险后反弹'成立，选举是 wash_cvd 的门控维度（s016 候选）。",
                  "- 2026-11-03 中期临近：当前 2026-08 处于选举前窗口 → wash_cvd 前向预期保守。"])
    REPORT.parent.mkdir(parents=True, exist_ok=True)
    REPORT.write_text("\n".join(lines) + "\n", encoding="utf-8")
    print(f"wrote {REPORT}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
