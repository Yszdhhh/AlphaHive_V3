r"""149_meme_washout.py — s008：meme 子池 washout 是否强于全池（情绪类 E-B）。

假设：meme 币（DOGE/1000PEPE/FARTCOIN 等）情绪驱动最强、杠杆散户结构最纯，
washout（砸坑）后的反弹（轧空/情绪修复）应强于普通山寨。

分组（universe 66 内）：
- meme 子池：DOGE/1000PEPE/FARTCOIN/1000BONK/PENGU/PUMP/WIF/TRUMP/VIRTUAL/WLFI/SPCX/ESPORTS
- 对照：全池 washout vs meme washout vs 非 meme washout

事件：washout = price_z<-2 或 ret_24h<-8%（720h rolling z，72h 冷却）——144 加密同口径。
基线：同期随机 symbol×时点横截面（bootstrap 95% CI，seed=2026）。
判定：CI 下界>0 → GO_LONG；n<30 → 样本不足。

输出：reports/meme_washout.md
用法：python scripts/149_meme_washout.py
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

REPORT = PROJECT_ROOT / "reports" / "meme_washout.md"
LO_MS = int(pd.Timestamp("2022-01-01", tz="UTC").timestamp() * 1000)
HI_MS = int(pd.Timestamp("2026-06-30", tz="UTC").timestamp() * 1000)
MIN_EVENTS = 30
N_BASELINE = 3000
SEED = 2026
WASH_Z = -2.0
WASH_RET = -8.0

MEME_POOL = {
    "DOGEUSDT", "1000PEPEUSDT", "FARTCOINUSDT", "1000BONKUSDT", "PENGUUSDT",
    "PUMPUSDT", "WIFUSDT", "TRUMPUSDT", "VIRTUALUSDT", "WLFIUSDT",
    "SPCXUSDT", "ESPORTSUSDT",
}


def detect_washout(sym: str, ctx: pd.DataFrame) -> pd.DataFrame:
    axis = ctx.index.to_numpy(dtype=np.int64)
    close = ctx["close"].to_numpy(dtype=float)
    s = pd.Series(close)
    z = (s - s.rolling(720, min_periods=360).mean()) / s.rolling(720, min_periods=360).std().replace(0, np.nan)
    ret24 = s.pct_change(24) * 100.0
    fired = np.isfinite(z.to_numpy()) & np.isfinite(ret24.to_numpy()) & \
        ((z.to_numpy() < WASH_Z) | (ret24.to_numpy() < WASH_RET))
    events: list[int] = []
    last = -10**18
    for i in np.flatnonzero(fired):
        t = int(axis[i])
        if t - last >= 72 * 3_600_000:
            events.append(t)
            last = t
    return pd.DataFrame({"symbol": sym, "timestamp": events}) if events else pd.DataFrame(
        columns=["symbol", "timestamp"])


def main() -> int:
    symbols = m113.load_universe_symbols()
    ctxs = m113.load_price_ctx(symbols)
    print(f"ctx {len(ctxs)} | meme 池命中 {len(set(symbols) & MEME_POOL)}")

    all_ev: list[pd.DataFrame] = []
    for sym, ctx in ctxs.items():
        ev = detect_washout(sym, ctx)
        if not ev.empty:
            all_ev.append(ev)
    events = pd.concat(all_ev, ignore_index=True) if all_ev else pd.DataFrame(
        columns=["symbol", "timestamp"])
    events = events[(events["timestamp"] >= LO_MS) & (events["timestamp"] <= HI_MS)].copy()
    # forward 收益
    fwd_parts = []
    for sym, g in events.groupby("symbol", sort=False):
        if sym in ctxs:
            fwd_parts.append(forward_stats(ctxs[sym], g.copy(), DEFAULT_HORIZONS))
    events = pd.concat(fwd_parts, ignore_index=True) if fwd_parts else events
    events["is_meme"] = events["symbol"].isin(MEME_POOL)
    print(f"washout 事件 {len(events)} | meme {int(events['is_meme'].sum())}")

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

    lines = ["# s008：meme 子池 washout 事件研究\n",
             f"- 生成：{datetime.now(timezone.utc):%Y-%m-%d %H:%M UTC}",
             f"- 事件：washout（price_z<-2 或 ret_24h<-8%，72h 冷却），2022-01→2026-06",
             f"- meme 池（{len(MEME_POOL)}）：{', '.join(sorted(MEME_POOL))}",
             "- 基线：同期随机 symbol×时点横截面（bootstrap 95% CI，seed=2026）\n",
             "| 组 | n | 24h 均值 | 24h 超额 | 24h CI | 168h 均值 | 168h 超额 | 168h CI | 168h 中位数 | 判定 |",
             "|---|---|---:|---:|---:|---:|---:|---:|---:|---|"]

    def row(label: str, g: pd.DataFrame) -> None:
        n = len(g)
        if n == 0:
            lines.append(f"| {label} | 0 | - | - | - | - | - | - | - | 无事件 |")
            return
        r24 = pd.to_numeric(g["ret_24h"], errors="coerce").dropna().to_numpy()
        r168 = pd.to_numeric(g["ret_168h"], errors="coerce").dropna().to_numpy()
        ci24 = bootstrap_ci(r24, br24, n_boot=1000, alpha=0.05, seed=SEED)
        ci168 = bootstrap_ci(r168, br168, n_boot=1000, alpha=0.05, seed=SEED + 1)
        verdict = ("样本不足" if n < MIN_EVENTS else
                   "GO_LONG" if ci168["ci_lo"] > 0 else
                   "GO_SHORT" if ci168["ci_hi"] < 0 else "NO_GO")
        lines.append(f"| {label} | {n} | {r24.mean():+.2f}% | {ci24['mean_diff']:+.2f}% "
                     f"| [{ci24['ci_lo']:+.2f}, {ci24['ci_hi']:+.2f}] | {r168.mean():+.2f}% "
                     f"| {ci168['mean_diff']:+.2f}% | [{ci168['ci_lo']:+.2f}, {ci168['ci_hi']:+.2f}] "
                     f"| {np.median(r168):+.2f}% | **{verdict}** |")
        print(f"[149] {label}: n={n} ex168={ci168['mean_diff']:+.2f}% med={np.median(r168):+.2f}% {verdict}")

    row("全池 washout", events)
    row("meme 子池", events[events["is_meme"]])
    row("非 meme 池", events[~events["is_meme"]])

    if events["is_meme"].any() and (~events["is_meme"]).any():
        m = events[events["is_meme"]]
        o = events[~events["is_meme"]]
        c = bootstrap_ci(pd.to_numeric(m["ret_168h"], errors="coerce").dropna().to_numpy(),
                         pd.to_numeric(o["ret_168h"], errors="coerce").dropna().to_numpy(),
                         n_boot=1000, alpha=0.05, seed=SEED + 2)
        lines.append("\n直接对照（168h）：meme − 非meme")
        lines.append(f"- 差 {c['mean_diff']:+.2f}% CI[{c['ci_lo']:+.2f}, {c['ci_hi']:+.2f}]"
                     f"（{'显著' if c['ci_lo'] > 0 else '不显著'}）")

    lines.extend(["\n## 解读\n",
                   "- meme 显著强于非 meme → 情绪类 edge 成立，meme 池值得单列（s008 升级候选）。",
                   "- meme 与全池无差 → meme 没有额外情绪溢价，s008 并入 s001 统一管理。",
                   "- meme 显著弱 → 情绪品种反弹更差（可能是反身性崩盘），认知入库。"])
    REPORT.parent.mkdir(parents=True, exist_ok=True)
    REPORT.write_text("\n".join(lines) + "\n", encoding="utf-8")
    print(f"wrote {REPORT}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
