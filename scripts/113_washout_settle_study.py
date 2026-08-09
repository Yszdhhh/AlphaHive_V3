"""113_washout_settle_study.py — A1 washout-and-settle 事件研究（episode 分列）。

命题（机制）：大饼见底窗口，山寨出现**短期出清**（价格深跌、被动盘被洗出），
一旦出现企稳确认（卖压枯竭 / 空头拥挤 / 杠杆被清），向上的轧空燃料仍在 → 做多。

触发（无前视，冷却 72h/币）：
- **washout**：price_z < -2.0（30d 自序列） 或  ret_24h < -8%
- **settle 确认**（任一即可）：
  - conf_cvd  : cvd_divergence > 2.0（价格新低但 CVD 未跟随 = 卖压枯竭）
  - conf_fund : funding < -0.0002（空头拥挤，付费持仓）
  - conf_oi   : OI 24h 变化 < -15%（杠杆多头被强平出清）——仅 2024-06+ 窗口

数据（2026-08-06 核实）：
- price_z/ret_24h/cvd_divergence：coinglass klines（close + taker_buy_quote_volume，
  CVD 代理 = cumsum(2*taker_buy_qv - quote_volume)，覆盖 2021-12+，老币可测 2022 磨底）
- funding：币安 fundingRate 回填（110）
- OI：coinglass oi_ohlc（2024-06 → 2026-05，公开接口无法回填更早）

用法：
  python scripts/113_washout_settle_study.py [--symbols ...] [--n-baseline 3000]
"""
from __future__ import annotations

import argparse
import json
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

COINGLASS_RAW1H = Path(r"C:\Users\10639\Desktop\🔒 加密资产\coinglass_db\raw_1h")
FUNDING_DIR = Path(r"C:\Users\10639\Desktop\加密\binance_free_db\history\funding")
REPORTS_DIR = PROJECT_ROOT / "reports"

BASE_SYMBOLS = ["BTCUSDT", "ETHUSDT", "SOLUSDT"]
HOUR_MS = 3_600_000
FUND_GAP_MS = 9 * HOUR_MS
WASH_PRICE_Z = -2.0
WASH_RET_24H = -8.0
SETTLE_CVD = 2.0
SETTLE_FUND = -0.0002
SETTLE_OI = -15.0

EPISODES = [
    ("2022熊底+FTX底", "2022-01-01", "2023-01-31"),
    ("2023平台蓄力",    "2023-02-01", "2024-05-31"),
    ("2024崩→恢复",    "2024-06-01", "2025-01-31"),
    ("2025顶→熊",      "2025-02-01", "2026-06-30"),
    ("当前筑底(前向)",  "2026-07-01", "2030-01-01"),
]


def load_universe_symbols() -> list[str]:
    with (PROJECT_ROOT / "config" / "universe.json").open("r", encoding="utf-8") as f:
        universe = json.load(f)["symbols"]
    return [item["symbol"] for item in universe if item["symbol"] not in BASE_SYMBOLS]


def load_price_ctx(symbols: list[str]) -> dict[str, pd.DataFrame]:
    """构建价格上下文表：close / ret_24h / price_z / cvd_z / cvd_divergence / oi_24h_chg。"""
    tables: dict[str, pd.DataFrame] = {}
    for s in symbols:
        p = COINGLASS_RAW1H / "klines" / f"{s}.parquet"
        if not p.exists():
            continue
        df = pd.read_parquet(p)
        if "open_time" not in df.columns or "close" not in df.columns:
            continue
        ts = pd.to_numeric(df["open_time"], errors="coerce").to_numpy(dtype=np.int64)
        close = pd.to_numeric(df["close"], errors="coerce").to_numpy(dtype=float)
        qv = pd.to_numeric(df["quote_volume"], errors="coerce").to_numpy(dtype=float) if "quote_volume" in df.columns else np.full(len(ts), np.nan)
        tb = pd.to_numeric(df["taker_buy_quote_volume"], errors="coerce").to_numpy(dtype=float) if "taker_buy_quote_volume" in df.columns else np.full(len(ts), np.nan)
        s_ser = pd.Series(close, index=pd.Index(ts))
        s_ser = s_ser[~s_ser.index.duplicated(keep="last")].sort_index()
        t = pd.DataFrame(index=s_ser.index)
        t["close"] = s_ser.replace([np.inf, -np.inf], np.nan).dropna()
        # 抹假 bar（30d rolling median 偏离 50x）
        med = t["close"].rolling(720, min_periods=360).median()
        ratio = t["close"] / med.replace(0, pd.NA)
        t["close"] = t["close"].where((ratio >= 0.02) & (ratio <= 50.0))
        if len(t) < 800:
            continue
        c = t["close"]
        t["ret_24h"] = c.pct_change(24).replace([np.inf, -np.inf], pd.NA) * 100.0
        # price_z / cvd_z（30d=720h 自序列）
        zwin = 720
        t["price_z"] = rolling_z(c, zwin)
        cvd_series = pd.Series((2 * tb - qv), index=pd.Index(ts)).sort_index()
        cvd_cum = cvd_series.groupby(cvd_series.index).last().sort_index().cumsum()
        cvd_z = rolling_z(cvd_cum.reindex(t.index), zwin)
        t["cvd_z"] = cvd_z
        t["cvd_divergence"] = t["price_z"] - t["cvd_z"]
        # OI 24h 变化（仅 coinglass oi_ohlc 窗口）
        oi_p = COINGLASS_RAW1H / "oi_ohlc" / f"{s}.parquet"
        t["oi_24h_chg"] = np.nan
        if oi_p.exists():
            oi = pd.read_parquet(oi_p)
            oi_ts = pd.to_numeric(oi["time"], errors="coerce").to_numpy(dtype=np.int64)
            oi_c = pd.to_numeric(oi["close"], errors="coerce").to_numpy(dtype=float)
            oi_ser = pd.Series(oi_c, index=pd.Index(oi_ts))
            oi_ser = oi_ser[~oi_ser.index.duplicated(keep="last")].sort_index().reindex(t.index)
            t["oi_24h_chg"] = (oi_ser.pct_change(24) * 100.0).replace([np.inf, -np.inf], pd.NA)
        tables[s] = t
    return tables


def rolling_z(series: pd.Series, window: int) -> pd.Series:
    s = pd.to_numeric(series, errors="coerce")
    minp = max(int(window * 0.5), 2)
    mean = s.rolling(window, min_periods=minp).mean()
    std = s.rolling(window, min_periods=minp).std()
    return (s - mean) / std.where(std > 0)


def load_funding_series(symbols: list[str]) -> dict[str, pd.Series]:
    out: dict[str, pd.Series] = {}
    for s in symbols:
        p = FUNDING_DIR / f"{s}.parquet"
        if not p.exists():
            continue
        df = pd.read_parquet(p)
        ts = pd.to_numeric(df["fundingTime"], errors="coerce")
        rate = pd.to_numeric(df["fundingRate"], errors="coerce")
        if len(ts) == 0:
            continue
        out[s] = pd.Series(rate.to_numpy(dtype=float), index=pd.Index(ts.to_numpy(dtype=np.int64)))
    return out


def funding_on_axis(fund_series: pd.Series, axis_ts: np.ndarray) -> np.ndarray:
    idx = pd.Index(axis_ts)
    pos = np.searchsorted(fund_series.index.to_numpy(), idx.to_numpy(), side="right") - 1
    fts = fund_series.index.to_numpy()
    fval = fund_series.to_numpy()
    out = np.full(len(axis_ts), np.nan)
    valid = pos >= 0
    out[valid] = fval[pos[valid]]
    out[valid & ((idx.to_numpy() - fts[pos]) >= FUND_GAP_MS)] = np.nan
    return out


def detect_washout_events(
    sym: str,
    ctx: pd.DataFrame,
    funding: pd.Series | None,
    cooldown_h: float,
    no_settle: bool = False,
) -> pd.DataFrame:
    axis = ctx.index.to_numpy()
    price_z = ctx["price_z"].to_numpy()
    ret24 = ctx["ret_24h"].to_numpy()
    cvd_div = ctx["cvd_divergence"].to_numpy()
    oi24 = ctx["oi_24h_chg"].to_numpy()
    fund = funding_on_axis(funding, axis) if funding is not None else np.full(len(axis), np.nan)

    wash = ((price_z < WASH_PRICE_Z) | (ret24 < WASH_RET_24H)) & np.isfinite(price_z) & np.isfinite(ret24)
    if no_settle:
        fired = wash
        conf_cvd = np.zeros(len(axis), dtype=bool)
        conf_fund = np.zeros(len(axis), dtype=bool)
        conf_oi = np.zeros(len(axis), dtype=bool)
    else:
        conf_cvd = cvd_div > SETTLE_CVD
        conf_fund = fund < SETTLE_FUND
        conf_oi = oi24 < SETTLE_OI
        fired = wash & (conf_cvd | conf_fund | conf_oi)

    cooldown_ms = int(cooldown_h * HOUR_MS)
    events: list[int] = []
    last: int | None = None
    for i in np.flatnonzero(fired):
        ts = int(axis[i])
        if last is None or (ts - last) >= cooldown_ms:
            events.append(ts)
            last = ts
    if not events:
        return pd.DataFrame(columns=["symbol", "timestamp", "feature", "feature_value",
                                     "ret_24h_at_event", "conf_cvd", "conf_fund", "conf_oi"])
    ev = np.array(events, dtype=np.int64)
    return pd.DataFrame({
        "symbol": sym,
        "timestamp": ev,
        "feature": "washout_settle",
        "feature_value": price_z[np.searchsorted(axis, ev)],
        "ret_24h_at_event": ret24[np.searchsorted(axis, ev)],
        "conf_cvd": conf_cvd[np.searchsorted(axis, ev)],
        "conf_fund": conf_fund[np.searchsorted(axis, ev)],
        "conf_oi": conf_oi[np.searchsorted(axis, ev)],
    })


def episode_of(ts_ms: np.ndarray) -> np.ndarray:
    out = np.full(len(ts_ms), "?", dtype=object)
    for i, ts in enumerate(ts_ms):
        for name, s, e in EPISODES:
            if pd.Timestamp(s, tz="UTC").timestamp() * 1000 <= ts < pd.Timestamp(e, tz="UTC").timestamp() * 1000:
                out[i] = name
                break
    return out


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--cooldown", type=float, default=72.0)
    parser.add_argument("--no-settle", action="store_true",
                        help="消融：只 washout，不要 settle 确认（对比确认是否贡献 edge）")
    parser.add_argument("--min-events", type=int, default=30)
    parser.add_argument("--n-baseline", type=int, default=3000)
    parser.add_argument("--seed", type=int, default=2026)
    parser.add_argument("--symbols", type=str, default=None)
    args = parser.parse_args()

    symbols = args.symbols.split(",") if args.symbols else load_universe_symbols()
    ctxs = load_price_ctx(symbols)
    fundings = load_funding_series(symbols)
    print(f"价格上下文 {len(ctxs)} | funding 覆盖 {len(fundings)}")

    rng = np.random.default_rng(args.seed)
    evs: list[pd.DataFrame] = []
    for sym, ctx in ctxs.items():
        ev = detect_washout_events(sym, ctx, fundings.get(sym), args.cooldown, args.no_settle)
        if not ev.empty:
            evs.append(ev)
    events = pd.concat(evs, ignore_index=True) if evs else pd.DataFrame(
        columns=["symbol", "timestamp", "feature", "feature_value", "ret_24h_at_event",
                 "conf_cvd", "conf_fund", "conf_oi"])
    if events.empty:
        print("无事件。")
        return
    events["episode"] = episode_of(events["timestamp"].to_numpy())
    fwd_parts = []
    for sym, g in events.groupby("symbol", sort=False):
        fwd_parts.append(forward_stats(ctxs[sym], g.copy(), horizons=DEFAULT_HORIZONS))
    events = pd.concat(fwd_parts, ignore_index=True) if fwd_parts else events
    events.to_csv(REPORTS_DIR / "washout_settle_events.csv", index=False)
    print(f"事件总数: {len(events)}")

    lines: list[str] = []
    lines.append("# A1 washout-and-settle 事件研究（episode 分列）\n")
    lines.append(f"- 生成: {pd.Timestamp.now(tz='UTC'):%Y-%m-%d %H:%M UTC}")
    lines.append(f"- washout: price_z<{WASH_PRICE_Z} 或 ret_24h<{WASH_RET_24H}%  |  "
                 f"{'[消融] 无 settle 确认' if args.no_settle else f'settle 确认任一: cvd_div>{SETTLE_CVD} / funding<{SETTLE_FUND} / oi_24h<{SETTLE_OI}%'}  |  冷却 {args.cooldown}h")
    lines.append(f"- 可用 symbols: {len(ctxs)}（老币含 2022/2023，新币自上市）")
    lines.append(f"- 基线: 同 episode 区间随机 symbol×时点横截面，bootstrap 95% CI")
    lines.append("> **多 episode 一致性优先**；当前筑底窗口只有前向影子。\n")

    lines.append("## 各 episode 汇总\n")
    lines.append("| episode | 事件数 | 4h均 | 24h均 | 24h超额 | 24h CI | 72h超额 | 168h超额 | 判定 |")
    lines.append("|---|---|---|---|---|---|---|---|---|")
    per_ep_rows = []
    for name, s, e in EPISODES:
        sub = events[events["episode"] == name]
        n_ev = len(sub)
        row: dict = {"episode": name, "n": n_ev}
        if n_ev > 0:
            start_ms = int(pd.Timestamp(s, tz="UTC").timestamp() * 1000)
            end_ms = int(pd.Timestamp(e, tz="UTC").timestamp() * 1000)
            base = draw_random_events(ctxs, args.n_baseline, rng, max_forward_hours=168, start_ms=start_ms, end_ms=end_ms)
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
                bs_v = pd.to_numeric(base_stats[col], errors="coerce").dropna().to_numpy() if not base_stats.empty else np.array([])
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
    pd.DataFrame(per_ep_rows).to_csv(REPORTS_DIR / "washout_settle_episodes.csv", index=False)

    # 确认信号分列（哪些 settle 确认主导）
    lines.append("\n## settle 确认分布\n")
    conf_rows = events.groupby("episode")[["conf_cvd", "conf_fund", "conf_oi"]].mean().round(2)
    conf_n = events.groupby("episode")[["conf_cvd", "conf_fund", "conf_oi"]].count()
    lines.append("| episode | 事件数 | conf_cvd占比 | conf_fund占比 | conf_oi占比 |")
    lines.append("|---|---|---|---|---|")
    for ep, r in conf_rows.iterrows():
        lines.append(f"| {ep} | {int(conf_n.loc[ep,'conf_cvd'])} | {r['conf_cvd']:.0%} | {r['conf_fund']:.0%} | {r['conf_oi']:.0%} |")

    out = REPORTS_DIR / f"washout_settle_study{'_no_settle' if args.no_settle else ''}.md"
    REPORTS_DIR.mkdir(parents=True, exist_ok=True)
    out.write_text("\n".join(lines), encoding="utf-8")
    print(f"wrote {out}")
    print("\n=== episode 判定 ===")
    for r in per_ep_rows:
        print(f"  {r['episode']:18s} n={r['n']:5d}  {r['verdict']}")


if __name__ == "__main__":
    main()
