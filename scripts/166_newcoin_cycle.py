r"""166_newcoin_cycle.py — 新币 washout×确认 × BTC 周期交互（164 的自然延伸）。

164 发现：wash_cvd（成熟池）在 Mayer>1.5（牛市插针）最强、Mayer<0.8（深熊）最弱。
本脚本测【新币池】（s009 口径：washout+上市<90天+4h 确认）是否同样受周期调制，
还是新币情绪独立于 BTC 周期。

分层：事件时点 Mayer <0.8（熊市）/ 0.8-1.5（中部）/ >1.5（牛市插针）。
对照：s009 全样本（157 的 +5.82%）。
判定：门槛 G；牛市组显著强于熊市组 → 周期调制一致（s009 加周期条件）；
无差异 → 新币情绪独立（周期不适用新币池）。

输出：reports/newcoin_cycle.md
用法：python scripts/166_newcoin_cycle.py
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

REPORT = PROJECT_ROOT / "reports" / "newcoin_cycle.md"
LO_MS = int(pd.Timestamp("2022-01-01", tz="UTC").timestamp() * 1000)
HI_MS = int(pd.Timestamp("2026-06-30", tz="UTC").timestamp() * 1000)
NEW_DAYS = 90
MIN_EVENTS = 30
N_BASELINE = 3000
SEED = 2026


def listing_dates() -> dict[str, int]:
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


def btc_cycle() -> pd.DataFrame:
    p = m113.COINGLASS_RAW1H / "klines" / "BTCUSDT.parquet"
    df = pd.read_parquet(p, columns=["open_time", "close"])
    df = df.drop_duplicates(subset="open_time").sort_values("open_time")
    df["ts"] = pd.to_numeric(df["open_time"], errors="coerce").astype(np.int64)
    df["close"] = pd.to_numeric(df["close"], errors="coerce").astype(float)
    df["day"] = pd.to_datetime(df["ts"], unit="ms", utc=True).dt.tz_localize(None).dt.normalize()
    daily = df.groupby("day")["close"].last().dropna()
    ma200 = daily.rolling(200, min_periods=120).mean()
    return (daily / ma200.replace(0, np.nan)).dropna()


def main() -> int:
    cycle = btc_cycle()
    ctxs = m113.load_price_ctx(m113.load_universe_symbols())
    listed = listing_dates()

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
                events.append(i)
                last = t
        for i in events:
            t = int(axis[i])
            if (t - listed[sym]) >= NEW_DAYS * 24 * 3_600_000:
                continue
            if i + 168 >= len(close):
                continue
            r4 = (close[i + 4] / close[i] - 1) * 100.0
            r168 = (close[i + 168] / close[i] - 1) * 100.0
            if np.isfinite(r4) and np.isfinite(r168) and r4 > 0:
                ev_parts.append({"symbol": sym, "t": t, "r168": r168})
    ev = pd.DataFrame(ev_parts)
    ev = ev[(ev["t"] >= LO_MS) & (ev["t"] <= HI_MS)]
    ev_day = pd.to_datetime(ev["t"].to_numpy(), unit="ms", utc=True).tz_localize(None).normalize()
    ev["mayer"] = ev_day.map(cycle).to_numpy()
    usable = ev[ev["mayer"].notna()].copy()
    print(f"新币×确认 {len(ev)} | 有周期 {len(usable)}")

    rng = np.random.default_rng(SEED)
    base = draw_random_events(ctxs, N_BASELINE, rng, max_forward_hours=168,
                              start_ms=LO_MS, end_ms=HI_MS)
    bparts = []
    for bs, bg in base.groupby("symbol", sort=False):
        if bs in ctxs:
            bparts.append(forward_stats(ctxs[bs], bg.copy(), DEFAULT_HORIZONS))
    base_df = pd.concat(bparts, ignore_index=True) if bparts else pd.DataFrame()
    br168 = pd.to_numeric(base_df["ret_168h"], errors="coerce").dropna().to_numpy()

    lines = ["# 新币 washout×确认 × BTC 周期交互（166）\n",
             f"- 生成：{datetime.now(timezone.utc):%Y-%m-%d %H:%M UTC}",
             "- 事件：washout + 上市<90天 + 4h 确认（157 口径）",
             "- 分层：事件时点 Mayer（价格/200日线）<0.8 熊市 / 0.8-1.5 中部 / >1.5 牛市插针",
             "- 检验：新币池是否同受周期调制（对照 164 成熟池：牛市强、熊市弱）\n",
             "| 周期层 | n | 168h 均值 | 168h 超额 | CI | 中位数 | 尾切 | 判定 |",
             "|---|---|---:|---:|---:|---:|---:|---|"]

    def row(label: str, g: pd.DataFrame) -> None:
        n = len(g)
        if n == 0:
            lines.append(f"| {label} | 0 | - | - | - | - | - | 无事件 |")
            return
        r = g["r168"].to_numpy(dtype=float)
        ci = bootstrap_ci(r, br168, n_boot=1000, alpha=0.05, seed=SEED)
        thr = np.quantile(r, 0.95)
        tail = r[r <= thr].mean()
        verdict = ("样本不足" if n < MIN_EVENTS else
                   "GO_LONG" if ci["ci_lo"] > 0 else
                   "GO_SHORT" if ci["ci_hi"] < 0 else "NO_GO")
        lines.append(f"| {label} | {n} | {r.mean():+.2f}% | {ci['mean_diff']:+.2f}% "
                     f"| [{ci['ci_lo']:+.2f}, {ci['ci_hi']:+.2f}] | {np.median(r):+.2f}% "
                     f"| {tail:+.2f}% | **{verdict}** |")
        print(f"[166] {label}: n={n} ex168={ci['mean_diff']:+.2f}% med={np.median(r):+.2f}% {verdict}")

    row("新币×确认 全部（157 对照）", usable)
    row("熊市（Mayer<0.8）", usable[usable["mayer"] < 0.8])
    row("中部（0.8-1.5）", usable[(usable["mayer"] >= 0.8) & (usable["mayer"] <= 1.5)])
    row("牛市插针（Mayer>1.5）", usable[usable["mayer"] > 1.5])

    lines.extend(["\n## 解读\n",
                   "- 与成熟池同向（牛市强熊市弱）→ 周期调制普适，s009 可加周期条件。",
                   "- 无差异 → 新币情绪独立于 BTC 周期（新币池自带时间锚，周期不适用）。",
                   "- 注意：新币事件集中在 2024-2026（2022-23 新币少），熊市组可能 n 不足。"])
    REPORT.parent.mkdir(parents=True, exist_ok=True)
    REPORT.write_text("\n".join(lines) + "\n", encoding="utf-8")
    print(f"wrote {REPORT}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
