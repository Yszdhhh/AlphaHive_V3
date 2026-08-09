"""106_regime_engine.py — 市场 regime 门控 CLI（Phase 2）。

把事件研究结果按触发时点的市场 regime 分层，回答：
"cvd_bear_divergence 这个信号在哪个市场状态最强？"——直接验证外部假设
（BTC 见底/存储见顶窗口）是否成立。

纯函数在 harness/lib/regime_engine.py（可单测）；本文件只做数据加载 + 报告。
输入 reports/event_study_events.csv（105 输出），输出 event_study_by_regime.md。

只读回测，无订单路径（符合宪法）。
用法：
  python scripts/106_regime_engine.py [--trigger cvd_bear_divergence]
"""
from __future__ import annotations

import argparse
import sys
from pathlib import Path

import numpy as np
import pandas as pd

PROJECT_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(PROJECT_ROOT))

from harness.lib.regime_engine import assign_regime, btc_state, load_regimes, sp500_below_50d

RAW_1H = Path(r"C:\Users\10639\Desktop\🔒 加密资产\coinglass_db\raw_1h")
MACRO_ROOT = Path(r"C:\Users\10639\Desktop\🔒 加密资产\coinglass_db\macro")
EVENTS_PATH = PROJECT_ROOT / "reports" / "event_study_events.csv"
OUT_PATH = PROJECT_ROOT / "reports" / "event_study_by_regime.md"
BTC = "BTCUSDT"


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--events-path", default=str(EVENTS_PATH))
    parser.add_argument("--trigger", default=None, help="只分析某 trigger（默认全部）")
    args = parser.parse_args()

    events_path = Path(args.events_path)
    if not events_path.exists():
        print(f"[106] 无事件明细 {events_path}，先跑 105_event_study.py")
        return
    events = pd.read_csv(events_path)

    btc = pd.read_parquet(RAW_1H / "klines" / f"{BTC}.parquet")
    btc_close = pd.to_numeric(btc.set_index("open_time")["close"], errors="coerce").sort_index()
    btc_ts = btc_close.index.to_numpy(dtype=np.int64)
    btc_dd, btc_above = btc_state(btc_close)

    sp = pd.read_parquet(MACRO_ROOT / "SP500.parquet")
    sp_idx = sp.index.to_numpy(dtype=np.int64)  # datetime64[ms] → ms int
    sp_close = pd.Series(pd.to_numeric(sp["close"], errors="coerce").to_numpy(), index=sp_idx).sort_index()
    sp_ts = sp_close.index.to_numpy(dtype=np.int64)
    sp_below = sp500_below_50d(sp_close)

    cfg = load_regimes()
    ev_ts = pd.to_numeric(events["timestamp"], errors="coerce").to_numpy(dtype=np.int64)
    events["regime"] = assign_regime(ev_ts, btc_dd, btc_above, btc_ts, sp_below, sp_ts, cfg)

    triggers = [args.trigger] if args.trigger else sorted(events["trigger"].unique())
    lines: list[str] = []
    lines.append("# AlphaHive V3 事件研究 × regime 门控\n")
    lines.append(f"- 生成: {pd.Timestamp.now(tz='UTC'):%Y-%m-%d %H:%M UTC}")
    lines.append(f"- regime 版本: {cfg['market_regimes_version']}")
    lines.append("> regime = 触发时点的市场状态（btc_recovery 优先）。DXY/VIX 为合成数据，不使用。\n")

    for tname in triggers:
        sub = events[events["trigger"] == tname]
        if sub.empty:
            continue
        lines.append(f"\n## {tname}\n")
        lines.append("| regime | n | 24h均 | 24h胜率 | 168h均 | 168h胜率 |")
        lines.append("|---|---|---|---|---|---|")
        for reg, g in sub.groupby("regime", dropna=False):
            r24 = pd.to_numeric(g["ret_24h"], errors="coerce").dropna()
            r168 = pd.to_numeric(g["ret_168h"], errors="coerce").dropna() if "ret_168h" in g.columns else pd.Series(dtype=float)
            if r24.empty:
                lines.append(f"| {reg} | 0 | - | - | - | - |")
            else:
                lines.append(
                    f"| {reg} | {len(g)} | {r24.mean():.2f}% | {(r24 > 0).mean() * 100:.0f}% | "
                    f"{r168.mean():.2f}% | {(r168 > 0).mean() * 100:.0f}% |"
                )
    OUT_PATH.parent.mkdir(parents=True, exist_ok=True)
    OUT_PATH.write_text("\n".join(lines), encoding="utf-8")
    print(f"[106] wrote {OUT_PATH}")
    for tname in triggers:
        sub = events[events["trigger"] == tname]
        if sub.empty:
            continue
        print(f"\n=== {tname} (n={len(sub)}) ===")
        for reg, g in sub.groupby("regime"):
            r24 = pd.to_numeric(g["ret_24h"], errors="coerce").dropna()
            if not r24.empty:
                print(f"  {reg:14s} n={len(g):5d}  24h={r24.mean():+.2f}%")


if __name__ == "__main__":
    main()
