r"""177_meta_labeling_firstpass.py — meta-labeling 半天诊断实验（AFML 深拆方案 §5）。

目标：回答两个问题
(1) 多特征联合的 purged OOF AUC 是否显著 > 0.55？
(2) meta 过滤后 168h 超额是否 ≥ V_confirm 基线 +3.56% + 1.0pp？

方法（meta_labeling_plan.md §3，缺口边做边补）：
- 样本：wash_cvd 全事件（115，72h 冷却，2022-01→2026-06）n=1348
- 标签：y = r168 − 54bps > 0（垂直障碍，成本后）
- 特征（现有列 asof）：price_z / ret_24h / cvd_divergence / r4 / days_since_listing /
  log(liq24) / np_z / mayer / cycle_z（NaN 填中位数，标注）
- purged k-fold（k=5，时间有序；purge=标签窗重叠 168h，embargo=168h）
- L1 logistic（saga）+ HistGBM（depth≤3）→ OOF AUC + 校准
- T 扫描 {0.5..0.75} 仅在 OOF，bootstrap CI，trials 记账
- 判定：AUC>0.55 且 增量≥+1.0pp（CI 下界>0）→ GO；否则 NO_GO

输出：reports/external_intel/meta_labeling_firstpass.md
用法：python scripts/177_meta_labeling_firstpass.py
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

REPORT = PROJECT_ROOT / "reports" / "external_intel" / "meta_labeling_firstpass.md"
LO_MS = int(pd.Timestamp("2022-01-01", tz="UTC").timestamp() * 1000)
HI_MS = int(pd.Timestamp("2026-06-30", tz="UTC").timestamp() * 1000)
COST = 0.0054
T_SCAN = [0.50, 0.55, 0.60, 0.65, 0.70, 0.75]
N_FOLDS = 5
LABEL_H = 168


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


def btc_cycle() -> pd.DataFrame:
    """BTC 日线 → mayer（rolling 200d）+ cycle_z（全期对数回归残差 z）。"""
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
    cyc = resid / np.std(resid)
    return pd.DataFrame({"mayer": mayer, "cycle_z": cyc}, index=daily.index).dropna()


def main() -> int:
    # ---------- 宽表 ----------
    symbols = m113.load_universe_symbols()
    ctxs = m113.load_price_ctx(symbols)
    fundings = m113.load_funding_series(symbols)
    listed = listing_dates()

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

    # 特征 asof 拼接
    for sym, g in events.groupby("symbol", sort=False):
        ctx = ctxs[sym]
        axis = ctx.index.to_numpy(dtype=np.int64)
        pos = np.searchsorted(axis, g["timestamp"].to_numpy(dtype=np.int64), side="right") - 1
        pos = np.clip(pos, 0, len(axis) - 1)
        for col in ["price_z", "ret_24h", "cvd_divergence"]:
            if col in ctx.columns:
                vals = pd.to_numeric(ctx[col], errors="coerce").to_numpy(dtype=float)
                events.loc[g.index, col] = vals[pos]
        # r4（事件后 4h 收益，主口径作特征）
        close = ctx["close"].to_numpy(dtype=float)
        r4 = np.full(len(g), np.nan)
        for i, (_, r) in enumerate(g.iterrows()):
            p0 = pos[i]
            if p0 >= 0 and p0 + 4 < len(close) and np.isfinite(close[p0]) and np.isfinite(close[p0 + 4]):
                r4[i] = (close[p0 + 4] / close[p0] - 1) * 100
        events.loc[g.index, "r4"] = r4

    events["days_since_listing"] = (events["timestamp"] - events["symbol"].map(listed)) / (24 * 3_600_000)
    events["days_since_listing"] = events["days_since_listing"].clip(lower=0)

    # BTC 周期特征（mayer/cycle_z）
    cycle = btc_cycle()
    ev_day = pd.to_datetime(events["timestamp"].to_numpy(), unit="ms", utc=True).tz_localize(None).normalize()
    events["mayer"] = ev_day.map(cycle["mayer"]).to_numpy()
    events["cycle_z"] = ev_day.map(cycle["cycle_z"]).to_numpy()

    # 标签
    events["y"] = (pd.to_numeric(events["ret_168h"], errors="coerce") / 100.0 - COST > 0).astype(float)
    usable = events[events["y"].notna()].copy()
    print(f"事件 {len(events)} | 有标签 {len(usable)} | 正类率 {usable['y'].mean():.1%}")

    FEATS = ["price_z", "ret_24h", "cvd_divergence", "r4", "days_since_listing",
             "mayer", "cycle_z", "liq24_log", "np_z"]
    # liq24（事件时点 24h 成交额对数）+ np_z（净持仓背离）
    for sym, g in events.groupby("symbol", sort=False):
        ctx = ctxs[sym]
        axis = ctx.index.to_numpy(dtype=np.int64)
        pos = np.searchsorted(axis, g["timestamp"].to_numpy(dtype=np.int64), side="right") - 1
        pos = np.clip(pos, 0, len(axis) - 1)
        # liq24 从 klines quote_volume
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
        # np_z（161 口径）
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
    X = events[FEATS].apply(pd.to_numeric, errors="coerce")
    med = X.median()
    X = X.fillna(med)
    y = usable["y"].to_numpy(dtype=float)
    ts = usable["timestamp"].to_numpy(dtype=np.int64)

    from sklearn.linear_model import LogisticRegression
    from sklearn.ensemble import HistGradientBoostingClassifier
    from sklearn.metrics import roc_auc_score

    # ---------- purged k-fold ----------
    order = np.argsort(ts)
    Xs, ys, tss = X.to_numpy()[order], y[order], ts[order]
    n = len(Xs)
    fold_bounds = np.array_split(np.arange(n), N_FOLDS)
    oof_prob = np.full(n, np.nan)
    n_trials = 0
    for fold_i, test_idx in enumerate(fold_bounds):
        t0, t1 = tss[test_idx[0]], tss[test_idx[-1]]
        # purge：训练事件标签窗 [ts, ts+168h] 与测试块 [t0, t1] 重叠 → 剔除
        # embargo：测试块后 168h 内
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
    print(f"OOF AUC = {auc:.3f}（n={valid.sum()}，trials={n_trials}）")

    # ---------- T 扫描（OOF） ----------
    br168 = pd.to_numeric(
        pd.to_numeric(events["ret_168h"], errors="coerce").median(), errors="coerce")
    base_r = pd.to_numeric(usable["ret_168h"], errors="coerce").to_numpy(dtype=float)
    lines = ["# meta-labeling 诊断实验（177）\n",
             f"- 生成：{datetime.now(timezone.utc):%Y-%m-%d %H:%M UTC}",
             f"- 样本：wash_cvd {len(usable)}（有标签）；正类率 {usable['y'].mean():.1%}",
             f"- 特征：{FEATS}（asof，NaN 填中位数）",
             f"- purged k-fold（k={N_FOLDS}，purge/embargo 168h）；L1 logistic（saga C=0.1）",
             f"- **OOF AUC = {auc:.3f}**（trials={n_trials}）\n",
             "| T | 通过 n | 通过率 | 168h 均值 | 超额vs全事件 | bootstrap CI | 判定 |",
             "|---|---:|---:|---:|---:|---:|---|"]

    rng = np.random.default_rng(2026)
    best = None
    for T in T_SCAN:
        sel = valid & (oof_prob >= T)
        if sel.sum() < 30:
            lines.append(f"| {T:.2f} | {int(sel.sum())} | - | - | - | - | 样本不足 |")
            continue
        r = base_r[sel]
        ex = r.mean() - base_r.mean()
        # bootstrap CI（vs 全事件均值）
        boot = []
        for _ in range(500):
            s = rng.choice(r, size=len(r), replace=True)
            boot.append(s.mean() - base_r.mean())
        ci_lo, ci_hi = np.percentile(boot, [2.5, 97.5])
        verdict = "✅" if ex >= 1.0 and ci_lo > 0 else "✗"
        lines.append(f"| {T:.2f} | {int(sel.sum())} | {sel.mean():.0%} | {r.mean():+.2f}% "
                     f"| {ex:+.2f}% | [{ci_lo:+.2f}, {ci_hi:+.2f}] | {verdict} |")
        if ex >= 1.0 and ci_lo > 0 and (best is None or ex > best[1]):
            best = (T, ex)
        print(f"[177] T={T:.2f}: n={int(sel.sum())} 超额 {ex:+.2f}% CI[{ci_lo:+.2f},{ci_hi:+.2f}]")

    # ---------- 判定 ----------
    lines.append("\n## 判定\n")
    if auc <= 0.55:
        lines.append("**NO_GO（AUC ≤ 0.55）**：多特征联合无区分度——规则层已捕获可用信息，关闭。")
    elif best is None:
        lines.append("**NO_GO（无 T 满足增量 ≥ +1.0pp 且 CI 下界 > 0）**：规则基线已到天花板。")
    else:
        lines.append(f"**GO（T={best[0]:.2f}，增量 {best[1]:+.2f}pp）**：预注册正式 ML alpha card（账户 E）。")
    lines.append(f"\n*对照基线：V_confirm +3.56%（148）；全事件均值 {base_r.mean():+.2f}%*")
    REPORT.parent.mkdir(parents=True, exist_ok=True)
    REPORT.write_text("\n".join(lines) + "\n", encoding="utf-8")
    print(f"wrote {REPORT}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
