r"""153_operator_search.py — 算子搜索 MVP（路线 #3，表达侧黑盒）。

WorldQuant 模式轻量版：自动生成"特征×阈值"候选事件，gauntlet 自动过滤。
本 MVP 只搜索【单特征极值事件】（与 wash_cvd 无关的独立事件源），
不搜组合（AND/交互）——那是下一轮扩展。

特征池（全部无前视，事件时点 asof）：
- ret_24h / price_z / cvd_divergence（113 ctx）
- qv24_ratio（放量：24h 量 / 30d 中位数，121 公式）
- funding_norm（30d min-max，146 公式）
- imb_norm（taker imbalance 30d min-max，151 公式）
- liq_short_z（131 公式，2024-06+）
- oi_24h_chg（OI 24h 变化 %，113 ctx）

搜索：每特征 × 方向（高/低）× 阈值（q85/q95 或等价绝对阈值）→ 候选事件
（72h 冷却）。gauntlet 过滤（每候选）：
1. n ≥ 30
2. 24h 超额 CI 下界 > 0（bootstrap，seed=2026）
3. 独立窗口一致性：2022-23 与 2024-26 两段超额同号
4. 尾部切除（去 top 5%）后 24h 均值仍 > 0
5. 成本覆盖：24h 毛利 > 54bps

输出：reports/operator_search.md（全候选表 + 通过 gauntlet 的幸存者）
用法：python scripts/153_operator_search.py
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

from harness.lib.event_study import bootstrap_ci  # noqa: E402

REPORT = PROJECT_ROOT / "reports" / "operator_search.md"
LO_MS = int(pd.Timestamp("2022-01-01", tz="UTC").timestamp() * 1000)
HI_MS = int(pd.Timestamp("2026-06-30", tz="UTC").timestamp() * 1000)
SPLIT_MS = int(pd.Timestamp("2024-01-01", tz="UTC").timestamp() * 1000)
MIN_EVENTS = 30
COOLDOWN_H = 72
COST_BPS = 54.0 / 100.0  # round-trip %


def build_features(sym: str) -> pd.DataFrame | None:
    """ctx + 全特征（无前视）。"""
    p = m113.COINGLASS_RAW1H / "klines" / f"{sym}.parquet"
    if not p.exists():
        return None
    df = pd.read_parquet(p)
    if not {"open_time", "close", "quote_volume"}.issubset(df.columns):
        return None
    ts = pd.to_numeric(df["open_time"], errors="coerce").to_numpy(dtype=np.int64)
    close = pd.to_numeric(df["close"], errors="coerce").to_numpy(dtype=float)
    qv = pd.to_numeric(df["quote_volume"], errors="coerce").to_numpy(dtype=float)
    tb = pd.to_numeric(df["taker_buy_quote_volume"], errors="coerce").to_numpy(dtype=float) \
        if "taker_buy_quote_volume" in df.columns else np.full(len(ts), np.nan)
    # 假 bar 清洗（113 同款）
    s = pd.Series(close)
    med = s.rolling(720, min_periods=360).median()
    ratio = s / med.replace(0, np.nan)
    close = np.where((ratio >= 0.02) & (ratio <= 50.0), close, np.nan)
    out = pd.DataFrame({"close": close}, index=pd.Index(ts))
    c = out["close"]
    out["ret_24h"] = c.pct_change(24) * 100.0
    z = (c - c.rolling(720, min_periods=360).mean()) / c.rolling(720, min_periods=360).std().replace(0, np.nan)
    out["price_z"] = z
    cvd = pd.Series(2 * tb - qv, index=pd.Index(ts)).sort_index()
    cvd_cum = cvd.groupby(cvd.index).last().sort_index().cumsum()
    cvd_z = (cvd_cum - cvd_cum.rolling(720, min_periods=360).mean()) / cvd_cum.rolling(720, min_periods=360).std().replace(0, np.nan)
    out["cvd_divergence"] = (z - cvd_z).to_numpy()
    # 放量
    qv_s = pd.Series(qv, index=pd.Index(ts)).sort_index()
    qv24 = qv_s.rolling(24).sum()
    qv24_med = qv24.rolling(720, min_periods=360).median()
    out["qv24_ratio"] = (qv24 / qv24_med.replace(0, np.nan)).to_numpy()
    # imbalance（151 口径）
    num = pd.Series(2 * tb - qv, index=pd.Index(ts)).sort_index().rolling(24).sum()
    den = qv_s.rolling(24).sum()
    imb = (num / den.replace(0, np.nan)).replace([np.inf, -np.inf], np.nan)
    lo = imb.rolling(720, min_periods=360).min()
    hi = imb.rolling(720, min_periods=360).max()
    out["imb_norm"] = ((imb - lo) / (hi - lo).replace(0, np.nan)).to_numpy()
    # funding（146 口径）
    f = m113.load_funding_series([sym]).get(sym)
    if f is not None and len(f):
        f2 = f[f.index >= LO_MS]
        flo = f2.rolling(90, min_periods=45).min()
        fhi = f2.rolling(90, min_periods=45).max()
        fnorm = ((f2 - flo) / (fhi - flo).replace(0, np.nan)).reindex(out.index, method="ffill")
        out["funding_norm"] = fnorm.to_numpy()
    # liq_short_z（131 口径，2024-06+）
    lp = m113.COINGLASS_RAW1H / "liquidation" / f"{sym}.parquet"
    if lp.exists():
        ld = pd.read_parquet(lp)
        if {"time", "short_liquidation_usd"}.issubset(ld.columns):
            lts = pd.to_numeric(ld["time"], errors="coerce").to_numpy(dtype=np.int64)
            lsh = pd.to_numeric(ld["short_liquidation_usd"], errors="coerce").to_numpy(dtype=float)
            lser = pd.Series(lsh, index=pd.Index(lts))
            lser = lser[~lser.index.duplicated(keep="last")].sort_index().reindex(out.index)
            short24 = lser.rolling(24).sum()
            out["liq_short_z"] = m113.rolling_z(short24, 720).to_numpy()
    # OI
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


def detect(feat: np.ndarray, axis: np.ndarray, cond: np.ndarray) -> list[int]:
    cd = COOLDOWN_H * 3_600_000
    ev: list[int] = []
    last = -10**18
    for i in np.flatnonzero(cond):
        t = int(axis[i])
        if t - last >= cd:
            ev.append(t)
            last = t
    return ev


def main() -> int:
    symbols = m113.load_universe_symbols()
    ctxs = {s: build_features(s) for s in symbols}
    ctxs = {s: c for s, c in ctxs.items() if c is not None and len(c) > 800}
    print(f"特征 ctx {len(ctxs)}")

    FEATS = ["ret_24h", "price_z", "cvd_divergence", "qv24_ratio",
             "funding_norm", "imb_norm", "liq_short_z", "oi_24h_chg"]
    candidates: list[dict] = []
    for sym, ctx in ctxs.items():
        axis = ctx.index.to_numpy(dtype=np.int64)
        close = ctx["close"].to_numpy(dtype=float)
        for fname in FEATS:
            if fname not in ctx.columns:
                continue
            v = ctx[fname].to_numpy(dtype=float)
            valid = np.isfinite(v)
            if valid.sum() < 720:
                continue
            q85 = np.nanquantile(v[valid], 0.85)
            q15 = np.nanquantile(v[valid], 0.15)
            for direction, cond in [("high", valid & (v > q85)), ("low", valid & (v < q15))]:
                ev = detect(v, axis, cond)
                for t in ev:
                    pos = int(np.searchsorted(axis, t, side="right")) - 1
                    if pos < 0 or pos + 168 >= len(close):
                        continue
                    r24 = (close[pos + 24] / close[pos] - 1) * 100.0
                    r168 = (close[pos + 168] / close[pos] - 1) * 100.0
                    if np.isfinite(r24) and np.isfinite(r168):
                        candidates.append({"sym": sym, "feat": fname, "dir": direction,
                                           "t": int(t), "r24": r24, "r168": r168})
    cdf = pd.DataFrame(candidates)
    print(f"候选事件 {len(cdf)}")

    rng = np.random.default_rng(2026)
    base = m113.__dict__.get("draw_random_events")
    from harness.lib.event_study import draw_random_events, DEFAULT_HORIZONS, forward_stats  # noqa: E402
    bbase = draw_random_events(ctxs, 3000, rng, max_forward_hours=168,
                               start_ms=LO_MS, end_ms=HI_MS)
    bparts = []
    for bs, bg in bbase.groupby("symbol", sort=False):
        if bs in ctxs:
            bparts.append(forward_stats(ctxs[bs], bg.copy(), DEFAULT_HORIZONS))
    bdf = pd.concat(bparts, ignore_index=True) if bparts else pd.DataFrame()
    br24 = pd.to_numeric(bdf["ret_24h"], errors="coerce").dropna().to_numpy()
    print(f"基线 n={len(br24)}")

    lines = ["# 算子搜索 MVP：单特征极值事件 gauntlet（153，路线 #3）\n",
             f"- 生成：{datetime.now(timezone.utc):%Y-%m-%d %H:%M UTC}",
             f"- 搜索：8 特征 × 高/低 × q85/q15 阈值 = 16 候选类；事件 72h 冷却，2022-01→2026-06",
             "- gauntlet：① n≥30 ② 24h 超额 CI 下界>0 ③ 独立窗口同号 ④ 尾部切除(去 top5%)仍正 ⑤ 毛利>54bps\n",
             "| 特征 | 方向 | n | 24h超额 | CI | 168h超额 | W1 | W2 | 尾切 | 净毛利 | 通过 |",
             "|---|---|---:|---:|---:|---:|---:|---:|---:|---:|---|"]

    survivors = []
    for (feat, direction), g in cdf.groupby(["feat", "dir"]):
        g = g[(g["t"] >= LO_MS) & (g["t"] <= HI_MS)]
        n = len(g)
        if n < MIN_EVENTS:
            lines.append(f"| {feat} | {direction} | {n} | - | - | - | - | - | - | - | n<30 |")
            continue
        r24 = g["r24"].to_numpy(dtype=float)
        r168 = g["r168"].to_numpy(dtype=float)
        ci = bootstrap_ci(r24, br24, n_boot=1000, alpha=0.05, seed=2026)
        w1 = r24[g["t"].to_numpy() < SPLIT_MS]
        w2 = r24[g["t"].to_numpy() >= SPLIT_MS]
        w1_ok = w1.mean() > 0 if len(w1) >= 10 else None
        w2_ok = w2.mean() > 0 if len(w2) >= 10 else None
        both_ok = (w1_ok is True) and (w2_ok is True)
        thr = np.quantile(r24, 0.95)
        tail_ok = r24[r24 <= thr].mean() > 0
        gross = r24.mean()
        net_ok = gross - COST_BPS > 0
        passed = ci["ci_lo"] > 0 and both_ok and tail_ok and net_ok
        if passed:
            survivors.append((feat, direction, n, ci["mean_diff"]))
        lines.append(f"| {feat} | {direction} | {n} | {ci['mean_diff']:+.2f}% "
                     f"| [{ci['ci_lo']:+.2f}, {ci['ci_hi']:+.2f}] | {r168.mean():+.2f}% "
                     f"| {w1.mean():+.2f}% | {w2.mean():+.2f}% | {r24[r24 <= thr].mean():+.2f}% "
                     f"| {gross - COST_BPS:+.2f}% | {'✅' if passed else '✗'} |")
        print(f"[153] {feat}/{direction}: n={n} ex24={ci['mean_diff']:+.2f}% "
              f"{'✅ 通过' if passed else '✗'}")

    lines.append("\n## 幸存者\n")
    if survivors:
        for s in survivors:
            lines.append(f"- **{s[0]}/{s[1]}**: n={s[2]}，24h 超额 {s[3]:+.2f}%")
    else:
        lines.append("- 无候选通过全部 5 门 gauntlet——单特征极值事件不构成独立 edge（与 146/151 一致）。")
    lines.extend(["\n## 解读\n",
                   "- 单特征极值（动量/量/资金流/持仓）独立事件：预期多数失败（历史 20+ 因子 HARD_FAIL 教训）。",
                   "- 若有幸存者 → 登记 alpha card 走独立复核；无幸存者 → 下一轮搜【组合算子】"
                   "（特征 AND/交互），或转向多特征 ML 拟合（黑盒第二阶段）。",
                   "- gauntlet 门 ③④ 是防过拟合核心：单窗口显著 + 尾部驱动的一律枪毙。"])
    REPORT.parent.mkdir(parents=True, exist_ok=True)
    REPORT.write_text("\n".join(lines) + "\n", encoding="utf-8")
    print(f"wrote {REPORT}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
