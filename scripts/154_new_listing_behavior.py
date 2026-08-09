r"""154_new_listing_behavior.py — 新上市资产行为（场景路线：时间锚）。

假设（机构盲区 #2 时间锚）：新上市币（<90 天）washout 事件的情绪结构更纯、
机构覆盖少、做市商未充分进入 → 砸坑后反弹应强于成熟期；且上市初期波动率更高。

数据：coinglass klines 起始时间 ≈ 上市日（universe 66，含 2024-2025 新币：
FARTCOIN/TRUMP/WLFI/GRASS/PUMP/PENGU 等）。
分层：事件时点距上市 <90 天（新币期）/ ≥90 天（成熟期）。
事件：washout（price_z<-2 或 ret_24h<-8%，72h 冷却）——149 同口径。
基线：同期随机横截面；每层各自 24h/168h 超额。

输出：reports/new_listing_behavior.md
用法：python scripts/154_new_listing_behavior.py
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

REPORT = PROJECT_ROOT / "reports" / "new_listing_behavior.md"
LO_MS = int(pd.Timestamp("2022-01-01", tz="UTC").timestamp() * 1000)
HI_MS = int(pd.Timestamp("2026-06-30", tz="UTC").timestamp() * 1000)
NEW_DAYS = 90          # 新币期 = 上市后 90 天内
MIN_EVENTS = 30
N_BASELINE = 3000
SEED = 2026


def listing_dates() -> dict[str, int]:
    """klines 首条 open_time = 上市日（毫秒）。"""
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
    symbols = m113.load_universe_symbols()
    ctxs = m113.load_price_ctx(symbols)
    listed = listing_dates()
    print(f"ctx {len(ctxs)} | 上市日已知 {len(listed)}")

    # 上市日分布
    new_coins = sorted((s for s, d in listed.items()
                        if d >= int(pd.Timestamp("2024-01-01", tz="UTC").timestamp() * 1000)),
                       key=lambda s: listed[s])
    print("2024+ 上市:", ", ".join(f"{s}({pd.Timestamp(listed[s], unit='ms', tz='UTC'):%y-%m})"
                                   for s in new_coins))

    lines = ["# 新上市资产行为：washout × 上市年龄分层（154，时间锚场景）\n",
             f"- 生成：{datetime.now(timezone.utc):%Y-%m-%d %H:%M UTC}",
             f"- 假设：新币期（<{NEW_DAYS} 天）washout 反弹强于成熟期（机构覆盖少/做市未充分/情绪纯）",
             f"- 上市日 = coinglass klines 首条时间；2024+ 新币 {len(new_coins)} 个：",
             "  " + ", ".join(f"{s}({pd.Timestamp(listed[s], unit='ms', tz='UTC'):%Y-%m})" for s in new_coins),
             "- 事件：washout（price_z<-2 或 ret_24h<-8%，72h 冷却）；基线：随机横截面\n",
             "| 上市年龄 | n | 24h 均值 | 24h 超额 | CI | 168h 均值 | 168h 超额 | 168h 中位数 | 判定 |",
             "|---|---|---:|---:|---:|---:|---:|---:|---|"]

    # 收集 washout 事件 + 上市年龄
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
    fwd_parts = []
    for sym, g in events.groupby("symbol", sort=False):
        if sym in ctxs:
            fwd_parts.append(forward_stats(ctxs[sym], g.copy(), DEFAULT_HORIZONS))
    events = pd.concat(fwd_parts, ignore_index=True) if fwd_parts else events
    print(f"washout 事件 {len(events)}（新币期 {int((events['age_days'] < NEW_DAYS).sum())}）")

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
                     f"| [{ci24['ci_lo']:+.2f}, {ci24['ci_hi']:+.2f}] | {r168.mean():+.2f}% "
                     f"| {ci168['mean_diff']:+.2f}% | {np.median(r168):+.2f}% | **{verdict}** |")
        print(f"[154] {label}: n={n} ex168={ci168['mean_diff']:+.2f}% med={np.median(r168):+.2f}% {verdict}")

    row(f"新币期（<{NEW_DAYS} 天）", events[events["age_days"] < NEW_DAYS])
    row(f"成熟期（≥{NEW_DAYS} 天）", events[events["age_days"] >= NEW_DAYS])

    # 直接对照
    a = events[events["age_days"] < NEW_DAYS]
    b = events[events["age_days"] >= NEW_DAYS]
    if len(a) >= 10 and len(b) >= 10:
        c = bootstrap_ci(pd.to_numeric(a["ret_168h"], errors="coerce").dropna().to_numpy(),
                         pd.to_numeric(b["ret_168h"], errors="coerce").dropna().to_numpy(),
                         n_boot=1000, alpha=0.05, seed=SEED + 2)
        lines.append(f"\n直接对照（168h）：新币期 − 成熟期 = {c['mean_diff']:+.2f}% "
                     f"CI[{c['ci_lo']:+.2f}, {c['ci_hi']:+.2f}]"
                     f"（{'显著' if c['ci_lo'] > 0 else '不显著'}）")

    lines.extend(["\n## 解读\n",
                   "- 新币期显著更强 → 时间锚场景成立：新上市资产有独立于成熟池的 edge（s009 候选）。",
                   "- 无差异/更弱 → 上市年龄不是调制维度；新币的 washout 已包含在成熟池行为内。",
                   "- 注意：新币期样本天然少（<90 天 × 每币），n 小则样本不足不判。"])
    REPORT.parent.mkdir(parents=True, exist_ok=True)
    REPORT.write_text("\n".join(lines) + "\n", encoding="utf-8")
    print(f"wrote {REPORT}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
