r"""s018 S0+ 本地 — 截面中性 CS_MN funding（含价格腿粗拆，非 S1）。

- 结算后调仓；空高费率 quintile / 多低费率 quintile；n_leg=5
- 剔除 is_capped；排除 BTC/ETH
- 拆分 funding PnL vs 价格 PnL；成本 16.2bps / 27bps 双列
- 时间切 2025-01
数据：binance_free funding history + coinglass 1h klines（长历史）
用法：python scripts/s018_s0_local.py
"""
from __future__ import annotations

import sys
from datetime import datetime, timezone
from pathlib import Path

import numpy as np
import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from harness.lib.funding_semantics import (  # noqa: E402
    annotate_series,
    load_binance_funding_parquet,
    load_measurement_config,
    settlement_hours,
)

FUNDING_DIR = Path(r"C:\Users\10639\Desktop\加密\binance_free_db\history\funding")
KLINES = Path(r"C:\Users\10639\Desktop\🔒 加密资产\coinglass_db\raw_1h\klines")
OUT_MD = ROOT / "reports" / "s018_s0_local.md"
OUT_CSV = ROOT / "reports" / "s018_s0_local_periods.csv"

EXCLUDE = {"BTCUSDT", "ETHUSDT"}
N_LEG = 5
MIN_CROSS = N_LEG * 5  # 25
COST_REAL = 0.00162  # 16.2 bps per leg trade (one-way); round-trip rebalance approx below
COST_PESS = 0.0027
SEED = 20260812
SPLIT_MS = int(pd.Timestamp("2025-01-01", tz="UTC").timestamp() * 1000)
# 本地可跑：不全历史逐 bar 换手微观；用「权重变化 × 单边成本」近似
MAX_SYMBOLS = 70  # 本地尽量全 history funding
# 主规格 1=每结算；敏感性：每 N 个结算再调仓（降换手）
REBALANCE_EVERY_N = (1, 3, 9)  # 8h / 24h / 72h


def load_close_series(sym: str) -> pd.DataFrame | None:
    p = KLINES / f"{sym}.parquet"
    if not p.exists():
        return None
    df = pd.read_parquet(p, columns=["open_time", "open", "close"])
    df["ts"] = pd.to_numeric(df["open_time"], errors="coerce").astype("int64")
    df["open"] = pd.to_numeric(df["open"], errors="coerce")
    df["close"] = pd.to_numeric(df["close"], errors="coerce")
    return df.dropna(subset=["ts", "open", "close"]).sort_values("ts")


def asof_px(df: pd.DataFrame, t: int, col: str = "open") -> float:
    ts = df["ts"].to_numpy()
    i = int(np.searchsorted(ts, t, side="right") - 1)
    if i < 0:
        return float("nan")
    # 下一根 open 做调仓：若 col==open 且要 next bar
    return float(df[col].iloc[i])


def next_open(df: pd.DataFrame, t: int) -> float:
    """结算后下一根 1h open。"""
    ts = df["ts"].to_numpy()
    i = int(np.searchsorted(ts, t, side="right"))
    if i >= len(ts):
        return float("nan")
    return float(df["open"].iloc[i])


def run_book(g: pd.DataFrame, buckets: list, px: dict, every_n: int) -> pd.DataFrame:
    """every_n: rebalance every N settlement buckets; funding accrues each bucket."""
    rows = []
    prev_w: dict[str, float] = {}
    last_rebal_b = None
    rebal_count = 0
    for bi, b in enumerate(buckets):
        sub = g[g["bucket"] == b].dropna(subset=["rate"])
        if len(sub) < MIN_CROSS:
            prev_w = {}
            last_rebal_b = None
            continue
        sub = sub.sort_values("rate")
        do_rebal = (last_rebal_b is None) or (rebal_count % every_n == 0)
        if do_rebal:
            longs = sub.head(N_LEG)["symbol"].tolist()
            shorts = sub.tail(N_LEG)["symbol"].tolist()
            w = {}
            for s in longs:
                w[s] = w.get(s, 0.0) + 0.5 / N_LEG
            for s in shorts:
                w[s] = w.get(s, 0.0) - 0.5 / N_LEG
            if abs(sum(w.values())) > 0.05:
                prev_w = {}
                last_rebal_b = None
                continue
            turnover = 0.0
            for s in set(prev_w) | set(w):
                turnover += abs(w.get(s, 0.0) - prev_w.get(s, 0.0))
            new_w = w
            rebal_count += 1
        else:
            new_w = prev_w
            turnover = 0.0
            rebal_count += 1

        fund_pnl = 0.0
        if prev_w:
            rate_map = dict(zip(sub["symbol"], sub["rate"]))
            for s, wi in prev_w.items():
                r = rate_map.get(s)
                if r is None or not np.isfinite(r):
                    continue
                fund_pnl += -wi * float(r)

        price_pnl = 0.0
        if prev_w and bi > 0:
            b_prev = buckets[bi - 1]
            for s, wi in prev_w.items():
                if abs(wi) < 1e-12:
                    continue
                dfp = px.get(s)
                if dfp is None:
                    continue
                p0 = next_open(dfp, int(b_prev))
                p1 = next_open(dfp, int(b))
                if not np.isfinite(p0) or not np.isfinite(p1) or p0 <= 0:
                    continue
                price_pnl += wi * (p1 / p0 - 1.0)

        cost_real = turnover * COST_REAL
        cost_pess = turnover * COST_PESS
        gross = fund_pnl + price_pnl
        rows.append(
            {
                "bucket": b,
                "every_n": every_n,
                "n_sym": len(sub),
                "fund_pnl": fund_pnl,
                "price_pnl": price_pnl,
                "gross": gross,
                "turnover": turnover,
                "net_real": gross - cost_real,
                "net_pess": gross - cost_pess,
                "rebalanced": int(do_rebal),
            }
        )
        if do_rebal:
            prev_w = new_w
            last_rebal_b = b
        # else keep prev_w
    return pd.DataFrame(rows)


def main() -> int:
    if not FUNDING_DIR.exists():
        print(f"MISSING {FUNDING_DIR}")
        return 1
    cfg = load_measurement_config()
    settle_h = settlement_hours(cfg=cfg)
    bucket_ms = int(settle_h * 3600 * 1000)

    files = sorted(FUNDING_DIR.glob("*.parquet"))
    files = [f for f in files if f.stem not in EXCLUDE][:MAX_SYMBOLS]

    parts = []
    px = {}
    for fp in files:
        sym = fp.stem
        try:
            raw = load_binance_funding_parquet(fp)
            ann = annotate_series(raw["rate_decimal"], unit="decimal", cfg=cfg)
            use = raw.loc[~ann["is_capped"].to_numpy()].copy()
            use["symbol"] = sym
            use = use.rename(columns={"timestamp": "ts", "rate_decimal": "rate"})
            parts.append(use[["ts", "symbol", "rate"]])
            c = load_close_series(sym)
            if c is not None and len(c) > 100:
                px[sym] = c
        except Exception as e:
            print(f"skip {sym}: {e}")

    if not parts:
        return 2
    panel = pd.concat(parts, ignore_index=True)
    panel["bucket"] = (panel["ts"] // bucket_ms) * bucket_ms
    g = panel.sort_values("ts").groupby(["bucket", "symbol"], as_index=False).last()
    g = g[g["symbol"].isin(px)].copy()
    buckets = sorted(g["bucket"].unique())

    def summarize(df: pd.DataFrame, name: str) -> dict:
        if len(df) == 0:
            return {"name": name, "n": 0}
        return {
            "name": name,
            "n": len(df),
            "mean_fund": float(df["fund_pnl"].mean()),
            "mean_price": float(df["price_pnl"].mean()),
            "mean_gross": float(df["gross"].mean()),
            "mean_net_real": float(df["net_real"].mean()),
            "mean_net_pess": float(df["net_pess"].mean()),
            "sum_fund": float(df["fund_pnl"].sum()),
            "sum_price": float(df["price_pnl"].sum()),
            "mean_to": float(df["turnover"].mean()),
            "pct_gross_pos": float((df["gross"] > 0).mean()),
        }

    sens_lines = []
    main_per = None
    main_sum = None
    for every_n in REBALANCE_EVERY_N:
        per = run_book(g, buckets, px, every_n)
        if len(per) == 0:
            continue
        s = summarize(per, f"every_{every_n}x{settle_h}h")
        sens_lines.append(
            f"- every_n={every_n} (~{every_n * settle_h}h): n={s['n']} "
            f"fund={s['mean_fund']*1e4:.2f}bps price={s['mean_price']*1e4:.2f}bps "
            f"gross={s['mean_gross']*1e4:.2f}bps net16.2={s['mean_net_real']*1e4:.2f} "
            f"net27={s['mean_net_pess']*1e4:.2f} to={s['mean_to']:.3f}"
        )
        if every_n == 1:
            main_per = per
            main_sum = s
            per.to_csv(OUT_CSV, index=False)

    if main_per is None or main_sum is None:
        print("no periods")
        return 2

    per = main_per
    all_s = main_sum
    pre = summarize(per[per["bucket"] < SPLIT_MS], "pre_2025")
    post = summarize(per[per["bucket"] >= SPLIT_MS], "post_2025")

    fail = []
    if all_s["n"] < 180:
        fail.append(f"n_periods={all_s['n']}<180 underpowered for S1")
    if all_s.get("mean_net_pess", 0) <= 0:
        fail.append("mean net_pess (27bps) <= 0  [主规格 every_n=1]")
    if all_s.get("mean_price", 0) < 0 and abs(all_s["mean_price"]) > abs(all_s.get("mean_fund", 0)):
        fail.append("price leg magnitude > funding and negative")
    same_dir = (
        pre.get("n", 0) > 0
        and post.get("n", 0) > 0
        and np.sign(pre.get("mean_net_pess", 0)) == np.sign(post.get("mean_net_pess", 0))
    )
    if not same_dir:
        fail.append("time-split mean_net_pess not same sign")

    # 主规格 verdict（every_n=1）
    if all_s["n"] >= 100 and all_s["mean_net_pess"] > 0 and same_dir:
        verdict = "S0_INTERESTING"
    elif all_s.get("mean_net_pess", 0) <= 0 and all_s.get("mean_price", 0) < 0:
        verdict = "S0_FAIL_HINT"  # 红线命中，仍非正式 S1
    elif all_s["n"] >= 50:
        verdict = "S0_WEAK_OR_MIXED"
    else:
        verdict = "S0_UNDERPOWERED"

    def line(s: dict) -> str:
        if s.get("n", 0) == 0:
            return f"{s.get('name')}: empty"
        return (
            f"{s['name']}: n={s['n']} fund={s['mean_fund']*1e4:.2f}bps "
            f"price={s['mean_price']*1e4:.2f}bps gross={s['mean_gross']*1e4:.2f}bps "
            f"net16.2={s['mean_net_real']*1e4:.2f}bps net27={s['mean_net_pess']*1e4:.2f}bps "
            f"to={s['mean_to']:.2f} win%={s['pct_gross_pos']*100:.1f}"
        )

    now = datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M UTC")
    md = f"""# s018 CS_MN S0+ 本地（含价格腿 + 调仓频率敏感性）

- date: {now}
- script: `scripts/s018_s0_local.py`
- funding: `{FUNDING_DIR}` (≤{MAX_SYMBOLS} alts, uncapped only)
- prices: coinglass 1h
- **CS_MN / ≠s014 / ≠s005**；exploratory，不宣布 GO
- **主规格判定仅 every_n=1**；更低频为描述性敏感性（未改卡）

## 规格

- 结算 {settle_h}h：空 top{N_LEG} / 多 bottom{N_LEG}；美元中性
- funding / 价格腿拆分；成本 16.2 / 27 bps × 换手

## 主规格结论 (every_n=1)

| 项 | 值 |
|---|---|
| n | {all_s['n']} |
| mean fund / price / gross (bps) | {all_s['mean_fund']*1e4:.3f} / {all_s['mean_price']*1e4:.3f} / {all_s['mean_gross']*1e4:.3f} |
| mean net 16.2 / 27 (bps) | {all_s['mean_net_real']*1e4:.3f} / {all_s['mean_net_pess']*1e4:.3f} |
| mean turnover | {all_s['mean_to']:.3f} |
| 两段同向 net27 | {same_dir} |
| **S0 判定** | **{verdict}** |

### 分段（主规格）

- {line(all_s)}
- {line(pre)}
- {line(post)}

### 调仓频率敏感性（描述）

{chr(10).join(sens_lines)}

### 红线检查（主规格）

{chr(10).join('- ' + f for f in fail) if fail else '- none triggered'}

## 明细

`{OUT_CSV}`

## 解读

- funding 截面价差本身常为正，但 **价格腿 + 高频换手** 可吞噬 carry。
- 若敏感性显示低频仍净负 → 机制在可交易成本下弱；若低频转正 → 需 **改卡重预注册** 才能进 S1。

## 真·VPS

- 全所微观结构冲击、借币、多所 funding 对齐（本机已覆盖 70 币 8h 面板级）
"""
    OUT_MD.write_text(md, encoding="utf-8")
    print(md)
    print(f"Wrote {OUT_MD} n={all_s['n']} {verdict}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
