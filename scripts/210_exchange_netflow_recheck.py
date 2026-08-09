r"""210_exchange_netflow_recheck.py — 交易所净流入复核（Dune 版，140 的 ETH/单所/复核）。

140（CoinMetrics BTC 日频全所）：wash_cvd 事件日-1 净流入高三分位 24h +2.24%（描述性待复核）。
本脚本用 Dune：币安 ETH 钱包标签 → 日频 ETH 净流入（单所、2021-12→今），同口径分层复核：
高/中/低三分位 → wash_cvd 前向。判定：高三分位显著 > 低 → 140 结论在更细口径成立；
否则 → 140 的 +2.24% 是 CoinMetrics 口径伪影/不稳健。

输出：reports/exchange_netflow_recheck.md
用法：python scripts/210_exchange_netflow_recheck.py
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

from harness.lib.event_study import bootstrap_ci, forward_stats  # noqa: E402

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

REPORT = PROJECT_ROOT / "reports" / "exchange_netflow_recheck.md"
NETFLOW_CSV = PROJECT_ROOT / "data" / "dune" / "binance_eth_netflow_daily.csv"
MIN_N = 30
SEED = 2026
HORIZONS = (24, 72, 168)


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

    nf = pd.read_csv(NETFLOW_CSV)
    nf["date"] = pd.to_datetime(nf["date"], utc=True)
    nf = nf.set_index("date")["eth_netflow"].sort_index()
    nf_z = (nf - nf.rolling(30, min_periods=15).mean()) / nf.rolling(30, min_periods=15).std().replace(0, np.nan)
    # 事件日-1 asof（140 同款，避免前视）
    ev_prev = (pd.to_datetime(events["timestamp"], unit="ms", utc=True).dt.floor("D")
               - pd.Timedelta(days=1))
    events = events.assign(prev_day=ev_prev)
    events["nf"] = nf_z.reindex(ev_prev).to_numpy()
    ev = events.dropna(subset=["nf"]).copy()
    print(f"事件 {len(events)} | 有净流入样本 {len(ev)}")

    fwd_parts = []
    for sym, g in ev.groupby("symbol", sort=False):
        fwd_parts.append(forward_stats(ctxs[sym], g.copy(), horizons=HORIZONS))
    ev = pd.concat(fwd_parts, ignore_index=True) if fwd_parts else ev

    ev["tercile"] = pd.qcut(ev["nf"], 3, labels=[0, 1, 2], duplicates="drop")
    hi, mid, lo = ev[ev["tercile"] == 2], ev[ev["tercile"] == 1], ev[ev["tercile"] == 0]
    lines = ["# 交易所净流入复核（210，Dune ETH/币安单所 vs 140 BTC/全所）\n",
             f"- 生成：{datetime.now(timezone.utc):%Y-%m-%d %H:%M UTC}",
             f"- 数据：币安 ETH 钱包日净流 z（Dune，2021-12→今）；事件日-1 asof（140 同款）\n",
             "| 层 | n | 24h 均值 | 72h 均值 | 168h 均值 | 168h 中位 |",
             "|---|---|---:|---:|---:|---:|"]
    for label, g in [("净流入高（T3）", hi), ("中", mid), ("净流入低（T1）", lo)]:
        cells = []
        for h in HORIZONS:
            v = pd.to_numeric(g[f"ret_{h}h"], errors="coerce").dropna()
            cells.append(f"{v.mean():+.2f}%（n={len(v)}）")
        med = pd.to_numeric(g["ret_168h"], errors="coerce").dropna().median()
        lines.append(f"| {label} | {len(g)} | {' | '.join(cells)} | {med:+.2f}% |")

    v_hi = pd.to_numeric(hi["ret_24h"], errors="coerce").dropna().to_numpy(dtype=float)
    v_lo = pd.to_numeric(lo["ret_24h"], errors="coerce").dropna().to_numpy(dtype=float)
    lines.append("\n## 高−低增量（24h）\n")
    if len(v_hi) >= MIN_N and len(v_lo) >= MIN_N:
        ci = bootstrap_ci(v_hi, v_lo, seed=SEED)
        lines.append(f"| 高−低 | {ci['mean_diff']:+.2f}% CI[{ci['ci_lo']:+.2f}, {ci['ci_hi']:+.2f}] | "
                     f"对照 140 描述性 +2.24% |")
        print(f"[210] 高−低 24h {ci['mean_diff']:+.2f}% CI[{ci['ci_lo']:+.2f}, {ci['ci_hi']:+.2f}]")
    else:
        lines.append(f"样本不足（{len(v_hi)}/{len(v_lo)}）")

    lines += ["\n## 解读\n",
              "- 高−低显著为正 → 140 的 +2.24% 在 ETH/单所/小时更细口径成立（净流入高 = 资金进场确认）；",
              "- CI 含 0 → 140 结论不稳健（CoinMetrics 全所 BTC 口径的伪影）→ 关闭。",
              "- ⚠️ 资产不同（ETH vs BTC）、所不同（币安 vs 全所）：成立则方向一致，不成立则口径差异。"]
    REPORT.parent.mkdir(parents=True, exist_ok=True)
    REPORT.write_text("\n".join(lines) + "\n", encoding="utf-8")
    print(f"wrote {REPORT}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
