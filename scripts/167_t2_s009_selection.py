r"""167_t2_s009_selection.py — T2：s009 精选迁移（Sol 计划阶段1）。

新币 washout×4h 确认 事件 × 事件时点横截面评分 top50%（163 方法迁移）。
Sol 判定：不得降低 s009 中位数 + 净增量≥75bps。

评分（事件时点全 universe asof 截面百分位）：
- cvd_divergence pct（高 = 卖压枯竭更强）
- price_z pct（低 = washout 更深 → 用 1−pct）
- np_z pct（高 = 大户未流出）——新币池 net_position 覆盖可能缺失，缺失时权重归零

对照：s009 全事件 / top50% / bottom50%。
输出：reports/t2_s009_selection.md
用法：python scripts/167_t2_s009_selection.py
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

REPORT = PROJECT_ROOT / "reports" / "t2_s009_selection.md"
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


def add_np_z(ctx: pd.DataFrame, sym: str) -> np.ndarray:
    RAW = m113.COINGLASS_RAW1H
    np_p = RAW / "net_position" / f"{sym}.parquet"
    if not np_p.exists():
        return np.full(len(ctx), np.nan)
    try:
        n = pd.read_parquet(np_p)
        nts = pd.to_numeric(n["time"], errors="coerce").to_numpy(dtype=np.int64)
        nv = pd.to_numeric(n["net_position_change_cum"], errors="coerce").to_numpy(dtype=float)
        ns = pd.Series(nv, index=pd.Index(nts))
        ns = ns[~ns.index.duplicated(keep="last")].sort_index().reindex(ctx.index)
        return m113.rolling_z(ns, 720).to_numpy()
    except Exception:
        return np.full(len(ctx), np.nan)


def main() -> int:
    ctxs = m113.load_price_ctx(m113.load_universe_symbols())
    listed = listing_dates()

    # 预取特征数组
    feat: dict[str, dict] = {}
    for sym, ctx in ctxs.items():
        axis = ctx.index.to_numpy(dtype=np.int64)
        close = ctx["close"].to_numpy(dtype=float)
        cvd = pd.to_numeric(ctx.get("cvd_divergence", pd.Series(np.nan, index=ctx.index)),
                            errors="coerce").to_numpy(dtype=float)
        pz = pd.to_numeric(ctx.get("price_z", pd.Series(np.nan, index=ctx.index)),
                           errors="coerce").to_numpy(dtype=float)
        feat[sym] = {"axis": axis, "close": close, "cvd": cvd, "pz": pz,
                     "np": add_np_z(ctx, sym)}

    # s009 事件
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
            if np.isfinite(r4) and np.isfinite(r168) and r4 > 0:
                rows.append({"symbol": sym, "t": t, "i": i, "r168": r168})
    ev = pd.DataFrame(rows)
    ev = ev[(ev["t"] >= LO_MS) & (ev["t"] <= HI_MS)]
    print(f"s009 事件 {len(ev)}")

    # 事件时点横截面百分位
    for f in ["cvd", "pz", "np"]:
        ev[f"{f}_pct"] = np.nan
    for t, g in ev.groupby("t"):
        t = int(t)
        cross: dict[str, dict] = {}
        for sym in ctxs:
            fa = feat[sym]
            pos = int(np.searchsorted(fa["axis"], t, side="right")) - 1
            if pos < 0:
                continue
            cross[sym] = {f: (fa[f][pos] if pos < len(fa[f]) and np.isfinite(fa[f][pos]) else np.nan)
                          for f in ["cvd", "pz", "np"]}
        for f in ["cvd", "pz", "np"]:
            valid = {s: v[f] for s, v in cross.items() if np.isfinite(v[f])}
            if len(valid) < 10:
                continue
            arr = np.array(list(valid.values()))
            for s, v in valid.items():
                ev.loc[(ev["t"] == t) & (ev["symbol"] == s), f"{f}_pct"] = (arr < v).mean()
    # 合成分（cvd 高 + washout 深 + np 高；缺失维度权重均摊到可用维度）
    score_parts = []
    n_parts = []
    for f, sign in [("cvd", 1.0), ("pz", -1.0), ("np", 1.0)]:
        p = ev[f"{f}_pct"].fillna(0.5)
        score_parts.append(p * sign)
        n_parts.append(ev[f"{f}_pct"].notna().astype(float))
    ev["score"] = sum(score_parts) / pd.concat(n_parts, axis=1).sum(axis=1).clip(lower=1)

    rng = np.random.default_rng(SEED)
    base = draw_random_events(ctxs, N_BASELINE, rng, max_forward_hours=168,
                              start_ms=LO_MS, end_ms=HI_MS)
    bparts = []
    for bs, bg in base.groupby("symbol", sort=False):
        if bs in ctxs:
            bparts.append(forward_stats(ctxs[bs], bg.copy(), DEFAULT_HORIZONS))
    base_df = pd.concat(bparts, ignore_index=True) if bparts else pd.DataFrame()
    br168 = pd.to_numeric(base_df["ret_168h"], errors="coerce").dropna().to_numpy()

    lines = ["# T2：s009 精选迁移（167，Sol 计划）\n",
             f"- 生成：{datetime.now(timezone.utc):%Y-%m-%d %H:%M UTC}",
             "- 事件：新币 washout×4h 确认（s009）；评分 = 事件时点截面百分位合成",
             "- Sol 判定：精选 top50% 不得降低 s009 中位数 + 净增量≥75bps\n",
             "| 组 | n | 168h 均值 | 168h 超额 | CI | 中位数 | 尾切 | 判定 |",
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
        print(f"[167] {label}: n={n} ex168={ci['mean_diff']:+.2f}% med={np.median(r):+.2f}% {verdict}")

    row("s009 全（对照）", ev)
    top = ev[ev["score"] >= ev["score"].quantile(0.5)]
    bot = ev[ev["score"] < ev["score"].quantile(0.5)]
    row("精选 top50%", top)
    row("bottom50%", bot)

    if len(top) >= 10 and len(ev) >= 10:
        c = bootstrap_ci(top["r168"].to_numpy(), ev["r168"].to_numpy(),
                         n_boot=1000, alpha=0.05, seed=SEED + 1)
        med_delta = np.median(top["r168"]) - np.median(ev["r168"])
        lines.append(f"\n增量对照（top50% − s009 全）：超额 {c['mean_diff']:+.2f}% "
                     f"CI[{c['ci_lo']:+.2f}, {c['ci_hi']:+.2f}]；中位数变化 {med_delta:+.2f}%"
                     f"（{'✓ 中位数未降' if med_delta >= 0 else '✗ 中位数下降'}）")

    lines.extend(["\n## 裁决\n",
                   "- top50% 超额≥75bps 且中位数未降 → T2 通过（s009 加横截面精选，账户 D 参数升级）。",
                   "- 不满足 → T2 关闭（s009 保持全事件）。"])
    REPORT.parent.mkdir(parents=True, exist_ok=True)
    REPORT.write_text("\n".join(lines) + "\n", encoding="utf-8")
    print(f"wrote {REPORT}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
