r"""215_newcoin_age_test.py — 方向 A：新币生命周期 washout 深化（grok 通道B 优先级 1）。

E19（新币期 washout×4h确认，168h +5.82%）已验证。本测试深化：
① 上市日龄分箱（0-7d / 7-30d / 30-90d / >90d）——谁在付钱随日龄变化
② 4h 确认子集（E19 口径）
③ 日龄边界敏感（60/90/120，预注册后一次，不网格搜）
④ 与母边（wash_cvd）重叠率 → 独立事件超额
⑤ 成本：E20 低流动性代理分层（新币点差更大，须成本分层）

口径与 157 一致：washout（price_z<-2 或 ret24<-8%）+ 72h 冷却，age = 事件 ts − 首根 kline。
输出：reports/newcoin_age_test.md
用法：python scripts/215_newcoin_age_test.py
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

from harness.lib.event_study import bootstrap_ci, draw_random_events, forward_stats  # noqa: E402

_spec = importlib.util.spec_from_file_location(
    "m113", str(PROJECT_ROOT / "scripts" / "113_washout_settle_study.py"))
m113 = importlib.util.module_from_spec(_spec)
sys.modules["m113"] = m113
_spec.loader.exec_module(m113)

REPORT = PROJECT_ROOT / "reports" / "newcoin_age_test.md"
LO_MS = int(pd.Timestamp("2021-12-01", tz="UTC").timestamp() * 1000)
HI_MS = int(pd.Timestamp("2026-07-01", tz="UTC").timestamp() * 1000)
MIN_EVENTS = 20
SEED = 2026
AGE_BUCKETS = [(0, 7, "0-7d"), (7, 30, "7-30d"), (30, 90, "30-90d"), (90, 10**9, ">90d")]


def main() -> int:
    symbols = m113.load_universe_symbols()
    ctxs = m113.load_price_ctx(symbols)
    # 上市日 = 首根 kline
    listed = {}
    for sym in symbols:
        p = m113.COINGLASS_RAW1H / "klines" / f"{sym}.parquet"
        if p.exists():
            df = pd.read_parquet(p, columns=["open_time"])
            if len(df):
                listed[sym] = int(df["open_time"].min())
    print(f"有上市日 {len(listed)}/{len(symbols)}")

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
        evs, last = [], -10**18
        for i in np.flatnonzero(fired):
            t = int(axis[i])
            if t - last >= 72 * 3_600_000:
                evs.append(t)
                last = t
        if evs:
            ev_parts.append(pd.DataFrame({"symbol": sym, "timestamp": evs}))
    events = pd.concat(ev_parts, ignore_index=True) if ev_parts else pd.DataFrame(
        columns=["symbol", "timestamp"])
    events = events[(events["timestamp"] >= LO_MS) & (events["timestamp"] <= HI_MS)].copy()
    events["listing_ms"] = events["symbol"].map(listed)
    events["age_days"] = (events["timestamp"] - events["listing_ms"]) / (24 * 3_600_000)

    # 前向 + 4h 确认 + wash_cvd 重叠（cvd_div>2）+ 低流动性代理（事件前 24h 成交额分位）
    fwd = []
    for sym, g in events.groupby("symbol", sort=False):
        ctx = ctxs[sym]
        axis = ctx.index.to_numpy(dtype=np.int64)
        close = ctx["close"].to_numpy(dtype=float)
        qv = pd.to_numeric(ctx["quote_volume"], errors="coerce") if "quote_volume" in ctx.columns else None
        cvd_div = pd.to_numeric(ctx["cvd_divergence"], errors="coerce") if "cvd_divergence" in ctx.columns else None
        for _, ev_row in g.iterrows():
            t = int(ev_row["timestamp"])
            pos = int(np.searchsorted(axis, t, side="right")) - 1
            if pos < 0 or pos + 168 >= len(close):
                continue
            r4 = (close[pos + 4] / close[pos] - 1) * 100.0
            r24 = (close[pos + 24] / close[pos] - 1) * 100.0
            r168 = (close[pos + 168] / close[pos] - 1) * 100.0
            if not (np.isfinite(r4) and np.isfinite(r24) and np.isfinite(r168)):
                continue
            liq = float(qv.iloc[pos - 24:pos].sum()) if qv is not None else np.nan
            wc = bool(np.isfinite(cvd_div.iloc[pos]) and cvd_div.iloc[pos] > 2.0) if cvd_div is not None else False
            fwd.append({"symbol": sym, "t": t, "age_days": float(ev_row["age_days"]),
                        "r4": r4, "r24": r24, "r168": r168, "liq_24h": liq, "wash_cvd": wc})
    ev = pd.DataFrame(fwd)
    ev["confirm"] = ev["r4"] > 0
    print(f"washout 事件 {len(ev)}")

    # 基线（同窗随机横截面）
    rng = np.random.default_rng(SEED)
    base = draw_random_events(ctxs, 3000, rng, max_forward_hours=168, start_ms=LO_MS, end_ms=HI_MS)
    bparts = []
    for bs, bg in base.groupby("symbol", sort=False):
        if bs in ctxs:
            bparts.append(forward_stats(ctxs[bs], bg.copy(), (168,)))
    bdf = pd.concat(bparts, ignore_index=True) if bparts else pd.DataFrame()
    br168 = pd.to_numeric(bdf["ret_168h"], errors="coerce").dropna().to_numpy()

    lines = ["# 新币生命周期 washout 深化（215，方向 A）\n",
             f"- 生成：{datetime.now(timezone.utc):%Y-%m-%d %H:%M UTC}",
             f"- 事件：washout（{len(ev)}，72h 冷却）；上市日 = 首根 kline；确认 = 4h 反弹\n",
             "## ① 日龄分箱 × 4h 确认（168h）\n",
             "| 日龄 | n | 均值 | 超额 CI | 中位 | 尾切 | 确认子集 n | 确认均值 | 判定 |",
             "|---|---|---:|---:|---:|---:|---:|---:|---|"]
    for lo, hi, name in AGE_BUCKETS:
        g = ev[(ev["age_days"] >= lo) & (ev["age_days"] < hi)]
        n = len(g)
        if n == 0:
            lines.append(f"| {name} | 0 | - | - | - | - | - | - | 无事件 |")
            continue
        r = g["r168"].to_numpy(dtype=float)
        ci = bootstrap_ci(r, br168, seed=SEED)
        thr = np.quantile(r, 0.95)
        gc = g[g["confirm"]]
        rc = gc["r168"].to_numpy(dtype=float) if len(gc) else np.array([])
        verdict = ("样本不足" if n < MIN_EVENTS else
                   "GO_LONG" if ci["ci_lo"] > 0 else "NO_GO")
        lines.append(f"| {name} | {n} | {r.mean():+.2f}% | [{ci['ci_lo']:+.2f}, {ci['ci_hi']:+.2f}] | "
                     f"{np.median(r):+.2f}% | {r[r <= thr].mean():+.2f}% | {len(gc)} | "
                     f"{rc.mean():+.2f}% | {verdict} |")
        print(f"[215] {name}: n={n} 均值 {r.mean():+.2f}% 确认 {len(gc)} 均值 {rc.mean():+.2f}%")

    # ③ 日龄边界敏感（60/90/120）
    lines.append("\n## ③ 日龄边界敏感（新币期=上市后 N 天内，确认子集 168h）\n")
    lines.append("| 边界 | n | 均值 | 超额 CI | 判定 |")
    lines.append("|---|---|---:|---:|---|")
    for nd in (60, 90, 120):
        g = ev[(ev["age_days"] < nd) & ev["confirm"]]
        r = g["r168"].to_numpy(dtype=float)
        if len(r) >= MIN_EVENTS:
            ci = bootstrap_ci(r, br168, seed=SEED)
            v = "GO_LONG" if ci["ci_lo"] > 0 else "NO_GO"
            lines.append(f"| <{nd}d | {len(r)} | {r.mean():+.2f}% | [{ci['ci_lo']:+.2f}, {ci['ci_hi']:+.2f}] | {v} |")
            print(f"[215] <{nd}d 确认: n={len(r)} 均值 {r.mean():+.2f}%")
        else:
            lines.append(f"| <{nd}d | {len(r)} | - | - | 样本不足 |")

    # ④ 母边重叠（wash_cvd）+ ⑤ 低流动性分层
    lines.append("\n## ④ wash_cvd 重叠（新币确认子集）\n")
    gc = ev[ev["confirm"]]
    wc_share = gc["wash_cvd"].mean() if len(gc) else 0.0
    lines.append(f"- 新币确认事件中同时是 wash_cvd（cvd_div>2）：{wc_share:.0%}（E19 参考 24%）")
    lines.append("\n## ⑤ 低流动性分层（新币确认子集，成本代理）\n")
    lines.append("| 流动性 | n | 168h 均值 | 判定参考 |")
    lines.append("|---|---:|---:|---|")
    med_liq = gc["liq_24h"].median()
    for label, m in [("低流动性（<中位）", gc["liq_24h"] < med_liq), ("高流动性", gc["liq_24h"] >= med_liq)]:
        r = gc[m]["r168"].to_numpy(dtype=float)
        if len(r):
            lines.append(f"| {label} | {len(r)} | {r.mean():+.2f}% | E20 低流动性 +2.60% 参考 |")
            print(f"[215] {label}: n={len(r)} 均值 {r.mean():+.2f}%")

    lines += ["\n## 解读\n",
              "- 日龄分箱单调（越新越强）且确认子集全正 → 新币生命周期是独立于母边的付钱结构（首周杠杆赌徒）；",
              "- 若 0-7d 显著 > 7-30d > 30-90d → 时间锚成立，可进 s009 参数（日龄上界）；",
              "- 低流动性分层：新币天然低流动，须成本分层确认（E20/E25），否则幅度含滑点幻觉。"]
    REPORT.parent.mkdir(parents=True, exist_ok=True)
    REPORT.write_text("\n".join(lines) + "\n", encoding="utf-8")
    print(f"wrote {REPORT}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
