r"""155_liquidity_stratification.py — 容量锚场景：wash_cvd × 事件时流动性分层。

假设（机构盲区 #1 容量锚）：wash_cvd 事件在低流动性币上更强——机构因滑点/容量
进不去，个人小资金可自由进出。用 24h 成交额（quote_volume rolling 24h）作流动性
代理（历史全可得，比市值序列更直接）。

事件：wash_cvd（115 口径，72h 冷却，2022-01→2026-06）。
分层：事件时点 24h 成交额三分位（事件样本内 q33/q67；无前视——阈值用事件样本
全局分位，等价于绝对流动性分档）。
基线：同期随机横截面；每层 24h/168h 超额 + 直接对照（低−高）。

输出：reports/liquidity_stratification.md
用法：python scripts/155_liquidity_stratification.py
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

REPORT = PROJECT_ROOT / "reports" / "liquidity_stratification.md"
LO_MS = int(pd.Timestamp("2022-01-01", tz="UTC").timestamp() * 1000)
HI_MS = int(pd.Timestamp("2026-06-30", tz="UTC").timestamp() * 1000)
MIN_EVENTS = 30
N_BASELINE = 3000
SEED = 2026


def add_liq24(ctxs: dict[str, pd.DataFrame]) -> dict[str, pd.DataFrame]:
    """每 ctx 补 liq24_usd = rolling(24).sum(quote_volume)（事件时点 asof 用）。"""
    for sym, t in ctxs.items():
        p = m113.COINGLASS_RAW1H / "klines" / f"{sym}.parquet"
        if not p.exists():
            t["liq24_usd"] = np.nan
            continue
        df = pd.read_parquet(p, columns=["open_time", "quote_volume"])
        ts = pd.to_numeric(df["open_time"], errors="coerce").to_numpy(dtype=np.int64)
        qv = pd.to_numeric(df["quote_volume"], errors="coerce").to_numpy(dtype=float)
        qs = pd.Series(qv, index=pd.Index(ts))
        qs = qs[~qs.index.duplicated(keep="last")].sort_index()
        t["liq24_usd"] = qs.reindex(t.index).rolling(24).sum().to_numpy()
    return ctxs


def main() -> int:
    symbols = m113.load_universe_symbols()
    ctxs = m113.load_price_ctx(symbols)
    ctxs = add_liq24(ctxs)
    fundings = m113.load_funding_series(symbols)
    print(f"ctx {len(ctxs)}")

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

    # 事件时点 liq24 asof
    liq_at = []
    for sym, g in events.groupby("symbol", sort=False):
        if sym not in ctxs:
            liq_at.append(pd.Series(np.nan, index=g.index))
            continue
        t = ctxs[sym]
        idx = t.index.to_numpy(dtype=np.int64)
        vals = pd.to_numeric(t["liq24_usd"], errors="coerce").to_numpy(dtype=float)
        pos = np.searchsorted(idx, g["timestamp"].to_numpy(dtype=np.int64), side="right") - 1
        pos = np.clip(pos, 0, len(idx) - 1)
        liq_at.append(pd.Series(vals[pos], index=g.index))
    events["liq24_usd"] = pd.concat(liq_at).sort_index()
    usable = events[events["liq24_usd"].notna()].copy()
    print(f"wash_cvd {len(events)} | 有流动性 {len(usable)}")

    q33, q67 = usable["liq24_usd"].quantile([0.33, 0.67])
    print(f"流动性分位: q33=${q33 / 1e6:.0f}M q67=${q67 / 1e6:.0f}M")
    lo = usable[usable["liq24_usd"] < q33]
    mid = usable[(usable["liq24_usd"] >= q33) & (usable["liq24_usd"] < q67)]
    hi = usable[usable["liq24_usd"] >= q67]

    rng = np.random.default_rng(SEED)
    base = draw_random_events(ctxs, N_BASELINE, rng, max_forward_hours=168,
                              start_ms=LO_MS, end_ms=HI_MS)
    bparts = []
    for bs, bg in base.groupby("symbol", sort=False):
        if bs in ctxs:
            bparts.append(forward_stats(ctxs[bs], bg.copy(), DEFAULT_HORIZONS))
    base_df = pd.concat(bparts, ignore_index=True) if bparts else pd.DataFrame()
    br24 = pd.to_numeric(base_df["ret_24h"], errors="coerce").dropna().to_numpy()
    br168 = pd.to_numeric(base_df["ret_168h"], errors="coerce").dropna().to_numpy()

    lines = ["# 容量锚：wash_cvd × 事件时流动性分层（155）\n",
             f"- 生成：{datetime.now(timezone.utc):%Y-%m-%d %H:%M UTC}",
             f"- 假设：低流动性币（机构容量盲区）wash_cvd 反弹更强",
             f"- 代理：事件时点 24h 成交额；分位 q33=${q33 / 1e6:.0f}M / q67=${q67 / 1e6:.0f}M",
             "- 基线：随机横截面；判定：CI 下界>0 → GO_LONG\n",
             "| 层 | n | 24h 均值 | 24h 超额 | 168h 均值 | 168h 超额 | 168h CI | 168h 中位数 | 判定 |",
             "|---|---|---:|---:|---:|---:|---:|---:|---|"]

    def row(label: str, g: pd.DataFrame) -> None:
        n = len(g)
        if n == 0:
            lines.append(f"| {label} | 0 | - | - | - | - | - | - | 无事件 |")
            return
        r24 = pd.to_numeric(g["ret_24h"], errors="coerce").dropna().to_numpy()
        r168 = pd.to_numeric(g["ret_168h"], errors="coerce").dropna().to_numpy()
        ci24 = bootstrap_ci(r24, br24, n_boot=1000, alpha=0.05, seed=SEED)
        ci168 = bootstrap_ci(r168, br168, n_boot=1000, alpha=0.05, seed=SEED + 1)
        verdict = ("样本不足" if n < MIN_EVENTS else
                   "GO_LONG" if ci168["ci_lo"] > 0 else
                   "GO_SHORT" if ci168["ci_hi"] < 0 else "NO_GO")
        lines.append(f"| {label} | {n} | {r24.mean():+.2f}% | {ci24['mean_diff']:+.2f}% "
                     f"| {r168.mean():+.2f}% | {ci168['mean_diff']:+.2f}% "
                     f"| [{ci168['ci_lo']:+.2f}, {ci168['ci_hi']:+.2f}] | {np.median(r168):+.2f}% | **{verdict}** |")
        print(f"[155] {label}: n={n} ex168={ci168['mean_diff']:+.2f}% med={np.median(r168):+.2f}% {verdict}")

    row("低流动性（<$33M）", lo)
    row("中流动性", mid)
    row("高流动性（>$67M）", hi)

    c = bootstrap_ci(pd.to_numeric(lo["ret_168h"], errors="coerce").dropna().to_numpy(),
                     pd.to_numeric(hi["ret_168h"], errors="coerce").dropna().to_numpy(),
                     n_boot=1000, alpha=0.05, seed=SEED + 2)
    lines.append(f"\n直接对照（168h）：低 − 高 = {c['mean_diff']:+.2f}% "
                 f"CI[{c['ci_lo']:+.2f}, {c['ci_hi']:+.2f}]"
                 f"（{'显著' if c['ci_lo'] > 0 else '不显著'}）")

    lines.extend(["\n## 解读\n",
                   "- 低流动性层显著更强 → 容量锚成立：小资金专属 edge（s010 候选）。",
                   "- 无差异 → 流动性不是 wash_cvd 的调制维度（edge 全池均匀）。",
                   "- 注意：低流动性层执行滑点更高，需成本敏感性复核（毛利 − 实际滑点）。"])
    REPORT.parent.mkdir(parents=True, exist_ok=True)
    REPORT.write_text("\n".join(lines) + "\n", encoding="utf-8")
    print(f"wrote {REPORT}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
