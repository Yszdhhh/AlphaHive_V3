r"""162_funding_oi_quadrant.py — funding × OI 联合拥挤度四象限（私信建议 + gpt 方案 B 交叉验证）。

背景：146/147 已证伪【裸 funding 极值反转】（基线 bug 修正后 NO_GO、尾部驱动）。
外部建议（私信 + gpt 方案 B）独立指向：funding 必须与 OI 变化交叉才有区分度——
- FH（funding 高）+ OI↑ = 新开多单，拥挤在【积累】（前瞻：继续涨？还是即将踩踏？）
- FH + OI↓ = 老仓平掉，拥挤在【出清】（前瞻：卖压释放，反弹？）
- FL（funding 低/负）+ OI↑ = 空头积累
- FL + OI↓ = 空头出清

方法（吸取 147 教训，全 gauntlet）：
- funding_norm：30d min-max（146 口径）；OI 24h 变化 %（oi_ohlc，141 口径）
- 四象限切：funding_norm > 0.75（FH）/ < 0.25（FL）；oi_24h_chg > +1%（OI↑）/ < -1%（OI↓）
- 窗口 2024-06→2026-05（OI 覆盖）；基线随机横截面；168h 超额 + 中位数 + 尾切 + 独立窗口
- 与 wash_cvd 的关系：不限定事件，全时点横截面状态（事件化：状态持续时触发）

输出：reports/funding_oi_quadrant.md
用法：python scripts/162_funding_oi_quadrant.py
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

REPORT = PROJECT_ROOT / "reports" / "funding_oi_quadrant.md"
LO_MS = int(pd.Timestamp("2024-06-01", tz="UTC").timestamp() * 1000)
HI_MS = int(pd.Timestamp("2026-05-31", tz="UTC").timestamp() * 1000)
MIN_EVENTS = 30
N_BASELINE = 3000
SEED = 2026
FH = 0.75
FL = 0.25
OI_UP = 1.0
OI_DOWN = -1.0
COOLDOWN_H = 72


def build_state(sym: str) -> pd.DataFrame | None:
    """ctx + funding_norm + oi_24h_chg（无前视，146/141 口径）。"""
    p = m113.COINGLASS_RAW1H / "klines" / f"{sym}.parquet"
    if not p.exists():
        return None
    df = pd.read_parquet(p)
    if "open_time" not in df.columns or "close" not in df.columns:
        return None
    ts = pd.to_numeric(df["open_time"], errors="coerce").to_numpy(dtype=np.int64)
    close = pd.to_numeric(df["close"], errors="coerce").to_numpy(dtype=float)
    s = pd.Series(close)
    med = s.rolling(720, min_periods=360).median()
    ratio = s / med.replace(0, np.nan)
    close = np.where((ratio >= 0.02) & (ratio <= 50.0), close, np.nan)
    out = pd.DataFrame({"close": close}, index=pd.Index(ts))
    # funding_norm（146 口径）
    fund = m113.load_funding_series([sym]).get(sym)
    if fund is not None and len(fund):
        f2 = fund[fund.index >= LO_MS]
        flo = f2.rolling(90, min_periods=45).min()
        fhi = f2.rolling(90, min_periods=45).max()
        fnorm = ((f2 - flo) / (fhi - flo).replace(0, np.nan)).reindex(out.index, method="ffill")
        out["funding_norm"] = fnorm.to_numpy()
    # OI 24h 变化（141 口径）
    op = m113.COINGLASS_RAW1H / "oi_ohlc" / f"{sym}.parquet"
    if op.exists():
        od = pd.read_parquet(op)
        if {"time", "close"}.issubset(od.columns):
            ots = pd.to_numeric(od["time"], errors="coerce").to_numpy(dtype=np.int64)
            oc = pd.to_numeric(od["close"], errors="coerce").to_numpy(dtype=float)
            oser = pd.Series(oc, index=pd.Index(ots))
            oser = oser[~oser.index.duplicated(keep="last")].sort_index().reindex(out.index)
            out["oi_24h_chg"] = (oser.pct_change(24) * 100.0).to_numpy()
    return out.dropna(subset=["close"])


def quadrant(fn: float, oi: float) -> str:
    if not np.isfinite(fn) or not np.isfinite(oi):
        return "NA"
    fh = fn > FH
    fl = fn < FL
    oup = oi > OI_UP
    odn = oi < OI_DOWN
    if fh and oup:
        return "FH_OIup"
    if fh and odn:
        return "FH_OIdown"
    if fl and oup:
        return "FL_OIup"
    if fl and odn:
        return "FL_OIdown"
    return "MID"


def main() -> int:
    symbols = m113.load_universe_symbols()
    ctxs = {s: build_state(s) for s in symbols}
    ctxs = {s: c for s, c in ctxs.items() if c is not None and len(c) > 1000}
    print(f"状态 ctx {len(ctxs)}")

    # 事件化：象限状态出现时触发（72h 冷却），forward 168h
    rows = []
    for sym, ctx in ctxs.items():
        axis = ctx.index.to_numpy(dtype=np.int64)
        close = ctx["close"].to_numpy(dtype=float)
        fn = ctx["funding_norm"].to_numpy(dtype=float) if "funding_norm" in ctx else np.full(len(ctx), np.nan)
        oi = ctx["oi_24h_chg"].to_numpy(dtype=float) if "oi_24h_chg" in ctx else np.full(len(ctx), np.nan)
        last_q: dict[str, int] = {}
        for i in range(len(axis)):
            t = int(axis[i])
            if t < LO_MS or t > HI_MS:
                continue
            q = quadrant(fn[i], oi[i])
            if q == "NA" or q == "MID":
                continue
            if last_q.get(q, -10**18) + COOLDOWN_H * 3_600_000 > t:
                continue
            if i + 168 >= len(close):
                continue
            r168 = (close[i + 168] / close[i] - 1) * 100.0
            if not np.isfinite(r168):
                continue
            rows.append({"symbol": sym, "t": t, "q": q, "r168": r168,
                         "fn": fn[i], "oi": oi[i]})
            last_q[q] = t
    ev = pd.DataFrame(rows)
    print(f"象限事件 {len(ev)}: {ev['q'].value_counts().to_dict()}")

    rng = np.random.default_rng(SEED)
    base = draw_random_events(ctxs, N_BASELINE, rng, max_forward_hours=168,
                              start_ms=LO_MS, end_ms=HI_MS)
    bparts = []
    for bs, bg in base.groupby("symbol", sort=False):
        if bs in ctxs:
            bparts.append(forward_stats(ctxs[bs], bg.copy(), DEFAULT_HORIZONS))
    base_df = pd.concat(bparts, ignore_index=True) if bparts else pd.DataFrame()
    br168 = pd.to_numeric(base_df["ret_168h"], errors="coerce").dropna().to_numpy()

    lines = ["# funding × OI 联合拥挤度四象限（162）\n",
             f"- 生成：{datetime.now(timezone.utc):%Y-%m-%d %H:%M UTC}",
             f"- 象限：FH=funding_norm>{FH} / FL<{FL}；OI↑=24h 变化>{OI_UP}% / OI↓<{OI_DOWN}%",
             f"- 事件：象限状态出现（72h 冷却），窗口 2024-06→2026-05（OI 覆盖）",
             "- 外部交叉验证：私信建议 + gpt 方案 B 独立指向本检验（146 证伪的裸反转不重复）",
             "- 基线：随机横截面；168h 超额 + 中位数 + 尾切 + 独立窗口\n",
             "| 象限 | 语义 | n | 168h 超额 | CI | 中位数 | 尾切 | W1(<25') | W2(25'+) | 判定 |",
             "|---|---|---:|---:|---:|---:|---:|---:|---:|---|"]

    def row(q: str, desc: str) -> None:
        g = ev[ev["q"] == q]
        n = len(g)
        if n < MIN_EVENTS:
            lines.append(f"| {q} | {desc} | {n} | - | - | - | - | - | - | 样本不足 |")
            return
        r = g["r168"].to_numpy(dtype=float)
        ci = bootstrap_ci(r, br168, n_boot=1000, alpha=0.05, seed=SEED)
        thr = np.quantile(r, 0.95)
        tail = r[r <= thr].mean()
        split = int(pd.Timestamp("2025-01-01", tz="UTC").timestamp() * 1000)
        w1 = r[g["t"].to_numpy() < split]
        w2 = r[g["t"].to_numpy() >= split]
        w1s = f"{w1.mean():+.2f}%({len(w1)})" if len(w1) >= 10 else "n<10"
        w2s = f"{w2.mean():+.2f}%({len(w2)})" if len(w2) >= 10 else "n<10"
        verdict = ("样本不足" if n < MIN_EVENTS else
                   "GO_LONG" if ci["ci_lo"] > 0 else
                   "GO_SHORT" if ci["ci_hi"] < 0 else "NO_GO")
        lines.append(f"| {q} | {desc} | {n} | {ci['mean_diff']:+.2f}% "
                     f"| [{ci['ci_lo']:+.2f}, {ci['ci_hi']:+.2f}] | {np.median(r):+.2f}% "
                     f"| {tail:+.2f}% | {w1s} | {w2s} | **{verdict}** |")
        print(f"[162] {q}: n={n} ex168={ci['mean_diff']:+.2f}% med={np.median(r):+.2f}% {verdict}")

    row("FH_OIup", "高费率+OI↑（多头积累）")
    row("FH_OIdown", "高费率+OI↓（多头出清）")
    row("FL_OIup", "低费率+OI↑（空头积累）")
    row("FL_OIdown", "低费率+OI↓（空头出清）")

    lines.extend(["\n## 解读\n",
                   "- 私信预测：FH_OIup（积累）与 FH_OIdown（出清）前瞻【截然相反】——若成立，funding×OI 联合有区分度（146 裸反转证伪的边界）。",
                   "- FH_OIdown 显著 GO_LONG → 出清后反弹（与 wash_cvd 机制呼应）；显著 GO_SHORT → 出清未完。",
                   "- 独立窗口两段同号 + 尾切仍正 → 可交易候选；否则保持认知。",
                   "- 若四象限均 NO_GO → funding×OI 联合也不构成 edge，外部建议证伪。"])
    REPORT.parent.mkdir(parents=True, exist_ok=True)
    REPORT.write_text("\n".join(lines) + "\n", encoding="utf-8")
    print(f"wrote {REPORT}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
