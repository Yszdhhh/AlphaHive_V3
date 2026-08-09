r"""160_s009_s010_stack.py — 叠加检验：新币期 × 低流动性 × 4h 确认（gpt C 方向 + TaskNewPool 建议）。

交叉验证来源：gpt 方案 C（性价比第一）+ TaskNewPool 发现（7 月亏损由 pump 类
股票代币尾部驱动，建议过滤）。本脚本回答：
1. 新币×确认×低流动性 是否强于 新币×确认×高流动性（容量锚 × 时间锚叠加）？
2. 排除 pump 类（上市后最大涨幅 > 300%）后尾部是否改善（账户 D 调整依据）？

事件：washout（149/157 口径）+ 上市 <90 天 + 4h 确认（r4>0）。
流动性：事件时点 24h 成交额（155 口径），中位数切高低。
pump 类：事件时点距上市的最高涨幅（上市低点→当前）> 300%。
基线：随机横截面；168h 超额 + 中位数 + 尾切。

输出：reports/s009_s010_stack.md
用法：python scripts/160_s009_s010_stack.py
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

REPORT = PROJECT_ROOT / "reports" / "s009_s010_stack.md"
LO_MS = int(pd.Timestamp("2022-01-01", tz="UTC").timestamp() * 1000)
HI_MS = int(pd.Timestamp("2026-06-30", tz="UTC").timestamp() * 1000)
NEW_DAYS = 90
MIN_EVENTS = 30
N_BASELINE = 3000
SEED = 2026
PUMP_THR = 300.0


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

    # 流动性 + washout + 确认 + 上市年龄 + pump 涨幅
    ev_parts = []
    for sym, ctx in ctxs.items():
        if sym not in listed:
            continue
        axis = ctx.index.to_numpy(dtype=np.int64)
        close = ctx["close"].to_numpy(dtype=float)
        # 流动性（155 口径）
        qv = None
        p = m113.COINGLASS_RAW1H / "klines" / f"{sym}.parquet"
        if p.exists():
            try:
                kdf = pd.read_parquet(p, columns=["open_time", "quote_volume"])
                kts = pd.to_numeric(kdf["open_time"], errors="coerce").to_numpy(dtype=np.int64)
                kqv = pd.to_numeric(kdf["quote_volume"], errors="coerce").to_numpy(dtype=float)
                qs = pd.Series(kqv, index=pd.Index(kts))
                qs = qs[~qs.index.duplicated(keep="last")].sort_index()
                liq24 = qs.reindex(ctx.index).rolling(24).sum().to_numpy(dtype=float)
            except Exception:
                liq24 = np.full(len(ctx), np.nan)
        else:
            liq24 = np.full(len(ctx), np.nan)
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
            if r4 <= 0:
                continue
            # pump：上市以来最高涨幅（NaN 安全）
            since = close[:i + 1]
            if np.isfinite(since).sum() < 2:
                continue
            gain = (np.nanmax(since) / np.nanmin(since) - 1) * 100.0
            ev_parts.append({"symbol": sym, "t": t, "r168": r168, "r4": r4,
                             "liq24": liq24[i], "pump_gain": gain})
    ev = pd.DataFrame(ev_parts)
    ev = ev[(ev["t"] >= LO_MS) & (ev["t"] <= HI_MS)]
    print(f"新币×确认事件 {len(ev)}")

    rng = np.random.default_rng(SEED)
    base = draw_random_events(ctxs, N_BASELINE, rng, max_forward_hours=168,
                              start_ms=LO_MS, end_ms=HI_MS)
    bparts = []
    for bs, bg in base.groupby("symbol", sort=False):
        if bs in ctxs:
            bparts.append(forward_stats(ctxs[bs], bg.copy(), DEFAULT_HORIZONS))
    base_df = pd.concat(bparts, ignore_index=True) if bparts else pd.DataFrame()
    br168 = pd.to_numeric(base_df["ret_168h"], errors="coerce").dropna().to_numpy()

    lines = ["# 叠加检验：新币期 × 低流动性 × 4h 确认（160）\n",
             f"- 生成：{datetime.now(timezone.utc):%Y-%m-%d %H:%M UTC}",
             f"- 事件：washout + 上市 <{NEW_DAYS}天 + 4h 确认（157 口径），共 {len(ev)}",
             "- 流动性中位数切：低（容量锚）/ 高；pump 类 = 上市以来最大涨幅 > 300%",
             "- 基线：随机横截面；168h 超额 + 中位数 + 尾切\n",
             "| 组 | n | 168h 超额 | CI | 中位数 | 尾切 | 判定 |",
             "|---|---|---:|---:|---:|---:|---|"]

    def row(label: str, g: pd.DataFrame) -> None:
        n = len(g)
        if n == 0:
            lines.append(f"| {label} | 0 | - | - | - | - | 无事件 |")
            return
        r = g["r168"].to_numpy(dtype=float)
        ci = bootstrap_ci(r, br168, n_boot=1000, alpha=0.05, seed=SEED)
        thr = np.quantile(r, 0.95)
        tail = r[r <= thr].mean()
        verdict = ("样本不足" if n < MIN_EVENTS else
                   "GO_LONG" if ci["ci_lo"] > 0 else
                   "GO_SHORT" if ci["ci_hi"] < 0 else "NO_GO")
        lines.append(f"| {label} | {n} | {ci['mean_diff']:+.2f}% "
                     f"| [{ci['ci_lo']:+.2f}, {ci['ci_hi']:+.2f}] | {np.median(r):+.2f}% "
                     f"| {tail:+.2f}% | **{verdict}** |")
        print(f"[160] {label}: n={n} ex168={ci['mean_diff']:+.2f}% med={np.median(r):+.2f}% tail={tail:+.2f}%")

    usable = ev[ev["liq24"].notna()]
    med_liq = usable["liq24"].median()
    row("新币×确认 全部（157 对照）", ev)
    row("×低流动性（<中位）", usable[usable["liq24"] < med_liq])
    row("×高流动性（≥中位）", usable[usable["liq24"] >= med_liq])
    row("×非 pump（涨幅≤300%）", ev[ev["pump_gain"] <= PUMP_THR])
    row("×pump（涨幅>300%）", ev[ev["pump_gain"] > PUMP_THR])
    row("×低流动性×非pump", usable[(usable["liq24"] < med_liq) & (usable["pump_gain"] <= PUMP_THR)])

    lines.extend(["\n## 解读\n",
                   "- 低流动性 × 新币 × 确认显著强于高流动性 → 容量锚×时间锚叠加（账户 D 参数优化依据）。",
                   "- 非 pump 显著强于 pump → TaskNewPool 建议落地（账户 D 排除 pump 类）。",
                   "- 两者皆无差 → 叠加不成立，s009/s010 保持独立。"])
    REPORT.parent.mkdir(parents=True, exist_ok=True)
    REPORT.write_text("\n".join(lines) + "\n", encoding="utf-8")
    print(f"wrote {REPORT}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
