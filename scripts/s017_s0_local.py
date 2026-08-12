r"""s017 S0 本地沙盒 — Token Unlock 残差空（描述性，不宣布 GO）。

规格对齐 alpha_card：
  入场 T0-14d 后第一根完整 1h open；持有到 T0；残差 vs BTC；
  过滤 pct_circ≥0.5%、ADV≥$2M、冷却 7d。
数据：derived_data unlock sample + coinglass 1h klines。
输出：reports/s017_s0_local.md + derived_data/token_unlocks/s0_events.csv
用法：python scripts/s017_s0_local.py
"""
from __future__ import annotations

import sys
from datetime import datetime, timezone
from pathlib import Path

import numpy as np
import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

KLINES = Path(r"C:\Users\10639\Desktop\🔒 加密资产\coinglass_db\raw_1h\klines")
DERIVED = Path(r"G:\Quant test\derived_data\token_unlocks")
EVENTS_PQ = DERIVED / "sample_events.parquet"
OUT_MD = ROOT / "reports" / "s017_s0_local.md"
OUT_CSV = DERIVED / "s0_events.csv"

DAY_MS = 86_400_000
HOUR_MS = 3_600_000
ENTRY_LEAD_D = 14
BETA_LOOKBACK_D = 30
ADV_DAYS = 7
ADV_MIN = 2_000_000.0
PCT_MIN = 0.005
COOLDOWN_D = 7
COST_RT = 0.0027 * 2  # 27bps 单边 ×2
SEED = 20260812
SPLIT_MS = int(pd.Timestamp("2024-01-01", tz="UTC").timestamp() * 1000)


def load_ohlcv(sym: str) -> pd.DataFrame | None:
    p = KLINES / f"{sym}.parquet"
    if not p.exists():
        return None
    df = pd.read_parquet(p, columns=["open_time", "open", "close", "quote_volume"])
    df = df.rename(columns={"open_time": "ts"})
    df["ts"] = pd.to_numeric(df["ts"], errors="coerce").astype("int64")
    for c in ("open", "close", "quote_volume"):
        df[c] = pd.to_numeric(df[c], errors="coerce")
    return df.dropna(subset=["ts", "open", "close"]).sort_values("ts").reset_index(drop=True)


def asof_row(df: pd.DataFrame, t: int) -> int | None:
    """index of last bar with ts <= t; None if none."""
    ts = df["ts"].to_numpy()
    i = int(np.searchsorted(ts, t, side="right") - 1)
    if i < 0:
        return None
    return i


def window_return(df: pd.DataFrame, t0: int, t1: int) -> float:
    """open at first bar after t0 → close of last bar <= t1."""
    ts = df["ts"].to_numpy()
    i0 = int(np.searchsorted(ts, t0, side="right"))  # first bar after t0 (完整 bar open)
    if i0 >= len(ts):
        return float("nan")
    i1 = int(np.searchsorted(ts, t1, side="right") - 1)
    if i1 < i0:
        return float("nan")
    o = float(df["open"].iloc[i0])
    c = float(df["close"].iloc[i1])
    if not np.isfinite(o) or o <= 0 or not np.isfinite(c):
        return float("nan")
    return c / o - 1.0


def adv_7d(df: pd.DataFrame, t_entry: int) -> float:
    """mean daily quote volume over 7d ending at entry (no look-ahead into hold)."""
    lo = t_entry - ADV_DAYS * DAY_MS
    m = (df["ts"] > lo) & (df["ts"] <= t_entry)
    sub = df.loc[m, "quote_volume"]
    if len(sub) < 24:
        return float("nan")
    # hourly sum → daily mean
    return float(sub.sum() / ADV_DAYS)


def beta_30d(sym_df: pd.DataFrame, btc: pd.DataFrame, t_entry: int) -> float:
    """OLS beta of daily rets over 30d before entry; clip [0, 1.5]."""
    lo = t_entry - BETA_LOOKBACK_D * DAY_MS
    # daily close asof each day end
    days = np.arange(lo + DAY_MS, t_entry + 1, DAY_MS)
    if len(days) < 10:
        return float("nan")
    s_rets, b_rets = [], []
    prev_s, prev_b = None, None
    for d in days:
        is_ = asof_row(sym_df, int(d))
        ib = asof_row(btc, int(d))
        if is_ is None or ib is None:
            continue
        cs = float(sym_df["close"].iloc[is_])
        cb = float(btc["close"].iloc[ib])
        if prev_s is not None and prev_s > 0 and prev_b is not None and prev_b > 0:
            s_rets.append(cs / prev_s - 1.0)
            b_rets.append(cb / prev_b - 1.0)
        prev_s, prev_b = cs, cb
    if len(s_rets) < 8:
        return float("nan")
    s = np.asarray(s_rets, float)
    b = np.asarray(b_rets, float)
    varb = float(np.var(b))
    if varb < 1e-18:
        return float("nan")
    beta = float(np.cov(s, b, ddof=0)[0, 1] / varb)
    return float(np.clip(beta, 0.0, 1.5))


def team_investor_flag(alloc: str) -> bool:
    a = (alloc or "").lower()
    keys = ("team", "investor", "seed", "private", "vc", "advisor", "foundation")
    return any(k in a for k in keys)


def main() -> int:
    if not EVENTS_PQ.exists():
        print(f"missing {EVENTS_PQ}; run s017_unlock_data_audit first")
        return 1
    raw = pd.read_parquet(EVENTS_PQ)
    btc = load_ohlcv("BTCUSDT")
    if btc is None:
        print("missing BTCUSDT klines")
        return 1

    # 主规格：pct>=0.5%；次：全量过 ADV 的对照
    cand = raw[raw["pct_circ"].fillna(0) >= PCT_MIN].copy()
    cand = cand.sort_values(["symbol", "unlock_ms"])
    rows = []
    last_entry: dict[str, int] = {}

    for r in cand.itertuples(index=False):
        sym = r.symbol
        t0 = int(r.unlock_ms)
        # normalize unlock to UTC day start if needed — keep as given
        t_entry = t0 - ENTRY_LEAD_D * DAY_MS
        # cooldown on entry
        prev = last_entry.get(sym)
        if prev is not None and (t_entry - prev) < COOLDOWN_D * DAY_MS:
            continue
        sdf = load_ohlcv(sym)
        if sdf is None:
            continue
        adv = adv_7d(sdf, t_entry)
        if not np.isfinite(adv) or adv < ADV_MIN:
            continue
        ret_s = window_return(sdf, t_entry, t0)
        ret_b = window_return(btc, t_entry, t0)
        beta = beta_30d(sdf, btc, t_entry)
        if not np.isfinite(ret_s) or not np.isfinite(ret_b) or not np.isfinite(beta):
            continue
        resid = ret_s - beta * ret_b
        # short residual pnl (positive if residual drops)
        short_resid = -resid
        net = short_resid - COST_RT
        ti = team_investor_flag(str(getattr(r, "alloc_keys", "")))
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
                "net_27bps_rt": net,
                "team_investor": ti,
                "alloc_keys": str(getattr(r, "alloc_keys", ""))[:120],
            }
        )
        last_entry[sym] = t_entry

    ev = pd.DataFrame(rows)
    if len(ev) == 0:
        OUT_MD.write_text("# s017 S0\n\n无合格事件\n", encoding="utf-8")
        print("no events")
        return 2

    ev["unlock_utc"] = pd.to_datetime(ev["unlock_ms"], unit="ms", utc=True)
    DERIVED.mkdir(parents=True, exist_ok=True)
    ev.to_csv(OUT_CSV, index=False)

    def pack(name: str, x: pd.DataFrame) -> dict:
        if len(x) == 0:
            return {
                "name": name, "n": 0, "mean_short": float("nan"), "med_short": float("nan"),
                "mean_net": float("nan"), "med_net": float("nan"), "ci_lo": float("nan"),
                "ci_hi": float("nan"), "pct_pos": float("nan"), "n_sym": 0,
            }
        sr = x["short_resid"].to_numpy(float)
        net = x["net_27bps_rt"].to_numpy(float)
        rng = np.random.default_rng(SEED)
        boots = [float(np.mean(rng.choice(sr, size=len(sr), replace=True))) for _ in range(800)]
        lo, hi = np.percentile(boots, [2.5, 97.5])
        return {
            "name": name,
            "n": len(x),
            "mean_short": float(np.mean(sr)),
            "med_short": float(np.median(sr)),
            "mean_net": float(np.mean(net)),
            "med_net": float(np.median(net)),
            "ci_lo": float(lo),
            "ci_hi": float(hi),
            "pct_pos": float(np.mean(sr > 0)),
            "n_sym": int(x["symbol"].nunique()),
        }

    main_all = pack("main_pct05_adv", ev)
    main_ti = pack("team_investor", ev[ev["team_investor"]]) if ev["team_investor"].any() else None
    early = pack("pre_2024", ev[ev["unlock_ms"] < SPLIT_MS]) if (ev["unlock_ms"] < SPLIT_MS).any() else None
    late = pack("post_2024", ev[ev["unlock_ms"] >= SPLIT_MS]) if (ev["unlock_ms"] >= SPLIT_MS).any() else None

    # monotonic by pct_circ terciles
    try:
        ev["pct_bin"] = pd.qcut(ev["pct_circ"], 3, labels=["low", "mid", "high"], duplicates="drop")
        mono = (
            ev.groupby("pct_bin", observed=True)["short_resid"]
            .agg(["count", "mean", "median"])
            .reset_index()
        )
        mono_txt = mono.to_string(index=False)
    except Exception as e:
        mono_txt = f"n/a ({e})"

    # random baseline: same symbols random 14d windows
    rng = np.random.default_rng(SEED)
    base_rets = []
    for _ in range(min(1500, max(300, len(ev) * 5))):
        row = ev.sample(1, random_state=int(rng.integers(1e9))).iloc[0]
        sdf = load_ohlcv(row["symbol"])
        if sdf is None:
            continue
        ts = sdf["ts"].to_numpy()
        if len(ts) < 40 * 24:
            continue
        # random end day with room for entry
        t1 = int(rng.choice(ts[ts > ts.min() + (ENTRY_LEAD_D + BETA_LOOKBACK_D) * DAY_MS]))
        t0e = t1 - ENTRY_LEAD_D * DAY_MS
        if adv_7d(sdf, t0e) < ADV_MIN:
            continue
        rs = window_return(sdf, t0e, t1)
        rb = window_return(btc, t0e, t1)
        b = beta_30d(sdf, btc, t0e)
        if not all(np.isfinite([rs, rb, b])):
            continue
        base_rets.append(-(rs - b * rb))
    base = np.asarray(base_rets, float) if base_rets else np.array([0.0])

    sr = ev["short_resid"].to_numpy(float)
    # excess vs random
    excess = float(np.mean(sr) - np.mean(base)) if len(base) else float("nan")
    rng2 = np.random.default_rng(SEED)
    boots = []
    for _ in range(600):
        boots.append(float(np.mean(rng2.choice(sr, len(sr), True)) - np.mean(rng2.choice(base, len(base), True))))
    blo, bhi = np.percentile(boots, [2.5, 97.5]) if boots else (np.nan, np.nan)

    def fmt(p: dict | None) -> str:
        if not p:
            return "n/a"
        return (
            f"{p['name']}: n={p['n']} sym={p['n_sym']} "
            f"mean_short={p['mean_short']*100:.2f}% med={p['med_short']*100:.2f}% "
            f"mean_net={p['mean_net']*100:.2f}% pos={p['pct_pos']*100:.1f}% "
            f"CI_mean[{p['ci_lo']*100:.2f},{p['ci_hi']*100:.2f}]%"
        )

    # simple CI for main mean short via bootstrap
    boots_m = [float(np.mean(rng2.choice(sr, len(sr), True))) for _ in range(800)]
    mlo, mhi = np.percentile(boots_m, [2.5, 97.5])
    main_all["ci_lo"], main_all["ci_hi"] = float(mlo), float(mhi)

    n_ok = len(ev)
    s0_note = []
    if n_ok < 80:
        s0_note.append(f"n={n_ok}<80 → 样本不足，不升级")
    if early and late:
        same = np.sign(early["mean_short"]) == np.sign(late["mean_short"])
        s0_note.append(f"两段同向={'YES' if same else 'NO'} (pre={early['mean_short']*100:.2f}% post={late['mean_short']*100:.2f}%)")
    s0_note.append(f"成本后 mean_net={main_all['mean_net']*100:.2f}%")
    s0_note.append(f"vs random excess={excess*100:.2f}% CI[{blo*100:.2f},{bhi*100:.2f}]% n_base={len(base)}")

    # descriptive verdict only
    if n_ok >= 30 and main_all["mean_short"] > 0 and mlo > 0 and main_all["med_short"] >= 0:
        verdict = "S0_INTERESTING"  # still not GO
    elif n_ok >= 20:
        verdict = "S0_WEAK_OR_MIXED"
    else:
        verdict = "S0_UNDERPOWERED"

    now = datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M UTC")
    md = f"""# s017 S0 本地沙盒 — Token Unlock 残差空

- date: {now}
- script: `scripts/s017_s0_local.py`
- events in: `{EVENTS_PQ}`
- prices: coinglass raw_1h klines
- **描述性 / exploratory；不宣布 GO / historical_pass**

## 规格（锁定）

- 入场: T0−14d 后第一根 1h open；平: T0 close asof
- 方向: 空残差 = −(r_sym − β·r_btc)，β=入场前 30d 日收益 OLS，clip[0,1.5]
- 过滤: pct_circ≥{PCT_MIN*100:.1f}% · ADV7d≥${ADV_MIN/1e6:.0f}M · 冷却 {COOLDOWN_D}d
- 成本: 悲观 round-trip {COST_RT*1e4:.0f} bps
- seed: {SEED}

## 结论

| 项 | 值 |
|---|---|
| 合格事件 n | {n_ok} |
| 覆盖币 | {main_all['n_sym']} |
| mean short residual | {main_all['mean_short']*100:.2f}% |
| median | {main_all['med_short']*100:.2f}% |
| bootstrap 95% CI mean | [{mlo*100:.2f}, {mhi*100:.2f}]% |
| mean net (27bps×2) | {main_all['mean_net']*100:.2f}% |
| 胜率 short>0 | {main_all['pct_pos']*100:.1f}% |
| vs random 14d excess | {excess*100:.2f}% CI[{blo*100:.2f},{bhi*100:.2f}] |
| **S0 判定** | **{verdict}** |

### 分层

- {fmt(main_all)}
- {fmt(main_ti)}
- {fmt(early)}
- {fmt(late)}

### 解锁占比三分位（单调性）

```
{mono_txt}
```

### 备注

{chr(10).join('- ' + x for x in s0_note)}

## 事件明细

`{OUT_CSV}`

## 下一跳（仍本地优先）

1. 扩 Mobula watchlist（更多 coinglass 币）→ 抬 n
2. team/investor 映射表手工化（alloc 字符串脏）
3. 次 horizon T0→T0+14d 仅描述
4. **S1 holdout 一次评** 仅当 n≥80 且 Owner 确认冻结

## 真·VPS 才需要

- Tokenomist 全量机构日历回填 / 跨源交叉校验
- 全市场数百币扫表
"""
    OUT_MD.write_text(md, encoding="utf-8")
    print(md)
    print(f"Wrote {OUT_MD} n={n_ok} verdict={verdict}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
