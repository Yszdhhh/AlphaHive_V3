r"""195_delisted_full_retest.py — wash_cvd 下架池完整复测（旗舰 E01 幸存者偏差终极检验）。

问题：E01 wash_cvd 的历史证据全部来自存活币（universe.json 66 符号）。183 只复测了
s009 的简化版（纯价格 washout + 4h 确认，无 CVD 层），均值 +6.25% 证明"确认机制非运气"。
本脚本把**带 CVD 层的完整 wash_cvd**（115 口径）推到下架池（SETTLING 127 ∪ GONE 31，
= master 分类），回答：卖压枯竭 edge 在下架资产上是否同样成立？

- wash_cvd = (price_z<-2.0 | ret24<-8%) AND cvd_divergence>2.0，72h 冷却（与 115 逐字一致）
- CVD 近似 = cumsum(2*taker_buy_quote_volume - quote_volume)（113 口径，fapi klines 有 taker）
- 4h 确认子集（r4>0）= s009/E18 机制的下架池版本（对照 183 +6.25%）
- 基线 = 同 episode 随机下架币横截面（draw_random_events，与 115/109 同款）
- 指标与 115 对齐：24h 超额 CI 为主判定，168h 均值/中位/胜率为辅
- episode 切分 2022/2023/2024/2025+，对照 115 幸存池同 episode 已发布数字

只读研究，不碰 config/触发/纸面。
输出：reports/delisted_full_retest.md
用法：python scripts/195_delisted_full_retest.py [--n-baseline 3000] [--seed 2026]
"""
from __future__ import annotations

import argparse
import sys
from datetime import datetime, timezone
from pathlib import Path

import numpy as np
import pandas as pd

PROJECT_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(PROJECT_ROOT))

from harness.lib.event_study import (  # noqa: E402
    bootstrap_ci,
    draw_random_events,
    forward_stats,
)

CACHE = PROJECT_ROOT / "data" / "delisted_raw"
MASTER = PROJECT_ROOT / "data" / "delisted_master.csv"
REPORT = PROJECT_ROOT / "reports" / "delisted_full_retest.md"

CVD_THRESHOLD = 2.0
WASH_PRICE_Z = -2.0
WASH_RET_24H = -8.0
COOLDOWN_H = 72.0
WINDOW = 720
HORIZONS = (4, 24, 72, 168)

# 115 幸存池 wash_cvd 24h 超额引用（2026-08-06 已发布报告，引用不重算）
SURVIVOR_REF = {
    "2022": ("+1.21% CI[-0.02,+2.38] NO_GO(擦边)", "2022熊底+FTX底"),
    "2023": ("+1.75% CI[+0.83,+2.68] GO_LONG", "2023平台蓄力"),
    "2024": ("+1.46% CI[+0.48,+2.52] GO_LONG", "2024崩→恢复"),
    "2025+": ("+0.85% CI[+0.06,+1.68] GO_LONG", "2025顶→熊"),
}

EPISODE_MS = {
    "2022": (pd.Timestamp("2022-01-01", tz="UTC"), pd.Timestamp("2023-01-01", tz="UTC")),
    "2023": (pd.Timestamp("2023-01-01", tz="UTC"), pd.Timestamp("2024-01-01", tz="UTC")),
    "2024": (pd.Timestamp("2024-01-01", tz="UTC"), pd.Timestamp("2025-01-01", tz="UTC")),
    "2025+": (pd.Timestamp("2025-01-01", tz="UTC"), None),
}


def build_ctx(df: pd.DataFrame) -> pd.DataFrame:
    """113 口径价格上下文：close/ret_24h/price_z/cvd/cvd_z/cvd_divergence。"""
    ts = df["t"].to_numpy(dtype=np.int64)
    close = df["c"].to_numpy(dtype=float)
    qv = df["qv"].to_numpy(dtype=float) if "qv" in df.columns else np.full(len(ts), np.nan)
    tb = df["tbqv"].to_numpy(dtype=float) if "tbqv" in df.columns else np.full(len(ts), np.nan)
    s = pd.Series(close, index=pd.Index(ts))
    s = s[~s.index.duplicated(keep="last")].sort_index()
    t = pd.DataFrame(index=s.index)
    t["close"] = s
    t["ret_24h"] = s.pct_change(24) * 100.0
    r = s.rolling(WINDOW, min_periods=WINDOW // 3)
    t["price_z"] = (s - r.mean()) / r.std().replace(0, np.nan)
    cvd = pd.Series(np.cumsum(2.0 * tb - qv), index=pd.Index(ts))
    cvd = cvd[~cvd.index.duplicated(keep="last")].sort_index()
    cr = cvd.rolling(WINDOW, min_periods=WINDOW // 3)
    cvd_z = (cvd - cr.mean()) / cr.std().replace(0, np.nan)
    t["cvd_divergence"] = t["price_z"] - cvd_z.reindex(t.index)
    return t


def detect_wash_cvd(ctx: pd.DataFrame) -> np.ndarray:
    price_z = ctx["price_z"].to_numpy()
    ret24 = ctx["ret_24h"].to_numpy()
    cvd_div = ctx["cvd_divergence"].to_numpy()
    finite = np.isfinite(price_z) & np.isfinite(ret24) & np.isfinite(cvd_div)
    wash = (price_z < WASH_PRICE_Z) | (ret24 < WASH_RET_24H)
    fired = finite & wash & (cvd_div > CVD_THRESHOLD)
    axis = ctx.index.to_numpy(dtype=np.int64)
    cooldown = int(COOLDOWN_H * 3_600_000)
    evs: list[int] = []
    last = -10**18
    for i in np.flatnonzero(fired):
        t = int(axis[i])
        if t - last >= cooldown:
            evs.append(t)
            last = t
    return np.array(evs, dtype=np.int64)


def episode_of(ts: int) -> str:
    y = datetime.fromtimestamp(ts / 1000, tz=timezone.utc).year
    return "2022" if y == 2022 else "2023" if y == 2023 else "2024" if y == 2024 else "2025+"


def forward_by_symbol(tables: dict[str, pd.DataFrame], events: pd.DataFrame) -> pd.DataFrame:
    """按 symbol 分组调 forward_stats（115 同款，避免跨 symbol 串表）。"""
    parts = []
    for sym, g in events.groupby("symbol", sort=False):
        parts.append(forward_stats(tables[sym], g.copy(), horizons=HORIZONS))
    return pd.concat(parts, ignore_index=True) if parts else events


def baseline_for(tables: dict[str, pd.DataFrame], rng: np.random.Generator,
                 n: int, start_ms: int | None, end_ms: int | None) -> np.ndarray:
    base = draw_random_events(tables, n, rng, max_forward_hours=168,
                              start_ms=start_ms, end_ms=end_ms)
    if base.empty:
        return np.array([])
    parts = []
    for bs, bg in base.groupby("symbol", sort=False):
        parts.append(forward_stats(tables[bs], bg.copy(), horizons=(168,)))
    b = pd.concat(parts, ignore_index=True)
    return pd.to_numeric(b["ret_168h"], errors="coerce").dropna().to_numpy(dtype=float)


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--n-baseline", type=int, default=3000)
    ap.add_argument("--seed", type=int, default=2026)
    args = ap.parse_args()

    master = pd.read_csv(MASTER)
    pool = sorted(master.loc[master["category"].isin(
        ["SETTLING", "USDT_PERP_GONE"]), "symbol"].tolist())

    tables: dict[str, pd.DataFrame] = {}
    usable = 0
    for sym in pool:
        cp = CACHE / f"{sym}.parquet"
        if not cp.exists():
            continue
        try:
            df = pd.read_parquet(cp)
        except Exception:  # noqa: BLE001
            continue
        if len(df) < 800:
            continue
        ctx = build_ctx(df)
        if ctx["cvd_divergence"].notna().sum() < 200:
            continue
        tables[sym] = ctx
        usable += 1

    rows: list[dict] = []
    for sym, ctx in tables.items():
        for ts in detect_wash_cvd(ctx):
            rows.append({"symbol": sym, "timestamp": int(ts), "episode": episode_of(int(ts))})
    events = pd.DataFrame(rows)
    print(f"下架池可用 {usable}/{len(pool)} | wash_cvd 事件 {len(events)}")
    if len(events) == 0:
        print("no events")
        return 1

    ev = forward_by_symbol(tables, events)
    rng = np.random.default_rng(args.seed)

    def ci_str(ev_v: np.ndarray, bs_v: np.ndarray) -> str:
        if len(ev_v) == 0 or len(bs_v) == 0:
            return "-"
        c = bootstrap_ci(ev_v, bs_v, seed=args.seed)
        return f"{c['mean_diff']:+.2f}% [{c['ci_lo']:+.2f}, {c['ci_hi']:+.2f}]"

    lines = ["# 下架池 wash_cvd 完整复测（195，E01 幸存者偏差终极检验）\n",
             f"- 生成：{datetime.now(timezone.utc):%Y-%m-%d %H:%M UTC}",
             f"- 下架池 = SETTLING(127) ∪ USDT_PERP_GONE(31)，可用 {usable}/{len(pool)}",
             f"- wash_cvd 事件 {len(events)}（115 口径：washout 且 cvd_div>2.0，72h 冷却）",
             f"- 基线 = 同 episode 随机下架币横截面（draw_random_events，与 115/109 同款）\n",
             "| 组 | n | 168h 均值 | 168h 中位 | 胜率 | 168h 超额 CI | 判定参考 |",
             "|---|---|---:|---:|---:|---:|---|"]

    # 池级：全事件 / 4h 确认 / 无确认
    base_pool = baseline_for(tables, rng, args.n_baseline,
                             int(pd.Timestamp("2022-01-01", tz="UTC").timestamp() * 1000), None)
    for label, mask, ref in [
        ("下架池 wash_cvd 全", np.ones(len(ev), dtype=bool),
         "幸存池 pooled 24h +1.31%（E01，2022-2025）"),
        ("下架池 wash_cvd + 4h确认", (ev["ret_4h"] > 0).to_numpy(),
         "183 下架池 +6.25%（无 CVD 层）/ 幸存新币 +5.82%"),
        ("下架池 wash_cvd 无确认", (ev["ret_4h"] <= 0).to_numpy(),
         "幸存 confirm−reject +5.04pp（148）"),
    ]:
        sub = ev[mask]
        v = pd.to_numeric(sub["ret_168h"], errors="coerce").dropna().to_numpy(dtype=float)
        if len(v) == 0:
            lines.append(f"| {label} | 0 | - | - | - | - | {ref} |")
            continue
        lines.append(f"| {label} | {len(v)} | {v.mean():+.2f}% | {np.median(v):+.2f}% | "
                     f"{100 * (v > 0).mean():.0f}% | {ci_str(v, base_pool)} | {ref} |")

    # 分 episode：24h 超额 CI（与 115 对齐）+ 168h 均值
    lines.append("\n## 分 episode（下架池 24h 超额 CI vs 115 幸存池引用）\n")
    lines.append("| episode | 下架池 n | 下架池 24h 超额 CI | 下架池 168h 均值 | 幸存池引用（115） |")
    lines.append("|---|---|---:|---:|---|")
    for ep, (s_ts, e_ts) in EPISODE_MS.items():
        sub = ev[ev["episode"] == ep]
        v24 = pd.to_numeric(sub["ret_24h"], errors="coerce").dropna().to_numpy(dtype=float)
        v168 = pd.to_numeric(sub["ret_168h"], errors="coerce").dropna().to_numpy(dtype=float)
        if len(v24) == 0:
            lines.append(f"| {ep} | 0 | - | - | {SURVIVOR_REF[ep][0]} |")
            continue
        # 24h 超额需要 24h 基线
        base = draw_random_events(tables, args.n_baseline, rng, max_forward_hours=168,
                                  start_ms=int(s_ts.timestamp() * 1000),
                                  end_ms=int(e_ts.timestamp() * 1000) if e_ts is not None else None)
        bp24 = []
        if not base.empty:
            for bsym, bg in base.groupby("symbol", sort=False):
                bp24.append(forward_stats(tables[bsym], bg.copy(), horizons=(24,)))
            b24 = pd.concat(bp24, ignore_index=True)
            b24_v = pd.to_numeric(b24["ret_24h"], errors="coerce").dropna().to_numpy(dtype=float)
        else:
            b24_v = np.array([])
        lines.append(f"| {ep} | {len(v24)} | {ci_str(v24, b24_v)} | "
                     f"({np.nanmean(v168):+.2f}%, n={len(v168)}) | {SURVIVOR_REF[ep][0]} |")
        print(f"  [195] {ep}: n={len(v24)} 24h超额 {ci_str(v24, b24_v)}")

    lines.append("\n## 解读\n"
                 "- 下架池 wash_cvd（含 CVD 层）与幸存池同 episode 同向 → E01 是机制 edge（卖压枯竭），非幸存者运气。\n"
                 "- 若下架池显著弱/反转 → E01 历史收益含幸存者成分，wash_cvd 前向预期需下修。\n"
                 "- 4h 确认子集对照 183：新增 CVD 层后是否仍接近幸存新币 +5.82%。")
    REPORT.parent.mkdir(parents=True, exist_ok=True)
    REPORT.write_text("\n".join(lines) + "\n", encoding="utf-8")
    print(f"wrote {REPORT}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
