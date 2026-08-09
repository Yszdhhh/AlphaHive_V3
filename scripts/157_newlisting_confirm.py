r"""157_newlisting_confirm.py — 组合场景：新币期 × 4h 确认（时间锚 + 执行锚交乘）。

154 发现新币期（<90 天）washout 方向正（+2.11%）但尾部驱动（去 top5% 转负）；
148 发现 4h 反弹确认能把 wash_cvd 的尾部砍掉（中位数转正）。本脚本测两者交乘：
新币期 washout ∩ 4h 确认——时间锚的尾部是否被执行锚修复，组合是否可交易。

分组（washout 事件，149 口径）：
- 新币期全部 / 新币期×4h确认 / 新币期×无确认
- 对照：成熟期×4h确认
- 主线：新币期×确认 vs 新币期全体的 168h 期望 + 尾部结构

输出：reports/newlisting_confirm.md
用法：python scripts/157_newlisting_confirm.py
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

REPORT = PROJECT_ROOT / "reports" / "newlisting_confirm.md"
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


def main() -> int:
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
                events.append(t)
                last = t
        if events:
            ev_parts.append(pd.DataFrame({"symbol": sym, "timestamp": events}))
    events = pd.concat(ev_parts, ignore_index=True) if ev_parts else pd.DataFrame(
        columns=["symbol", "timestamp"])
    events = events[(events["timestamp"] >= LO_MS) & (events["timestamp"] <= HI_MS)].copy()
    events["listing_ms"] = events["symbol"].map(listed)
    events["age_days"] = (events["timestamp"] - events["listing_ms"]) / (24 * 3_600_000)

    # 4h 确认 + forward
    fwd = []
    for sym, g in events.groupby("symbol", sort=False):
        ctx = ctxs[sym]
        axis = ctx.index.to_numpy(dtype=np.int64)
        close = ctx["close"].to_numpy(dtype=float)
        rows = []
        for _, ev_row in g.iterrows():
            t = int(ev_row["timestamp"])
            pos = int(np.searchsorted(axis, t, side="right")) - 1
            if pos < 0 or pos + 168 >= len(close):
                continue
            r4 = (close[pos + 4] / close[pos] - 1) * 100.0
            r24 = (close[pos + 24] / close[pos] - 1) * 100.0
            r168 = (close[pos + 168] / close[pos] - 1) * 100.0
            if np.isfinite(r4) and np.isfinite(r24) and np.isfinite(r168):
                rows.append({"symbol": sym, "t": t, "age_days": ev_row["age_days"],
                             "r4": r4, "r24": r24, "r168": r168})
        if rows:
            fwd.append(pd.DataFrame(rows))
    ev = pd.concat(fwd, ignore_index=True) if fwd else pd.DataFrame()
    ev["is_new"] = ev["age_days"] < NEW_DAYS
    ev["confirm"] = ev["r4"] > 0
    print(f"washout 事件 {len(ev)} | 新币期 {int(ev['is_new'].sum())} | 确认 {int(ev['confirm'].sum())}")

    rng = np.random.default_rng(SEED)
    base = draw_random_events(ctxs, N_BASELINE, rng, max_forward_hours=168,
                              start_ms=LO_MS, end_ms=HI_MS)
    bparts = []
    for bs, bg in base.groupby("symbol", sort=False):
        if bs in ctxs:
            bparts.append(forward_stats(ctxs[bs], bg.copy(), DEFAULT_HORIZONS))
    base_df = pd.concat(bparts, ignore_index=True) if bparts else pd.DataFrame()
    br168 = pd.to_numeric(base_df["ret_168h"], errors="coerce").dropna().to_numpy()

    lines = ["# 组合场景：新币期 × 4h 确认（157，时间锚+执行锚）\n",
             f"- 生成：{datetime.now(timezone.utc):%Y-%m-%d %H:%M UTC}",
             f"- 事件：washout（{len(ev)}）；新币期 = 上市 <{NEW_DAYS} 天；确认 = 事件后 4h 反弹",
             "- 基线：随机横截面；168h 超额 + 中位数 + 尾部切除（去 top5%）\n",
             "| 组 | n | 168h 均值 | 168h 超额 | CI | 中位数 | 尾切后均值 | 判定 |",
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
        print(f"[157] {label}: n={n} ex168={ci['mean_diff']:+.2f}% med={np.median(r):+.2f}% tail={tail:+.2f}%")

    row("新币期 全部", ev[ev["is_new"]])
    row("**新币期 × 4h确认**", ev[ev["is_new"] & ev["confirm"]])
    row("新币期 × 无确认", ev[ev["is_new"] & ~ev["confirm"]])
    row("成熟期 × 4h确认（对照）", ev[~ev["is_new"] & ev["confirm"]])

    # 直接对照
    a = ev[ev["is_new"] & ev["confirm"]]
    b = ev[ev["is_new"] & ~ev["confirm"]]
    if len(a) >= 10 and len(b) >= 10:
        c = bootstrap_ci(a["r168"].to_numpy(), b["r168"].to_numpy(),
                         n_boot=1000, alpha=0.05, seed=SEED + 1)
        lines.append(f"\n直接对照：新币×确认 − 新币×无确认 = {c['mean_diff']:+.2f}% "
                     f"CI[{c['ci_lo']:+.2f}, {c['ci_hi']:+.2f}]")

    lines.extend(["\n## 解读\n",
                   "- 新币×确认中位数/尾切转正且 CI 显著 → 时间锚+执行锚组合可交易（s009 升级候选）。",
                   "- 确认无法修复新币尾部（尾切仍负）→ 新币尾部是本质属性（暴涨/归零），组合不成立。",
                   "- 对照成熟期×确认 → 组合增益是新币特有还是普适。"])
    REPORT.parent.mkdir(parents=True, exist_ok=True)
    REPORT.write_text("\n".join(lines) + "\n", encoding="utf-8")
    print(f"wrote {REPORT}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
