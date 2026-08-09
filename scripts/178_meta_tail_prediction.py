r"""178_meta_tail_prediction.py — 负尾部预测实验（177 的目标错配修正）。

177 认知：胜率分类（P(r168>0)）无法转均值超额（右偏分布）。本实验换目标：
**预测深亏事件（r168 < -10%，占 23.1%）→ 过滤掉高 P(深亏) 事件 → 保留事件均值提升**。

- 标签：y = 1[r168 < -10%]
- 特征：同 177（9 个：price_z/ret_24h/cvd_div/r4/days_since_listing/mayer/cycle_z/liq24_log/np_z）
- purged k-fold（k=5，purge/embargo 168h，177 实现）
- 过滤：P(深亏) > T 的事件剔除；保留组均值超额 vs 全事件
- 判定：保留组 168h 超额增量 ≥ +1.0pp 且 bootstrap CI 下界 > 0；与 V_confirm 叠加对照

输出：reports/external_intel/meta_tail_prediction.md
用法：python scripts/178_meta_tail_prediction.py
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
_spec2 = importlib.util.spec_from_file_location(
    "m115", str(PROJECT_ROOT / "scripts" / "115_short_squeeze_combo_study.py"))
m115 = importlib.util.module_from_spec(_spec2)
sys.modules["m115"] = m115
_spec2.loader.exec_module(m115)

from harness.lib.event_study import DEFAULT_HORIZONS, forward_stats  # noqa: E402

REPORT = PROJECT_ROOT / "reports" / "external_intel" / "meta_tail_prediction.md"
LO_MS = int(pd.Timestamp("2022-01-01", tz="UTC").timestamp() * 1000)
HI_MS = int(pd.Timestamp("2026-06-30", tz="UTC").timestamp() * 1000)
TAIL_THR = -10.0
T_SCAN = [0.20, 0.25, 0.30, 0.35, 0.40]
N_FOLDS = 5
LABEL_H = 168


def btc_cycle() -> pd.DataFrame:
    closes: dict = {}
    for root in [m113.COINGLASS_RAW1H / "klines",
                 Path(r"C:\Users\10639\Desktop\加密\binance_free_db\raw_1h\klines")]:
        p = root / "BTCUSDT.parquet"
        if not p.exists():
            continue
        try:
            kl = pd.read_parquet(p, columns=["open_time", "close"])
        except Exception:
            continue
        ts = pd.to_numeric(kl["open_time"], errors="coerce").to_numpy(dtype=np.int64)
        cl = pd.to_numeric(kl["close"], errors="coerce").to_numpy(dtype=float)
        day = pd.to_datetime(ts, unit="ms", utc=True).tz_localize(None).normalize()
        for d, c in zip(day, cl):
            if np.isfinite(c):
                closes[d] = c
    daily = pd.Series(closes).sort_index()
    ma200 = daily.rolling(200, min_periods=120).mean()
    mayer = daily / ma200.replace(0, np.nan)
    logp = np.log(daily)
    x = np.arange(len(daily))
    A = np.vstack([x, np.ones(len(x))]).T
    beta, _, _, _ = np.linalg.lstsq(A, logp.to_numpy(), rcond=None)
    resid = logp.to_numpy() - (beta[0] * x + beta[1])
    return pd.DataFrame({"mayer": mayer, "cycle_z": resid / np.std(resid)},
                        index=daily.index).dropna()


def main() -> int:
    symbols = m113.load_universe_symbols()
    ctxs = m113.load_price_ctx(symbols)
    fundings = m113.load_funding_series(symbols)

    ev_parts = []
    for sym, ctx in ctxs.items():
        ev = m115.detect_events(sym, ctx, fundings.get(sym), "wash_cvd")
        if not ev.empty:
            ev_parts.append(ev)
    events = pd.concat(ev_parts, ignore_index=True) if ev_parts else pd.DataFrame(
        columns=["symbol", "timestamp"])
    events = events[(events["timestamp"] >= LO_MS) & (events["timestamp"] <= HI_MS)].copy()
    fwd_parts = []
    for sym, g in events.groupby("symbol", sort=False):
        if sym in ctxs:
            fwd_parts.append(forward_stats(ctxs[sym], g.copy(), DEFAULT_HORIZONS))
    events = pd.concat(fwd_parts, ignore_index=True) if fwd_parts else events

    # 特征（177 同款）
    for sym, g in events.groupby("symbol", sort=False):
        ctx = ctxs[sym]
        axis = ctx.index.to_numpy(dtype=np.int64)
        pos = np.searchsorted(axis, g["timestamp"].to_numpy(dtype=np.int64), side="right") - 1
        pos = np.clip(pos, 0, len(axis) - 1)
        for col in ["price_z", "ret_24h", "cvd_divergence"]:
            if col in ctx.columns:
                vals = pd.to_numeric(ctx[col], errors="coerce").to_numpy(dtype=float)
                events.loc[g.index, col] = vals[pos]
        close = ctx["close"].to_numpy(dtype=float)
        r4 = np.full(len(g), np.nan)
        for i, (_, r) in enumerate(g.iterrows()):
            p0 = pos[i]
            if p0 >= 0 and p0 + 4 < len(close) and np.isfinite(close[p0]) and np.isfinite(close[p0 + 4]):
                r4[i] = (close[p0 + 4] / close[p0] - 1) * 100
        events.loc[g.index, "r4"] = r4
        p = m113.COINGLASS_RAW1H / "klines" / f"{sym}.parquet"
        try:
            kdf = pd.read_parquet(p, columns=["open_time", "quote_volume"])
            kts = pd.to_numeric(kdf["open_time"], errors="coerce").to_numpy(dtype=np.int64)
            kqv = pd.to_numeric(kdf["quote_volume"], errors="coerce").to_numpy(dtype=float)
            qs = pd.Series(kqv, index=pd.Index(kts))
            qs = qs[~qs.index.duplicated(keep="last")].sort_index().reindex(ctx.index)
            liq24 = qs.rolling(24).sum().to_numpy(dtype=float)
            events.loc[g.index, "liq24_log"] = np.log(liq24[pos])
        except Exception:
            events.loc[g.index, "liq24_log"] = np.nan
        np_p = m113.COINGLASS_RAW1H / "net_position" / f"{sym}.parquet"
        if np_p.exists():
            try:
                n = pd.read_parquet(np_p)
                nts = pd.to_numeric(n["time"], errors="coerce").to_numpy(dtype=np.int64)
                nv = pd.to_numeric(n["net_position_change_cum"], errors="coerce").to_numpy(dtype=float)
                ns = pd.Series(nv, index=pd.Index(nts))
                ns = ns[~ns.index.duplicated(keep="last")].sort_index().reindex(ctx.index)
                nz = m113.rolling_z(ns, 720).to_numpy(dtype=float)
                events.loc[g.index, "np_z"] = nz[pos]
            except Exception:
                events.loc[g.index, "np_z"] = np.nan
    listed = {}
    for sym in m113.load_universe_symbols():
        pp = m113.COINGLASS_RAW1H / "klines" / f"{sym}.parquet"
        if pp.exists():
            try:
                listed[sym] = int(pd.read_parquet(pp, columns=["open_time"])["open_time"].min())
            except Exception:
                pass
    events["days_since_listing"] = ((events["timestamp"] - events["symbol"].map(listed))
                                    / (24 * 3_600_000)).clip(lower=0)
    cycle = btc_cycle()
    ev_day = pd.to_datetime(events["timestamp"].to_numpy(), unit="ms", utc=True).tz_localize(None).normalize()
    events["mayer"] = ev_day.map(cycle["mayer"]).to_numpy()
    events["cycle_z"] = ev_day.map(cycle["cycle_z"]).to_numpy()

    r168 = pd.to_numeric(events["ret_168h"], errors="coerce")
    events["y_tail"] = (r168 < TAIL_THR).astype(float)
    events["r4_pos"] = (pd.to_numeric(events["r4"], errors="coerce") > 0).astype(float)
    usable = events[events["y_tail"].notna()].copy()
    print(f"事件 {len(events)} | 深亏率 {usable['y_tail'].mean():.1%}（r168<{TAIL_THR}%）")

    FEATS = ["price_z", "ret_24h", "cvd_divergence", "r4", "days_since_listing",
             "mayer", "cycle_z", "liq24_log", "np_z"]
    X = usable[FEATS].apply(pd.to_numeric, errors="coerce").fillna(usable[FEATS].median())
    y = usable["y_tail"].to_numpy(dtype=float)
    ts = usable["timestamp"].to_numpy(dtype=np.int64)

    from sklearn.linear_model import LogisticRegression
    from sklearn.ensemble import HistGradientBoostingClassifier
    from sklearn.metrics import roc_auc_score

    order = np.argsort(ts)
    Xs, ys, tss = X.to_numpy()[order], y[order], ts[order]
    n = len(Xs)
    oof_prob = np.full(n, np.nan)
    n_trials = 0
    for test_idx in np.array_split(np.arange(n), N_FOLDS):
        t0, t1 = tss[test_idx[0]], tss[test_idx[-1]]
        keep = np.ones(n, dtype=bool)
        keep[test_idx] = False
        overlap = (tss < t1) & (tss + LABEL_H * 3_600_000 > t0)
        embargo = (tss >= t1) & (tss <= t1 + LABEL_H * 3_600_000)
        keep &= ~overlap & ~embargo
        tr_idx = np.flatnonzero(keep)
        if len(tr_idx) < 100:
            continue
        models = [
            LogisticRegression(penalty="l1", solver="saga", C=0.1, max_iter=3000),
            HistGradientBoostingClassifier(max_depth=3, max_iter=80, learning_rate=0.05,
                                           min_samples_leaf=30),
        ]
        probs = np.zeros(len(test_idx))
        for model in models:
            model.fit(Xs[tr_idx], ys[tr_idx])
            probs += model.predict_proba(Xs[test_idx])[:, 1]
            n_trials += 1
        oof_prob[test_idx] = probs / len(models)
    valid = np.isfinite(oof_prob)
    auc = roc_auc_score(ys[valid], oof_prob[valid])
    print(f"OOF AUC（预测深亏）= {auc:.3f}（trials={n_trials}）")

    base_r = pd.to_numeric(usable["ret_168h"], errors="coerce").to_numpy(dtype=float)
    rng = np.random.default_rng(2026)
    lines = ["# 负尾部预测实验（178，177 目标错配修正）\n",
             f"- 生成：{datetime.now(timezone.utc):%Y-%m-%d %H:%M UTC}",
             f"- 目标：预测深亏（r168<{TAIL_THR}%，占 {usable['y_tail'].mean():.1%}）→ 过滤",
             f"- **OOF AUC = {auc:.3f}**（9 特征，logistic+GBM 平均，purged CV，trials={n_trials}）\n",
             "| 过滤 P(深亏)>T | 保留 n | 保留率 | 保留组均值 | 超额vs全事件 | CI | 判定 |",
             "|---|---:|---:|---:|---:|---:|---|"]
    best = None
    for T in T_SCAN:
        sel = valid & (oof_prob <= T)
        if sel.sum() < 30:
            lines.append(f"| {T:.2f} | {int(sel.sum())} | - | - | - | - | 样本不足 |")
            continue
        r = base_r[sel]
        ex = r.mean() - base_r.mean()
        boot = []
        for _ in range(500):
            s = rng.choice(r, size=len(r), replace=True)
            boot.append(s.mean() - base_r.mean())
        ci_lo, ci_hi = np.percentile(boot, [2.5, 97.5])
        ok = ex >= 1.0 and ci_lo > 0
        lines.append(f"| {T:.2f} | {int(sel.sum())} | {sel.mean():.0%} | {r.mean():+.2f}% "
                     f"| {ex:+.2f}% | [{ci_lo:+.2f}, {ci_hi:+.2f}] | {'✅' if ok else '✗'} |")
        if ok and (best is None or ex > best[1]):
            best = (T, ex)
        print(f"[178] T={T:.2f}: 保留 {int(sel.sum())} 均值 {r.mean():+.2f}% 超额 {ex:+.2f}% CI[{ci_lo:+.2f},{ci_hi:+.2f}]")

    lines.append("\n## 判定\n")
    if best:
        lines.append(f"**GO（T={best[0]:.2f}，增量 {best[1]:+.2f}pp）**：负尾部过滤有效，可叠到 4h 确认之上。")
    else:
        lines.append("**NO_GO**：深亏不可预测或过滤无均值增益——负尾部是噪声而非特征可捕捉结构。")
    lines.append(f"\n*对照：全事件均值 {base_r.mean():+.2f}%；V_confirm +3.56%（148）；"
                 f"深亏率 {usable['y_tail'].mean():.1%}*")
    REPORT.parent.mkdir(parents=True, exist_ok=True)
    REPORT.write_text("\n".join(lines) + "\n", encoding="utf-8")
    print(f"wrote {REPORT}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
