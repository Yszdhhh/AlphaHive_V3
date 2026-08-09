"""115_short_squeeze_combo_study.py — "卖压枯竭"组合信号事件研究（推到全历史多 episode）。

动机：105 的 cvd_bear_divergence 只在 2024-06+ 测过（受 coinglass 衍生维度窗口限制）。
113 用 klines taker 推算的 CVD 可到 2021-12 → cvd_bear 可以推到 2022/2023。本脚本把
"卖压枯竭"各组合变体分 episode 验证，回答：**合并后能否含 2022 在内 4/4 全正**。

变体（全部 Long，cooldown 72h，与 113 同冷却口径以便对照）：
- V1 cvd_bear       : cvd_divergence > 2.0 且 ret_24h < -3%              （105 定义，推到全历史）
- V2 wash_cvd       : washout(price_z<-2.0 或 ret_24h<-8%) 且 cvd_divergence>2.0
- V3 cvd_bear_fund  : V1 且 funding < -0.0002（空头拥挤强化）

对照（已存在于 113 两份报告）：
- V0 纯 washout     : 2022 +0.99 / 2023 +0.70 / 2024 +0.12 / 2025 -0.01（无确认 = 接飞刀）
- V4 wash+任一确认   : 2022 +0.55 / 2023 +1.65 / 2024 +1.01 / 2025 +0.72

数据：coinglass klines（close + taker_buy_quote_volume/quote_volume → CVD 近似）+ 币安 funding（110 回填）。

用法：
  python scripts/115_short_squeeze_combo_study.py [--n-baseline 3000] [--seed 2026]
"""
from __future__ import annotations

import argparse
import importlib.util
import sys
from pathlib import Path

import numpy as np
import pandas as pd

PROJECT_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(PROJECT_ROOT))

from harness.lib.event_study import (
    DEFAULT_HORIZONS,
    bootstrap_ci,
    draw_random_events,
    forward_stats,
)

REPORTS_DIR = PROJECT_ROOT / "reports"

# 复用 113 的清洗/对齐/episode 函数（保证口径与 washout-settle 研究一致）
_spec = importlib.util.spec_from_file_location(
    "m113", str(PROJECT_ROOT / "scripts" / "113_washout_settle_study.py"))
m113 = importlib.util.module_from_spec(_spec)
sys.modules["m113"] = m113
_spec.loader.exec_module(m113)

load_universe_symbols = m113.load_universe_symbols
load_price_ctx = m113.load_price_ctx
load_funding_series = m113.load_funding_series
funding_on_axis = m113.funding_on_axis
episode_of = m113.episode_of
EPISODES = m113.EPISODES

CVD_THRESHOLD = 2.0
RET_BEAR = -3.0
WASH_PRICE_Z = -2.0
WASH_RET_24H = -8.0
FUND_RESET = -0.0002
COOLDOWN_H = 72.0

VARIANT_NAMES = ["cvd_bear", "wash_cvd", "cvd_bear_fund"]


def detect_events(sym: str, ctx: pd.DataFrame, funding: pd.Series | None,
                  variant: str) -> pd.DataFrame:
    axis = ctx.index.to_numpy()
    price_z = ctx["price_z"].to_numpy()
    ret24 = ctx["ret_24h"].to_numpy()
    cvd_div = ctx["cvd_divergence"].to_numpy()
    fund = funding_on_axis(funding, axis) if funding is not None else np.full(len(axis), np.nan)

    finite = np.isfinite(price_z) & np.isfinite(ret24) & np.isfinite(cvd_div)
    if variant == "cvd_bear":
        fired = finite & (cvd_div > CVD_THRESHOLD) & (ret24 < RET_BEAR)
    elif variant == "wash_cvd":
        wash = (price_z < WASH_PRICE_Z) | (ret24 < WASH_RET_24H)
        fired = finite & wash & (cvd_div > CVD_THRESHOLD)
    elif variant == "cvd_bear_fund":
        fired = (finite & (cvd_div > CVD_THRESHOLD) & (ret24 < RET_BEAR)
                 & np.isfinite(fund) & (fund < FUND_RESET))
    else:
        raise ValueError(variant)

    cooldown_ms = int(COOLDOWN_H * 3_600_000)
    events: list[int] = []
    last: int | None = None
    for i in np.flatnonzero(fired):
        ts = int(axis[i])
        if last is None or (ts - last) >= cooldown_ms:
            events.append(ts)
            last = ts
    if not events:
        return pd.DataFrame(columns=["symbol", "timestamp"])
    return pd.DataFrame({
        "symbol": sym,
        "timestamp": np.array(events, dtype=np.int64),
    })


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--n-baseline", type=int, default=3000)
    parser.add_argument("--seed", type=int, default=2026)
    parser.add_argument("--min-events", type=int, default=30)
    parser.add_argument("--symbols", type=str, default=None)
    args = parser.parse_args()

    symbols = args.symbols.split(",") if args.symbols else load_universe_symbols()
    ctxs = load_price_ctx(symbols)
    fundings = load_funding_series(symbols)
    print(f"价格上下文 {len(ctxs)} | funding 覆盖 {len(fundings)}")

    rng = np.random.default_rng(args.seed)

    # 1) 检测各变体事件
    all_ev = {}
    for variant in VARIANT_NAMES:
        evs = []
        for sym, ctx in ctxs.items():
            ev = detect_events(sym, ctx, fundings.get(sym), variant)
            if not ev.empty:
                evs.append(ev)
        events = pd.concat(evs, ignore_index=True) if evs else pd.DataFrame(
            columns=["symbol", "timestamp"])
        events["episode"] = episode_of(events["timestamp"].to_numpy())
        # forward 收益
        fwd_parts = []
        for sym, g in events.groupby("symbol", sort=False):
            fwd_parts.append(forward_stats(ctxs[sym], g.copy(), horizons=DEFAULT_HORIZONS))
        events = pd.concat(fwd_parts, ignore_index=True) if fwd_parts else events
        all_ev[variant] = events
        print(f"  {variant}: {len(events)} 事件")

    # 2) 每变体 × 每 episode bootstrap
    lines: list[str] = []
    lines.append("# 卖压枯竭组合信号事件研究（全历史多 episode）\n")
    lines.append(f"- 生成: {pd.Timestamp.now(tz='UTC'):%Y-%m-%d %H:%M UTC}")
    lines.append(f"- 数据: coinglass klines CVD 近似（可到 2021-12）+ 币安 funding（110 回填）")
    lines.append(f"- 冷却 {COOLDOWN_H}h，方向 Long，基线=同 episode 随机 symbol×时点，bootstrap 95% CI")
    lines.append("> 目的：把 cvd_bear（105，原只测 2024-06+）推到全历史，与 washout 组合看含 2022 是否 4/4 全正。")

    variant_desc = {
        "cvd_bear": "cvd_div>2.0 且 ret_24h<-3%（105 定义）",
        "wash_cvd": "washout(price_z<-2.0 或 ret_24h<-8%) 且 cvd_div>2.0",
        "cvd_bear_fund": "cvd_bear 且 funding<-0.0002",
    }
    per_ep_all = {}
    for variant in VARIANT_NAMES:
        events = all_ev[variant]
        lines.append(f"\n## V: {variant} — {variant_desc[variant]}\n")
        lines.append("| episode | 事件数 | 4h均 | 24h均 | 24h超额 | 24h CI | 72h超额 | 168h超额 | 判定 |")
        lines.append("|---|---|---|---|---|---|---|---|---|")
        per_ep_rows = []
        for name, s, e in EPISODES:
            sub = events[events["episode"] == name]
            n_ev = len(sub)
            row: dict = {"episode": name, "variant": variant, "n": n_ev}
            if n_ev > 0:
                start_ms = int(pd.Timestamp(s, tz="UTC").timestamp() * 1000)
                end_ms = int(pd.Timestamp(e, tz="UTC").timestamp() * 1000)
                base = draw_random_events(ctxs, args.n_baseline, rng, max_forward_hours=168,
                                          start_ms=start_ms, end_ms=end_ms)
                base_parts = []
                if not base.empty:
                    for bs, bg in base.groupby("symbol", sort=False):
                        if bs in ctxs:
                            base_parts.append(forward_stats(ctxs[bs], bg.copy(), DEFAULT_HORIZONS))
                base_stats = pd.concat(base_parts, ignore_index=True) if base_parts else pd.DataFrame()
                ci24 = {}
                for h in DEFAULT_HORIZONS:
                    col = f"ret_{h}h"
                    ev_v = pd.to_numeric(sub[col], errors="coerce").dropna().to_numpy()
                    bs_v = (pd.to_numeric(base_stats[col], errors="coerce").dropna().to_numpy()
                            if not base_stats.empty else np.array([]))
                    ci = bootstrap_ci(ev_v, bs_v, seed=args.seed)
                    row[f"{h}h_mean"] = float(np.nanmean(ev_v)) if len(ev_v) else np.nan
                    row[f"{h}h_excess"] = ci.get("mean_diff", np.nan)
                    row[f"{h}h_ci_lo"] = ci.get("ci_lo", np.nan)
                    row[f"{h}h_ci_hi"] = ci.get("ci_hi", np.nan)
                    if h == 24:
                        ci24 = ci
                n_ev_24 = int(np.isfinite(pd.to_numeric(sub["ret_24h"], errors="coerce")).sum())
                if n_ev_24 < args.min_events or not np.isfinite(ci24.get("ci_lo", np.nan)):
                    verdict = "PENDING" if "前向" in name else f"样本不足(n={n_ev_24}<{args.min_events})"
                elif ci24["ci_lo"] > 0:
                    verdict = "GO_LONG"
                elif ci24["ci_hi"] < 0:
                    verdict = "GO_SHORT"
                else:
                    verdict = "NO_GO"
                row["verdict"] = verdict
                lines.append(
                    f"| {name} | {n_ev} | {row.get('4h_mean', np.nan):.2f}% | {row.get('24h_mean', np.nan):.2f}% "
                    f"| {row.get('24h_excess', np.nan):+.2f}% | "
                    f"[{row.get('24h_ci_lo', np.nan):+.2f}, {row.get('24h_ci_hi', np.nan):+.2f}] "
                    f"| {row.get('72h_excess', np.nan):+.2f}% | {row.get('168h_excess', np.nan):+.2f}% "
                    f"| **{verdict}** |")
            else:
                row["verdict"] = "无事件"
                lines.append(f"| {name} | 0 | - | - | - | - | - | - | **无事件** |")
            per_ep_rows.append(row)
        per_ep_all[variant] = per_ep_rows

    # 3) 跨变体对照表（只看 24h 超额 + 判定）
    lines.append("\n## 跨变体 24h 超额对照\n")
    lines.append("| episode | cvd_bear | wash_cvd | cvd_bear_fund | 参考:纯washout(V0) | 参考:wash+任一确认(V4) |")
    lines.append("|---|---|---|---|---|---|")
    v0 = {"2022熊底+FTX底": 0.99, "2023平台蓄力": 0.70, "2024崩→恢复": 0.12, "2025顶→熊": -0.01}
    v4 = {"2022熊底+FTX底": 0.55, "2023平台蓄力": 1.65, "2024崩→恢复": 1.01, "2025顶→熊": 0.72}
    for name, s, e in EPISODES:
        if "前向" in name:
            continue
        cells = []
        for variant in VARIANT_NAMES:
            row = next((r for r in per_ep_all[variant] if r["episode"] == name), None)
            ex = row.get("24h_excess", np.nan) if row else np.nan
            cells.append(f"{ex:+.2f}%*" if isinstance(ex, float) and np.isfinite(ex) else "无事件")
        lines.append(f"| {name} | " + " | ".join(cells) + f" | {v0[name]:+.2f}% | {v4[name]:+.2f}% |")

    out = REPORTS_DIR / "short_squeeze_combo_study.md"
    REPORTS_DIR.mkdir(parents=True, exist_ok=True)
    out.write_text("\n".join(lines), encoding="utf-8")
    print(f"wrote {out}")


if __name__ == "__main__":
    main()
