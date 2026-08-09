"""112_funding_reset_study.py — A2 funding-reset 事件研究（多 episode 分列）。

命题（机制）：大饼见底窗口，山寨合约空头拥挤——funding 深度为负（空头付钱持仓），
一旦价格企稳不再创新低，费率成本 + 空头回补形成向上不对称 → 做多。

触发（无前视）：
- funding_decimal < FUND_THRESHOLD（默认 -0.0002 = -0.02%/8h，年化 ~-22%）
- 且 ret_24h >= PRICE_STABILIZE（默认 -3%，价格不再深跌 = 企稳）
- 冷却 72h/币，防同一段负费率窗口反复计数

数据（2026-08-06 核实）：
- funding 用币安 fundingRate 回填（110，2022-01→今，8h 小数，唯一口径）
  ——coinglass funding_ohlc.close/100 与币安一致（最大差 4e-6），重叠窗口做验证用。
- 价格用 coinglass klines（close, 2021-12→2026-07）。
- OI 历史公开接口不可回填 → A3 受限；funding 是 A 线里唯一能全 episode 验证的。

关键输出：**按 episode 分列**的收益 + bootstrap CI（多 episode 一致性 > pooled 显著性），
另附阈值敏感性（-0.0001/-0.0002/-0.0005/-0.001）。

用法：
  python scripts/112_funding_reset_study.py [--threshold -0.0002] [--symbols ...]
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

COINGLASS_KLINES = Path(r"C:\Users\10639\Desktop\🔒 加密资产\coinglass_db\raw_1h\klines")
FUNDING_DIR = Path(r"C:\Users\10639\Desktop\加密\binance_free_db\history\funding")
REPORTS_DIR = PROJECT_ROOT / "reports"

BASE_SYMBOLS = ["BTCUSDT", "ETHUSDT", "SOLUSDT"]
HOUR_MS = 3_600_000
FUND_GAP_MS = 9 * HOUR_MS  # funding 8h 一次，>9h 无新快照视为断档，不 ffill

# 大饼宏观阶段（基于 BTC 10 日收盘采样人工划分，2026-08-06）
EPISODES = [
    ("2022熊底+FTX底", "2022-01-01", "2023-01-31"),
    ("2023平台蓄力",    "2023-02-01", "2024-05-31"),
    ("2024崩→恢复",    "2024-06-01", "2025-01-31"),
    ("2025顶→熊",      "2025-02-01", "2026-06-30"),
    ("当前筑底(前向)",  "2026-07-01", "2030-01-01"),
]

FUND_THRESHOLDS = [-0.0001, -0.0002, -0.0005, -0.001]


def load_universe_symbols() -> list[str]:
    with (PROJECT_ROOT / "config" / "universe.json").open("r", encoding="utf-8") as f:
        universe = json.load(f)["symbols"]
    return [item["symbol"] for item in universe if item["symbol"] not in BASE_SYMBOLS]


def load_price_tables(symbols: list[str]) -> dict[str, pd.DataFrame]:
    """symbol -> DataFrame(index=ts ms, close)（coinglass klines，抹假 bar）。"""
    tables: dict[str, pd.DataFrame] = {}
    for s in symbols:
        p = COINGLASS_KLINES / f"{s}.parquet"
        if not p.exists():
            continue
        df = pd.read_parquet(p)
        if "open_time" not in df.columns or "close" not in df.columns:
            continue
        close = pd.to_numeric(df["close"], errors="coerce")
        ts = pd.to_numeric(df["open_time"], errors="coerce")
        t = pd.DataFrame({"close": close.to_numpy(dtype=float)},
                         index=pd.Index(ts.to_numpy(dtype=np.int64), name="timestamp"))
        t = t[~t.index.duplicated(keep="last")].sort_index()
        t = t.replace([np.inf, -np.inf], np.nan).dropna(subset=["close"])
        # 抹假 bar（coinglass 停更断点偶发 50x 偏离，复用 30d rolling median）
        med = t["close"].rolling(720, min_periods=360).median()
        ratio = t["close"] / med.replace(0, pd.NA)
        t["close"] = t["close"].where((ratio >= 0.02) & (ratio <= 50.0))
        tables[s] = t
    return tables


def load_funding_series(symbols: list[str]) -> dict[str, pd.Series]:
    """symbol -> Series(索引=ts ms, 值=funding 小数, 8h 快照 asof 到 1h 轴)。"""
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
        s_ser = pd.Series(rate.to_numpy(dtype=float), index=pd.Index(ts.to_numpy(dtype=np.int64)))
        s_ser = s_ser[~s_ser.index.duplicated(keep="last")].sort_index()
        out[s] = s_ser
    return out


def funding_on_axis(fund_series: pd.Series, axis_ts: np.ndarray) -> pd.Series:
    """把 8h funding 快照 asof 对齐到 1h 轴（无前视；断档 >9h → NaN）。"""
    idx = pd.Index(axis_ts)
    pos = np.searchsorted(fund_series.index.to_numpy(), idx.to_numpy(), side="right") - 1
    out = np.full(len(axis_ts), np.nan)
    valid = pos >= 0
    fts = fund_series.index.to_numpy()
    fval = fund_series.to_numpy()
    out[valid] = fval[pos[valid]]
    gap_ok = (idx.to_numpy() - fts[pos]) < FUND_GAP_MS
    out[~gap_ok] = np.nan
    return pd.Series(out, index=idx)


def detect_funding_reset_events(
    sym: str,
    price: pd.DataFrame,
    funding: pd.Series,
    threshold: float,
    stabilize_pct: float,
    cooldown_h: float,
) -> pd.DataFrame:
    """找 funding-reset 事件。无前视，冷却防重复。"""
    axis = price.index.to_numpy()
    fund = funding_on_axis(funding, axis).to_numpy()
    close = price["close"].to_numpy()
    ret24 = np.full(len(axis), np.nan)
    for i in range(24, len(axis)):
        b = close[i - 24]
        if np.isfinite(b) and b > 0 and np.isfinite(close[i]):
            ret24[i] = (close[i] / b - 1.0) * 100.0
    hit = (fund < threshold) & (ret24 >= stabilize_pct) & np.isfinite(fund) & np.isfinite(ret24)

    cooldown_ms = int(cooldown_h * HOUR_MS)
    events: list[int] = []
    last: int | None = None
    for i in np.flatnonzero(hit):
        ts = int(axis[i])
        if last is None or (ts - last) >= cooldown_ms:
            events.append(ts)
            last = ts
    if not events:
        return pd.DataFrame(columns=["symbol", "timestamp", "feature", "feature_value", "ret_24h_at_event"])
    ev = np.array(events, dtype=np.int64)
    return pd.DataFrame({
        "symbol": sym,
        "timestamp": ev,
        "feature": "funding_reset",
        "feature_value": fund[np.searchsorted(axis, ev)],
        "ret_24h_at_event": ret24[np.searchsorted(axis, ev)],
    })


def episode_of(ts_ms: np.ndarray) -> np.ndarray:
    labels = [e[0] for e in EPISODES]
    out = np.full(len(ts_ms), "?", dtype=object)
    for i, ts in enumerate(ts_ms):
        for name, s, e in EPISODES:
            if pd.Timestamp(s, tz="UTC").timestamp() * 1000 <= ts < pd.Timestamp(e, tz="UTC").timestamp() * 1000:
                out[i] = name
                break
    return out


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--threshold", type=float, default=-0.0002, help="funding 阈值（小数）")
    parser.add_argument("--stabilize", type=float, default=-3.0, help="企稳条件 ret_24h >= 该值（%）")
    parser.add_argument("--cooldown", type=float, default=72.0, help="同 symbol 冷却小时")
    parser.add_argument("--min-events", type=int, default=30, help="episode 判 GO 的最低事件数")
    parser.add_argument("--n-baseline", type=int, default=3000)
    parser.add_argument("--seed", type=int, default=2026)
    parser.add_argument("--symbols", type=str, default=None)
    args = parser.parse_args()

    symbols = args.symbols.split(",") if args.symbols else load_universe_symbols()
    prices = load_price_tables(symbols)
    fundings = load_funding_series(symbols)
    covered = [s for s in symbols if s in prices and s in fundings and len(fundings[s]) > 100]
    print(f"价格表 {len(prices)} | funding 覆盖 {len(fundings)} | 可用 {len(covered)} symbols")

    # 触发
    rng = np.random.default_rng(args.seed)
    evs: list[pd.DataFrame] = []
    for sym in covered:
        ev = detect_funding_reset_events(sym, prices[sym], fundings[sym],
                                         args.threshold, args.stabilize, args.cooldown)
        if not ev.empty:
            evs.append(ev)
    events = pd.concat(evs, ignore_index=True) if evs else pd.DataFrame(
        columns=["symbol", "timestamp", "feature", "feature_value", "ret_24h_at_event"])
    if events.empty:
        print("无事件。")
        return
    events["episode"] = episode_of(events["timestamp"].to_numpy())
    # forward 收益
    fwd_parts = []
    for sym, g in events.groupby("symbol", sort=False):
        ft = forward_stats(prices[sym], g.copy(), horizons=DEFAULT_HORIZONS)
        fwd_parts.append(ft)
    events = pd.concat(fwd_parts, ignore_index=True) if fwd_parts else events
    events.to_csv(REPORTS_DIR / "funding_reset_events.csv", index=False)
    print(f"事件总数: {len(events)}")

    # 阈值敏感性（pooled）
    sens_rows = []
    for th in FUND_THRESHOLDS:
        n = 0
        for sym in covered:
            ev = detect_funding_reset_events(sym, prices[sym], fundings[sym], th, args.stabilize, args.cooldown)
            n += len(ev)
        sens_rows.append({"threshold": th, "n_events": n})
    sens = pd.DataFrame(sens_rows)

    # 每 episode：事件 vs 同 episode 随机基线 bootstrap
    lines: list[str] = []
    lines.append("# A2 funding-reset 事件研究（episode 分列）\n")
    lines.append(f"- 生成: {pd.Timestamp.now(tz='UTC'):%Y-%m-%d %H:%M UTC}")
    lines.append(f"- 触发: funding < {args.threshold} 且 ret_24h >= {args.stabilize}%，冷却 {args.cooldown}h，方向 Long")
    lines.append(f"- funding 源: 币安 fundingRate 回填（110），coinglass 交叉验证一致")
    lines.append(f"- 可用 symbols: {len(covered)}  (老币覆盖 2022/2023 磨底；新币自上市起)")
    lines.append(f"- 基线: 同 episode 区间随机 symbol×时点横截面，bootstrap 95% CI")
    lines.append("> **多 episode 一致性优先**：edge 应在每个底部 episode 都显著为正；")
    lines.append("> 当前筑底窗口只有前向影子，历史判定不适用。\n")

    # 汇总表
    lines.append("## 各 episode 汇总\n")
    lines.append("| episode | 事件数 | 4h均 | 24h均 | 24h超额 | 24h CI | 72h超额 | 168h超额 | 判定 |")
    lines.append("|---|---|---|---|---|---|---|---|---|")
    per_ep_rows = []
    for name, s, e in EPISODES:
        sub = events[events["episode"] == name]
        n_ev = len(sub)
        row: dict = {"episode": name, "n": n_ev}
        ci24 = {}
        if n_ev > 0:
            start_ms = int(pd.Timestamp(s, tz="UTC").timestamp() * 1000)
            end_ms = int(pd.Timestamp(e, tz="UTC").timestamp() * 1000)
            base = draw_random_events(prices, args.n_baseline, rng, max_forward_hours=168,
                                      start_ms=start_ms, end_ms=end_ms)
            base_parts = []
            if not base.empty:
                for bs, bg in base.groupby("symbol", sort=False):
                    if bs in prices:
                        base_parts.append(forward_stats(prices[bs], bg.copy(), DEFAULT_HORIZONS))
            base_stats = pd.concat(base_parts, ignore_index=True) if base_parts else pd.DataFrame()
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
    pd.DataFrame(per_ep_rows).to_csv(REPORTS_DIR / "funding_reset_episodes.csv", index=False)

    # 阈值敏感性
    lines.append("\n## 阈值敏感性（pooled）\n")
    lines.append("| threshold | 事件数 |")
    lines.append("|---|---|")
    for _, r in sens.iterrows():
        lines.append(f"| {r['threshold']} | {int(r['n_events'])} |")

    # 老币子集在 2022/2023 的覆盖说明
    pre24 = [s for s in covered if fundings[s].index.min() <= pd.Timestamp("2023-01-01").timestamp() * 1000]
    lines.append(f"\n## 覆盖\n\n可测 2023-01 前（2022 磨底/FTX 底）的 symbols: **{len(pre24)}** 个")
    lines.append("\n> ⚠️ 老币子集（上市早）才有 2022/2023 funding；新币自上市起，早期 episode 币种少。")

    out = REPORTS_DIR / "funding_reset_study.md"
    REPORTS_DIR.mkdir(parents=True, exist_ok=True)
    out.write_text("\n".join(lines), encoding="utf-8")
    print(f"wrote {out}")
    print("\n=== episode 判定 ===")
    for r in per_ep_rows:
        print(f"  {r['episode']:18s} n={r['n']:5d}  {r['verdict']}")


if __name__ == "__main__":
    main()
