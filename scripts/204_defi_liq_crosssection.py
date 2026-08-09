r"""204_defi_liq_crosssection.py — 链上清算 × wash_cvd 横截面补充测试（131 的链上版）。

问题：交易所空头强平激增（131 liq_short_z>1）是 wash_cvd 最强门控（+4.44%）。链上
DeFi 清算（Aave v2/v3）是同一压力的另一面还是独立维度？链上清算 regime 是否调制
wash_cvd 事件收益？

数据：
- 链上清算：data/dune/defi_liq_daily.csv（Aave v2+v3 日频事件数，2020-12 → 今）
- wash_cvd 事件：115 口径（coinglass klines 2021-12 → 2026-07）
- 对照：131 交易所清算（coinglass liquidation 2024-06+）日总量 × 链上日清算 → 独立性

检验（对齐 131/grok M1-M3）：
- 分层：事件日链上清算 z（30d rolling）> 1（激增）vs ≤1（常态）→ 24/72/168h 前向
- 增量：激增−常态差 + bootstrap CI（131 同款 +3.97pp 对照）
- 独立性：链上清算日序列 vs 交易所清算日序列相关（phi/corr），事件重叠率

输出：reports/defi_liq_crosssection.md
用法：python scripts/204_defi_liq_crosssection.py
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

from harness.lib.event_study import bootstrap_ci, draw_random_events, forward_stats  # noqa: E402

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

REPORT = PROJECT_ROOT / "reports" / "defi_liq_crosssection.md"
LIQ_CSV = PROJECT_ROOT / "data" / "dune" / "defi_liq_daily.csv"
Z_THR = 1.0
MIN_EVENTS = 20
SEED = 2026
HORIZONS = (24, 72, 168)


def load_chain_liq() -> pd.Series:
    df = pd.read_csv(LIQ_CSV)
    s = pd.Series(pd.to_numeric(df["n_liq"], errors="coerce").to_numpy(),
                  index=pd.to_datetime(df["date"], utc=True))
    return s.sort_index()


def rolling_z(s: pd.Series, window: int = 30) -> pd.Series:
    mean = s.rolling(window, min_periods=max(int(window * 0.5), 5)).mean()
    std = s.rolling(window, min_periods=max(int(window * 0.5), 5)).std()
    return (s - mean) / std.replace(0, np.nan)


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
    events = events[(events["timestamp"] >= int(pd.Timestamp("2021-12-01", tz="UTC").timestamp() * 1000))].copy()

    chain = load_chain_liq()
    chain_z = rolling_z(chain)
    # 事件 → 事件日链上清算 z（asof 当日）
    ev_date = pd.to_datetime(events["timestamp"], unit="ms", utc=True).dt.floor("D")
    events["liq_z"] = chain_z.reindex(ev_date).to_numpy()
    events["n_liq"] = chain.reindex(ev_date).to_numpy()

    # 前向收益（按 symbol 分组，115 同款）
    fwd_parts = []
    for sym, g in events.groupby("symbol", sort=False):
        fwd_parts.append(forward_stats(ctxs[sym], g.copy(), horizons=HORIZONS))
    ev = pd.concat(fwd_parts, ignore_index=True) if fwd_parts else events
    n_total = len(ev)
    print(f"wash_cvd 事件（2021-12+）: {n_total} | 链上清算覆盖 {ev['liq_z'].notna().sum()}")

    hi = ev[ev["liq_z"] > Z_THR]
    lo = ev[ev["liq_z"] <= Z_THR]
    lines = ["# 链上清算 × wash_cvd 横截面（204，131 的链上版）\n",
             f"- 生成：{datetime.now(timezone.utc):%Y-%m-%d %H:%M UTC}",
             f"- 链上清算：Aave v2+v3 日频事件数（Dune，2020-12→今），30d rolling z",
             f"- 分层：事件日链上清算 z>{Z_THR}（激增）vs ≤{Z_THR}（常态）；wash_cvd 事件 {n_total}\n",
             "| 层 | n | 24h 均值 | 72h 均值 | 168h 均值 | 168h 中位 |",
             "|---|---|---:|---:|---:|---:|"]
    for label, g in [("激增 z>1", hi), ("常态 z≤1", lo)]:
        if len(g) == 0:
            lines.append(f"| {label} | 0 | - | - | - | - |")
            continue
        cells = []
        for h in HORIZONS:
            v = pd.to_numeric(g[f"ret_{h}h"], errors="coerce").dropna()
            cells.append(f"{v.mean():+.2f}%（n={len(v)}）")
        med = pd.to_numeric(g["ret_168h"], errors="coerce").dropna().median()
        lines.append(f"| {label} | {len(g)} | {' | '.join(cells)} | {med:+.2f}% |")

    # 激增−常态差（24h）+ bootstrap CI
    v_hi = pd.to_numeric(hi["ret_24h"], errors="coerce").dropna().to_numpy(dtype=float)
    v_lo = pd.to_numeric(lo["ret_24h"], errors="coerce").dropna().to_numpy(dtype=float)
    lines.append("\n## 激增−常态增量（24h，bootstrap）\n")
    if len(v_hi) >= MIN_EVENTS and len(v_lo):
        ci = bootstrap_ci(v_hi, v_lo, seed=SEED)
        lines.append(f"| 激增−常态差 | {ci['mean_diff']:+.2f}% CI[{ci['ci_lo']:+.2f}, {ci['ci_hi']:+.2f}] | 对照 131 交易所 liq 增量 +3.97pp |")
        print(f"[204] 激增−常态 24h 差 {ci['mean_diff']:+.2f}% CI[{ci['ci_lo']:+.2f}, {ci['ci_hi']:+.2f}]")
    else:
        lines.append(f"样本不足（hi={len(v_hi)}, lo={len(v_lo)}）")

    # 独立性：链上 vs 交易所清算（coinglass 2024-06+ 重叠窗）
    lines.append("\n## 独立性：链上 vs 交易所清算（2024-06→2026-06）\n")
    cg_total: pd.Series | None = None
    for sym in symbols:
        p = m113.COINGLASS_RAW1H / "liquidation" / f"{sym}.parquet"
        if not p.exists():
            continue
        df = pd.read_parquet(p)
        if not {"time", "long_liquidation_usd", "short_liquidation_usd"}.issubset(df.columns):
            continue
        tot = (pd.to_numeric(df["long_liquidation_usd"], errors="coerce").fillna(0)
               + pd.to_numeric(df["short_liquidation_usd"], errors="coerce").fillna(0))
        s = pd.Series(tot.to_numpy(), index=pd.to_datetime(
            pd.to_numeric(df["time"]), unit="ms", utc=True).dt.floor("D"))
        s = s.groupby(s.index).sum()
        cg_total = s if cg_total is None else cg_total.add(s, fill_value=0)
    if cg_total is not None:
        cg_daily = cg_total[cg_total.index >= pd.Timestamp("2024-06-01", tz="UTC")]
        ch_daily = chain[chain.index >= pd.Timestamp("2024-06-01", tz="UTC")]
        both = pd.concat([cg_daily, ch_daily], axis=1, join="inner").dropna()
        if len(both) > 100:
            corr = np.corrcoef(both.iloc[:, 0], both.iloc[:, 1])[0, 1]
            # 事件重叠：双方各自 z>2 的日（72h 冷却）
            def peak_days(s: pd.Series) -> set:
                z = rolling_z(s)
                evs, last = set(), None
                for d, v in z.items():
                    if v > 2.0 and (last is None or (d - last).days >= 3):
                        evs.add(d)
                        last = d
                return evs
            cg_pk, ch_pk = peak_days(both.iloc[:, 0]), peak_days(both.iloc[:, 1])
            lines.append(f"| 相关（日清算量） | {corr:.3f} | 链上峰值日 {len(ch_pk)} / 交易所峰值日 {len(cg_pk)} / 重叠 {len(ch_pk & cg_pk)} |")
            print(f"[204] 独立性: corr={corr:.3f} 峰值重叠 {len(ch_pk & cg_pk)}")
        else:
            lines.append("| 重叠样本不足 | - | - |")

    # 双清算共振（gpt-5.6-sol 建议 #4）：wash_cvd 事件日 链上z×交易所z 2×2
    cg_daily = cg_total[cg_total.index >= pd.Timestamp("2024-06-01", tz="UTC")]
    cg_z = rolling_z(cg_daily)
    ev2 = ev[ev["timestamp"] >= int(pd.Timestamp("2024-06-01", tz="UTC").timestamp() * 1000)].copy()
    ev_date2 = pd.to_datetime(ev2["timestamp"], unit="ms", utc=True).dt.floor("D")
    ev2["ex_z"] = cg_z.reindex(ev_date2).to_numpy()
    both_on = ev2[(ev2["liq_z"] > Z_THR) & (ev2["ex_z"] > Z_THR)]
    neither = ev2[(ev2["liq_z"] <= Z_THR) & (ev2["ex_z"] <= Z_THR)]
    lines.append("\n## 双清算共振（2024-06+，链上z>1 × 交易所z>1）\n")
    lines.append("| 组 | n | 24h 均值 | 72h 均值 | 168h 均值 |")
    lines.append("|---|---|---:|---:|---:|")
    for label, g in [("双激增（共振）", both_on), ("双常态", neither)]:
        if len(g) == 0:
            lines.append(f"| {label} | 0 | - | - | - |")
            continue
        cells = []
        for h in HORIZONS:
            v = pd.to_numeric(g[f"ret_{h}h"], errors="coerce").dropna()
            cells.append(f"{v.mean():+.2f}%（n={len(v)}）")
        lines.append(f"| {label} | {len(g)} | {' | '.join(cells)} |")
    if len(both_on) >= MIN_EVENTS and len(neither):
        v_b = pd.to_numeric(both_on["ret_24h"], errors="coerce").dropna().to_numpy(dtype=float)
        v_n = pd.to_numeric(neither["ret_24h"], errors="coerce").dropna().to_numpy(dtype=float)
        ci = bootstrap_ci(v_b, v_n, seed=SEED)
        lines.append(f"\n共振−双常态 24h 差：{ci['mean_diff']:+.2f}% CI[{ci['ci_lo']:+.2f}, {ci['ci_hi']:+.2f}]")
        print(f"[204] 共振−双常态 24h 差 {ci['mean_diff']:+.2f}% CI[{ci['ci_lo']:+.2f}, {ci['ci_hi']:+.2f}]")

    lines += ["\n## 解读\n",
              "- 链上清算激增日 wash_cvd 更强 → DeFi 压力是 131 的链上同胞，可作门控候选；",
              "- 不显著/负 → 链上清算与交易所清算是不同压力面（DeFi 抵押品 vs 合约杠杆），勿混用；",
              "- 独立性相关高 → 链上无增量（同一压力两面）；低 → 独立维度可补充。"]
    REPORT.parent.mkdir(parents=True, exist_ok=True)
    REPORT.write_text("\n".join(lines) + "\n", encoding="utf-8")
    print(f"wrote {REPORT}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
