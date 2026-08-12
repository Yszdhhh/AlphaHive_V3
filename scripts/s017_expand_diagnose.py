r"""s017 — 扩日历后诊断（冻结 S1 pct=1%，不改选形态）。

重算 short_resid → 集中度 / leave-one-out / 簇化 / 稀疏 cliff。
用法：python scripts/s017_expand_diagnose.py
"""
from __future__ import annotations

import importlib.util
import sys
from datetime import datetime, timezone
from pathlib import Path

import numpy as np
import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

DERIVED = Path(r"G:\Quant test\derived_data\token_unlocks")
EVENTS_PQ = DERIVED / "sample_events.parquet"
OUT_MD = ROOT / "reports" / "s017_expand_diagnose.md"
OUT_CSV = DERIVED / "expanded_pct1_events.csv"

# 冻结：S1 胜出形态
PCT = 0.01
SEED = 20260812
N_BOOT = 600
DAY_MS = 86_400_000
COST_RT = 0.0027 * 2
CLUSTER_GAP_D = 7
SPARSE_MAX_PER_YEAR = 4
DENSE_SCHED = 100  # schedule rows


def _load_s0():
    spec = importlib.util.spec_from_file_location("s017s0", str(ROOT / "scripts" / "s017_s0_local.py"))
    m = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(m)
    return m


def boot_ci(x: np.ndarray) -> tuple[float, float]:
    x = np.asarray(x, float)
    x = x[np.isfinite(x)]
    if len(x) == 0:
        return float("nan"), float("nan")
    if len(x) == 1:
        return float(x[0]), float(x[0])
    rng = np.random.default_rng(SEED)
    boots = [float(np.mean(rng.choice(x, size=len(x), replace=True))) for _ in range(N_BOOT)]
    lo, hi = np.percentile(boots, [2.5, 97.5])
    return float(lo), float(hi)


def pack(name: str, df: pd.DataFrame) -> dict:
    if df is None or len(df) == 0:
        return {"name": name, "n": 0, "n_sym": 0, "mean": float("nan"), "med": float("nan"),
                "ci_lo": float("nan"), "ci_hi": float("nan"), "top": "", "top_w": float("nan"), "pos": float("nan")}
    sr = df["short_resid"].to_numpy(float)
    lo, hi = boot_ci(sr)
    vc = df["symbol"].value_counts()
    return {
        "name": name,
        "n": len(df),
        "n_sym": int(df["symbol"].nunique()),
        "mean": float(np.mean(sr)),
        "med": float(np.median(sr)),
        "ci_lo": lo,
        "ci_hi": hi,
        "top": str(vc.index[0]),
        "top_w": float(vc.iloc[0] / len(df)),
        "pos": float(np.mean(sr > 0)),
    }


def line(p: dict) -> str:
    if p["n"] == 0:
        return f"{p['name']}: empty"
    return (
        f"{p['name']}: n={p['n']} sym={p['n_sym']} mean={p['mean']*100:.2f}% "
        f"med={p['med']*100:.2f}% CI[{p['ci_lo']*100:.2f},{p['ci_hi']*100:.2f}] "
        f"top={p['top']}({p['top_w']*100:.1f}%) pos={p['pos']*100:.1f}%"
    )


def cluster_mean(df: pd.DataFrame) -> pd.DataFrame:
    """同一 symbol 间隔≤7d 并簇，簇收益=事件 mean。"""
    rows = []
    for sym, g in df.sort_values("unlock_ms").groupby("symbol"):
        g = g.reset_index(drop=True)
        cluster_id = 0
        last_ms = None
        idxs: list[list[int]] = [[]]
        for i, r in g.iterrows():
            t = int(r["unlock_ms"])
            if last_ms is not None and (t - last_ms) > CLUSTER_GAP_D * DAY_MS:
                cluster_id += 1
                idxs.append([])
            idxs[cluster_id].append(i)
            last_ms = t
        for cid, ix in enumerate(idxs):
            if not ix:
                continue
            sub = g.loc[ix]
            rows.append(
                {
                    "symbol": sym,
                    "cluster": cid,
                    "n_ev": len(sub),
                    "short_resid": float(sub["short_resid"].mean()),
                    "unlock_ms": int(sub["unlock_ms"].iloc[0]),
                }
            )
    return pd.DataFrame(rows)


def sparse_filter(df: pd.DataFrame) -> pd.DataFrame:
    """每币每年最多 SPARSE_MAX_PER_YEAR（按 short_resid abs 保留最大）。"""
    d = df.copy()
    d["year"] = pd.to_datetime(d["unlock_ms"], unit="ms", utc=True).dt.year
    d["abs_sr"] = d["short_resid"].abs()
    keep = []
    for (_, _), g in d.groupby(["symbol", "year"]):
        keep.append(g.nlargest(SPARSE_MAX_PER_YEAR, "abs_sr"))
    return pd.concat(keep, ignore_index=True) if keep else d.iloc[0:0]


def build_events(m, raw: pd.DataFrame) -> pd.DataFrame:
    btc = m.load_ohlcv("BTCUSDT")
    if btc is None:
        raise RuntimeError("no BTC")
    cand = raw[raw["pct_circ"].fillna(0) >= PCT].copy().sort_values(["symbol", "unlock_ms"])
    last_entry: dict[str, int] = {}
    rows = []
    for r in cand.itertuples(index=False):
        sym = r.symbol
        t0 = int(r.unlock_ms)
        t_entry = t0 - m.ENTRY_LEAD_D * DAY_MS
        prev = last_entry.get(sym)
        if prev is not None and (t_entry - prev) < m.COOLDOWN_D * DAY_MS:
            continue
        sdf = m.load_ohlcv(sym)
        if sdf is None:
            continue
        adv = m.adv_7d(sdf, t_entry)
        if not np.isfinite(adv) or adv < m.ADV_MIN:
            continue
        ret_s = m.window_return(sdf, t_entry, t0)
        ret_b = m.window_return(btc, t_entry, t0)
        beta = m.beta_30d(sdf, btc, t_entry)
        if not all(np.isfinite([ret_s, ret_b, beta])):
            continue
        resid = ret_s - beta * ret_b
        short_resid = -resid
        rows.append(
            {
                "symbol": sym,
                "unlock_ms": t0,
                "entry_ms": t_entry,
                "pct_circ": float(r.pct_circ),
                "adv_7d": adv,
                "beta": beta,
                "ret_sym": ret_s,
                "ret_btc": ret_b,
                "resid": resid,
                "short_resid": short_resid,
                "net_27bps_rt": short_resid - COST_RT,
                "alloc_keys": str(getattr(r, "alloc_keys", ""))[:120],
                "n_schedule_hint": getattr(r, "n_schedule", None),
            }
        )
        last_entry[sym] = t_entry
    return pd.DataFrame(rows)


def main() -> int:
    m = _load_s0()
    if not EVENTS_PQ.exists():
        print("missing sample_events; run s017_expand_calendar.py first")
        return 1
    raw = pd.read_parquet(EVENTS_PQ)
    # schedule density per symbol
    dens = raw.groupby("symbol").size().rename("n_schedule_rows")
    print(f"raw events={len(raw)} symbols={raw['symbol'].nunique()}")

    ev = build_events(m, raw)
    if len(ev) == 0:
        print("no qualified events")
        return 2
    ev = ev.merge(dens, left_on="symbol", right_index=True, how="left")
    ev.to_csv(OUT_CSV, index=False)
    print(f"qualified pct>={PCT} n={len(ev)} sym={ev['symbol'].nunique()}")

    full = pack("full_pct1", ev)
    # leave-one-out
    packs = [full]
    for sym in ev["symbol"].value_counts().head(5).index.tolist():
        packs.append(pack(f"leave_{sym}", ev[ev["symbol"] != sym]))
    top3 = ev["symbol"].value_counts().head(3).index.tolist()
    packs.append(pack("leave_top3", ev[~ev["symbol"].isin(top3)]))

    # cluster
    cl = cluster_mean(ev)
    packs.append(pack("clustered_7d", cl.rename(columns={"short_resid": "short_resid"})))

    # filters diagnostic
    packs.append(pack("drop_dense_sched", ev[ev["n_schedule_rows"].fillna(0) <= DENSE_SCHED]))
    packs.append(pack("sparse_cliff_4py", sparse_filter(ev)))

    # SEI share
    sei_w = float((ev["symbol"] == "SEIUSDT").mean()) if len(ev) else 0.0
    vc = ev["symbol"].value_counts()
    by_sym = (
        ev.groupby("symbol")["short_resid"]
        .agg(["count", "mean", "median"])
        .sort_values("count", ascending=False)
    )
    by_sym["weight"] = by_sym["count"] / by_sym["count"].sum()

    # verdict
    leave_sei = next((p for p in packs if p["name"] == "leave_SEIUSDT"), None)
    leave_t3 = next((p for p in packs if p["name"] == "leave_top3"), None)
    if full["top_w"] >= 0.5:
        if leave_sei and leave_sei["n"] >= 30 and leave_sei["ci_lo"] > 0:
            verdict = "IMPROVED_BUT_STILL_MIXED"
        elif leave_sei and leave_sei["n"] >= 20 and leave_sei["mean"] > 0:
            verdict = "MIXED_NEED_MORE_CALENDAR"
        else:
            verdict = "SINGLE_NAME_DOMINATED"
    elif full["n_sym"] >= 15 and leave_t3 and leave_t3["ci_lo"] > 0 and full["ci_lo"] > 0:
        verdict = "STRUCTURAL_MULTI"
    elif full["ci_lo"] > 0 and leave_sei and leave_sei.get("ci_lo", -1) > 0:
        verdict = "IMPROVED_BUT_STILL_MIXED"
    else:
        verdict = "MIXED_NEED_MORE_CALENDAR"

    now = datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M UTC")
    md = f"""# s017 扩日历后诊断（冻结 pct=1%）

- date: {now}
- script: `scripts/s017_expand_diagnose.py`
- calendar: `{EVENTS_PQ}`
- **冻结形态**: pct_circ ≥ **{PCT*100:.0f}%**（S1 胜出，**未重选**）
- 过滤: ADV≥$2M · 冷却 7d · 空残差同 S0
- **描述性 / exploratory；不宣布 GO；不改 S1 选形态**

## 结论

| 项 | 值 |
|---|---|
| 合格事件 n | {full['n']} |
| 覆盖币 | {full['n_sym']} |
| mean / median short | {full['mean']*100:.2f}% / {full['med']*100:.2f}% |
| bootstrap CI | [{full['ci_lo']*100:.2f}%, {full['ci_hi']*100:.2f}%] |
| top 币权重 | {full['top']} **{full['top_w']*100:.1f}%** |
| SEI 占比 | {sei_w*100:.1f}% |
| **Verdict** | **{verdict}** |

### 分层

{chr(10).join('- ' + line(p) for p in packs)}

### 分币（top 15）

```
{by_sym.head(15).to_string()}
```

### 簇化摘要

- 事件→簇: {len(ev)} → {len(cl)}
- SEI 事件/簇: {int((ev.symbol=='SEIUSDT').sum())} / {int((cl.symbol=='SEIUSDT').sum()) if len(cl) else 0}

## 解读

- `STRUCTURAL_MULTI`: 多币、leave-top3 CI>0 → 可考虑预注册稀疏 cliff 再 holdout  
- `IMPROVED_BUT_STILL_MIXED`: 有改善但仍集中或 leave 边界  
- `MIXED_NEED_MORE_CALENDAR`: 方向在但分散不够  
- `SINGLE_NAME_DOMINATED`: 单币主导  

## 产出

- `{OUT_CSV}`
- 本报告

## 禁区

- 未重跑 S1 选 pct  
- 未宣称 historical_pass  
"""
    OUT_MD.write_text(md, encoding="utf-8")
    print(md)
    print(f"Wrote {OUT_MD} verdict={verdict}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
