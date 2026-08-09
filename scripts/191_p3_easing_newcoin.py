r"""191_p3_easing_newcoin.py — P3：降息期 × 新币交互。

184 发现：降息期（EASING）wash_cvd 弱（+1.16% NO_GO vs 非降息 +1.61%）。
166 发现：新币池与成熟池周期行为相反（新币熊市强）。
本脚本：新币 washout×4h 确认（s009 口径）按 EASING 分层——新币是否独立于宏观降息。

输出：reports/p3_easing_newcoin.md
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

REPORT = PROJECT_ROOT / "reports" / "p3_easing_newcoin.md"
MACRO = Path(r"C:\Users\10639\Desktop\🔒 加密资产\coinglass_db\macro")
LO_MS = int(pd.Timestamp("2022-01-01", tz="UTC").timestamp() * 1000)
HI_MS = int(pd.Timestamp("2026-06-30", tz="UTC").timestamp() * 1000)
NEW_DAYS = 90
MIN_EVENTS = 20
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


def main() -> int:
    ctxs = m113.load_price_ctx(m113.load_universe_symbols())
    listed = listing_dates()
    # EASING 状态（184 口径）
    p = MACRO / "FEDFUNDS.parquet"
    d = pd.read_parquet(p)
    idx = pd.to_datetime(d.index) if not isinstance(d.index, pd.DatetimeIndex) else d.index
    fed = pd.Series(pd.to_numeric(d["close"], errors="coerce").to_numpy(), index=idx).dropna()
    fed = fed.resample("D").last().ffill()
    easing = (fed.diff(90) <= -0.25)

    # 新币 washout×确认 事件（157 口径）
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
    ev["EASING"] = easing.reindex(ev_day).to_numpy(dtype=float)
    usable = ev[ev["EASING"].notna()].copy()
    print(f"新币×确认 {len(ev)} | 有 EASING {len(usable)} | 降息期占比 {usable['EASING'].mean():.0%}")

    rng = np.random.default_rng(SEED)
    base = draw_random_events(ctxs, N_BASELINE, rng, max_forward_hours=168,
                              start_ms=LO_MS, end_ms=HI_MS)
    bparts = []
    for bs, bg in base.groupby("symbol", sort=False):
        if bs in ctxs:
            bparts.append(forward_stats(ctxs[bs], bg.copy(), DEFAULT_HORIZONS))
    base_df = pd.concat(bparts, ignore_index=True) if bparts else pd.DataFrame()
    br168 = pd.to_numeric(base_df["ret_168h"], errors="coerce").dropna().to_numpy()

    lines = ["# P3：降息期 × 新币交互（191）\n",
             f"- 生成：{datetime.now(timezone.utc):%Y-%m-%d %H:%M UTC}",
             f"- 事件：新币 washout×4h 确认（s009 口径，{len(usable)}）；EASING=FEDFUNDS 90d 降≥25bp\n",
             "| 组 | n | 168h 超额 | CI | 中位数 | 判定 |",
             "|---|---|---:|---:|---:|---|"]

    def row(label: str, g: pd.DataFrame) -> None:
        n = len(g)
        if n < MIN_EVENTS:
            lines.append(f"| {label} | {n} | - | - | - | 样本不足 |")
            print(f"[191] {label}: n={n} 样本不足")
            return
        r = g["r168"].to_numpy(dtype=float)
        ci = bootstrap_ci(r, br168, n_boot=1000, alpha=0.05, seed=SEED)
        verdict = ("样本不足" if n < MIN_EVENTS else
                   "GO_LONG" if ci["ci_lo"] > 0 else
                   "GO_SHORT" if ci["ci_hi"] < 0 else "NO_GO")
        lines.append(f"| {label} | {n} | {ci['mean_diff']:+.2f}% "
                     f"| [{ci['ci_lo']:+.2f}, {ci['ci_hi']:+.2f}] | {np.median(r):+.2f}% | **{verdict}** |")
        print(f"[191] {label}: n={n} ex168={ci['mean_diff']:+.2f}% med={np.median(r):+.2f}% {verdict}")

    row("新币×确认 全（s009 对照）", usable)
    row("  降息期（EASING=1）", usable[usable["EASING"] == 1])
    row("  非降息期（EASING=0）", usable[usable["EASING"] == 0])

    lines.extend(["\n## 解读\n",
                  "- 新币在降息期显著强/弱 → 新币受宏观周期调制（与成熟池 184 对比）。",
                  "- 无差异 → 新币独立于降息周期（时间锚效应主导）。"])
    REPORT.parent.mkdir(parents=True, exist_ok=True)
    REPORT.write_text("\n".join(lines) + "\n", encoding="utf-8")
    print(f"wrote {REPORT}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
