r"""168_newcoin_cycle_review.py — 166 稳健性验证：新币熊市增强是否可靠。

166 发现：新币 washout×4h确认 在 Mayer<0.8（熊市）+7.40% 中位数 +4.90%（n=35）。
本脚本六项验证：
1. 独立窗口：熊市事件按 2022-23 / 2024-26 切，两段同号？
2. 尾部切除：去 top5% 后均值/中位数
3. 阈值敏感性：Mayer <0.7 / <0.8 / <0.9
4. 确认依赖：熊市新币 washout 无确认组（4h 确认是否熊市必要）
5. 集中度：熊市事件按 symbol/月份分布（单币/单月主导？）
6. 成本敏感性：1×/2×/3× 成本净期望

输出：reports/newcoin_cycle_review.md
用法：python scripts/168_newcoin_cycle_review.py
"""
from __future__ import annotations

import importlib.util
import sys
from collections import Counter
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

REPORT = PROJECT_ROOT / "reports" / "newcoin_cycle_review.md"
LO_MS = int(pd.Timestamp("2022-01-01", tz="UTC").timestamp() * 1000)
HI_MS = int(pd.Timestamp("2026-06-30", tz="UTC").timestamp() * 1000)
NEW_DAYS = 90
MIN_EVENTS = 20
N_BASELINE = 3000
SEED = 2026
COST = 54.0 / 10000.0  # 54bps round-trip


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


def btc_mayer() -> pd.Series:
    p = m113.COINGLASS_RAW1H / "klines" / "BTCUSDT.parquet"
    df = pd.read_parquet(p, columns=["open_time", "close"])
    df = df.drop_duplicates(subset="open_time").sort_values("open_time")
    df["ts"] = pd.to_numeric(df["open_time"], errors="coerce").astype(np.int64)
    df["close"] = pd.to_numeric(df["close"], errors="coerce").astype(float)
    df["day"] = pd.to_datetime(df["ts"], unit="ms", utc=True).dt.tz_localize(None).dt.normalize()
    daily = df.groupby("day")["close"].last().dropna()
    ma200 = daily.rolling(200, min_periods=120).mean()
    return (daily / ma200.replace(0, np.nan)).dropna()


def collect(require_confirm: bool) -> pd.DataFrame:
    ctxs = m113.load_price_ctx(m113.load_universe_symbols())
    listed = listing_dates()
    rows = []
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
            if not (np.isfinite(r4) and np.isfinite(r168)):
                continue
            if require_confirm and r4 <= 0:
                continue
            rows.append({"symbol": sym, "t": t, "r168": r168, "r4": r4})
    ev = pd.DataFrame(rows)
    ev = ev[(ev["t"] >= LO_MS) & (ev["t"] <= HI_MS)]
    ev_day = pd.to_datetime(ev["t"].to_numpy(), unit="ms", utc=True).tz_localize(None).normalize()
    ev["mayer"] = ev_day.map(btc_mayer()).to_numpy()
    return ev.dropna(subset=["mayer"])


def main() -> int:
    ev = collect(require_confirm=True)
    ev_nc = collect(require_confirm=False)
    print(f"新币×确认 {len(ev)} | 新币无确认 {len(ev_nc)}")

    rng = np.random.default_rng(SEED)
    ctxs = m113.load_price_ctx(m113.load_universe_symbols())
    base = draw_random_events(ctxs, N_BASELINE, rng, max_forward_hours=168,
                              start_ms=LO_MS, end_ms=HI_MS)
    bparts = []
    for bs, bg in base.groupby("symbol", sort=False):
        if bs in ctxs:
            bparts.append(forward_stats(ctxs[bs], bg.copy(), DEFAULT_HORIZONS))
    base_df = pd.concat(bparts, ignore_index=True) if bparts else pd.DataFrame()
    br168 = pd.to_numeric(base_df["ret_168h"], errors="coerce").dropna().to_numpy()

    lines = ["# 166 稳健性验证：新币熊市增强（168）\n",
             f"- 生成：{datetime.now(timezone.utc):%Y-%m-%d %H:%M UTC}",
             "- 六项：独立窗口 / 尾切 / Mayer 阈值敏感性 / 确认依赖 / 集中度 / 成本敏感性\n",
             "## 1. 独立窗口 + 尾切（熊市 Mayer<0.8，确认组）\n",
             "| 组 | n | 168h 均值 | 超额 | CI | 中位数 | 尾切后均值 | 判定 |",
             "|---|---|---:|---:|---:|---:|---:|---|"]

    def row(label: str, g: pd.DataFrame) -> None:
        n = len(g)
        if n < MIN_EVENTS:
            lines.append(f"| {label} | {n} | - | - | - | - | - | 样本不足 |")
            print(f"[168] {label}: n={n} 样本不足")
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
        print(f"[168] {label}: n={n} ex168={ci['mean_diff']:+.2f}% med={np.median(r):+.2f}% tail={tail:+.2f}% {verdict}")

    bear = ev[ev["mayer"] < 0.8]
    split = int(pd.Timestamp("2024-01-01", tz="UTC").timestamp() * 1000)
    row("熊市 全部（166 对照）", bear)
    row("  熊市 2022-23", bear[bear["t"] < split])
    row("  熊市 2024-26", bear[bear["t"] >= split])

    # 集中度
    sym_top = Counter(bear["symbol"]).most_common(5)
    mon = pd.to_datetime(bear["t"].to_numpy(), unit="ms", utc=True).strftime("%Y-%m")
    mon_top = Counter(mon).most_common(5)
    lines.append("\n## 2. 集中度检查（熊市 35 事件）\n")
    lines.append(f"- 最多 symbol：{sym_top}")
    lines.append(f"- 最多月份：{mon_top}")
    print(f"[168] 集中度: sym={sym_top} mon={mon_top}")

    # 阈值敏感性
    lines.append("\n## 3. Mayer 阈值敏感性（确认组）\n")
    for thr_m in [0.7, 0.8, 0.9]:
        g = ev[ev["mayer"] < thr_m]
        n = len(g)
        if n >= MIN_EVENTS:
            r = g["r168"].to_numpy(dtype=float)
            ci = bootstrap_ci(r, br168, n_boot=1000, alpha=0.05, seed=SEED)
            lines.append(f"| Mayer<{thr_m} | {n} | {r.mean():+.2f}% | {ci['mean_diff']:+.2f}% "
                         f"| [{ci['ci_lo']:+.2f}, {ci['ci_hi']:+.2f}] | {np.median(r):+.2f}% | |")
            print(f"[168] Mayer<{thr_m}: n={n} ex168={ci['mean_diff']:+.2f}% med={np.median(r):+.2f}%")
        else:
            lines.append(f"| Mayer<{thr_m} | {n} | - | - | - | - | 样本不足 |")

    # 确认依赖
    lines.append("\n## 4. 确认依赖（熊市，确认 vs 无确认）\n")
    row("熊市 新币×确认", bear)
    bear_nc = ev_nc[ev_nc["mayer"] < 0.8]
    row("熊市 新币×无确认", bear_nc)

    # 成本敏感性
    r = bear["r168"].to_numpy(dtype=float)
    lines.append("\n## 5. 成本敏感性（熊市×确认）\n")
    for k in [1, 2, 3]:
        net = r.mean() / 100.0 - COST * k
        lines.append(f"- {k}× 成本（{COST * k * 100:.0f}bps）：净 {net * 100:+.2f}%"
                     f"（{'✓' if net > 0 else '✗'}）")

    lines.extend(["\n## 裁决\n",
                   "- 独立窗口两段同号 + 尾切仍正 + 阈值单调 + 确认必要 → 166 稳健（s009 周期条件升级）。",
                   "- 任一失败 → 熊市增强不稳健，s009 保持全事件。"])
    REPORT.parent.mkdir(parents=True, exist_ok=True)
    REPORT.write_text("\n".join(lines) + "\n", encoding="utf-8")
    print(f"wrote {REPORT}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
