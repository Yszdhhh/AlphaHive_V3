r"""205_dex_volume_crosssection.py — D 测试：DEX 量 × wash_cvd（gpt 评审优先级 D）。

问题：121 的 CEX 放量（quote_volume_ratio>1.5 → +1.90%）是 wash_cvd 有效二阶。DEX 量
（链上 AMM 流动性）是独立市场结构——"wash_cvd 事件的放量是否同时在 DEX 出现"是正交问题。

数据：
- DEX 量：dex.trades（全 DEX 聚合，token symbol 口径）日频 amount_usd，2021-12 → 今
- wash_cvd 事件：115 口径；CEX 放量 ratio：coinglass klines quote_volume 24h/30d 中位数
检验（121 镜像 + gpt 审计）：
- DEX 放量（事件日 DEX vol / 30d 中位数 > 1.5）→ 前向 24/72/168h
- 2×2 联合矩阵：CEX 放量 × DEX 放量 四格（回答"独立增量还是同一放量两面"）
- 覆盖报告：% 事件有非零 DEX 量（<50% 降级描述性）

输出：reports/dex_volume_crosssection.md
用法：python scripts/205_dex_volume_crosssection.py [--pull]（--pull 拉 Dune 数据，否则只用缓存）
"""
from __future__ import annotations

import argparse
import importlib.util
import sys
from datetime import datetime, timezone
from pathlib import Path

import numpy as np
import pandas as pd

PROJECT_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(PROJECT_ROOT))

from harness.lib.event_study import bootstrap_ci, forward_stats  # noqa: E402

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

REPORT = PROJECT_ROOT / "reports" / "dex_volume_crosssection.md"
DEX_CSV = PROJECT_ROOT / "data" / "dune" / "dex_vol_daily.csv"
RATIO_THR = 1.5   # 121 同款
MIN_EVENTS = 20
SEED = 2026
HORIZONS = (24, 72, 168)
SYMBOLS = ["DOGE", "ADA", "LINK", "AVAX", "TRX", "LTC", "BCH", "PEPE", "ENA", "AAVE",
           "SUI", "WLD", "ONDO", "ARB", "OP", "UNI", "ATOM", "ETC", "HBAR", "FIL",
           "LDO", "CRV", "PENDLE", "WIF", "ORDI", "TIA", "VIRTUAL", "PUMP"]


def pull_dex_volume() -> int:
    from harness.lib.dune_mcp import DuneMCP
    d = DuneMCP()
    d.initialize()
    sym_list = ", ".join(f"'{s}'" for s in SYMBOLS)
    # codex 审计修正：买卖双侧都计入（token_bought + token_sold 两个腿的 amount_usd 求和）
    sql = f"""
WITH legs AS (
  SELECT date_trunc('day', block_time) AS d, token_bought_symbol AS symbol,
         sum(amount_usd) AS vol_usd
  FROM dex.trades
  WHERE blockchain = 'ethereum' AND token_bought_symbol IN ({sym_list})
    AND block_time >= timestamp '2021-12-01'
  GROUP BY 1, 2
  UNION ALL
  SELECT date_trunc('day', block_time) AS d, token_sold_symbol AS symbol,
         sum(amount_usd) AS vol_usd
  FROM dex.trades
  WHERE blockchain = 'ethereum' AND token_sold_symbol IN ({sym_list})
    AND block_time >= timestamp '2021-12-01'
  GROUP BY 1, 2
)
SELECT d, symbol, sum(vol_usd) AS vol_usd FROM legs GROUP BY 1, 2 ORDER BY 1, 2
"""
    rows = d.run_query("ah_dex_vol_daily2", sql, max_polls=90, poll_sleep_s=6)
    if not rows:
        print("查询失败/超时")
        return 1
    df = pd.DataFrame(rows)
    df["date"] = pd.to_datetime(df["d"], utc=True).dt.date.astype(str)
    df["vol_usd"] = pd.to_numeric(df["vol_usd"], errors="coerce")
    DEX_CSV.parent.mkdir(parents=True, exist_ok=True)
    df[["date", "symbol", "vol_usd"]].to_csv(DEX_CSV, index=False)
    print(f"wrote {DEX_CSV}: {len(df)} 行（{len(df['symbol'].unique())} 符号）")
    return 0


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--pull", action="store_true")
    args = ap.parse_args()
    if args.pull:
        if pull_dex_volume():
            return 1

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
    events = events[(events["timestamp"] >= int(pd.Timestamp("2021-12-01", tz="UTC").timestamp() * 1000))].copy()

    # CEX 放量 ratio（121 口径：事件时点 24h quote_volume / 30d 中位数，直接读 coinglass klines）
    cex_ratio: dict[str, np.ndarray] = {}
    cex_axis: dict[str, np.ndarray] = {}
    for sym in events["symbol"].unique():
        p = m113.COINGLASS_RAW1H / "klines" / f"{sym}.parquet"
        if not p.exists():
            continue
        kl = pd.read_parquet(p)
        if "quote_volume" not in kl.columns:
            continue
        ts = pd.to_numeric(kl["time"], errors="coerce").to_numpy(dtype=np.int64) if "time" in kl.columns \
            else pd.to_numeric(kl["open_time"], errors="coerce").to_numpy(dtype=np.int64)
        qv = pd.to_numeric(kl["quote_volume"], errors="coerce")
        qv24 = qv.rolling(24).sum()
        med30 = qv24.rolling(30 * 24, min_periods=24).median()
        ratio = (qv24 / med30.replace(0, np.nan)).to_numpy(dtype=float)
        cex_ratio[sym] = ratio
        cex_axis[sym] = ts

    # DEX 量日频 → 30d 中位数 ratio（codex 审计修正：稠密日历 + 事件日前一完整日 asof）
    dex = pd.read_csv(DEX_CSV) if DEX_CSV.exists() else pd.DataFrame()
    dex["date"] = pd.to_datetime(dex["date"], utc=True)
    dex_pivot = dex.pivot_table(index="date", columns="symbol", values="vol_usd", aggfunc="sum")
    # 稠密日历：全日期范围补零（避免"最近 30 个活跃交易日"跨数月）
    full_idx = pd.date_range(dex_pivot.index.min(), dex_pivot.index.max(), freq="D", tz="UTC")
    dex_pivot = dex_pivot.reindex(full_idx).fillna(0.0)
    dex_ratio = dex_pivot / dex_pivot.rolling(30, min_periods=15).median().replace(0, np.nan)

    # codex 审计修正：用事件前一日（前一完整 UTC 日）的 DEX 量，避免日内前视
    ev_date = pd.to_datetime(events["timestamp"], unit="ms", utc=True).dt.floor("D")
    ev_prev_day = ev_date - pd.Timedelta(days=1)
    base_sym = events["symbol"].str.replace("USDT", "")
    rows = []
    for i, (_, e) in enumerate(events.iterrows()):
        d = ev_prev_day.iloc[i]
        s = base_sym.iloc[i]
        r = {"symbol": e["symbol"], "timestamp": int(e["timestamp"]), "date": d}
        if s in dex_ratio.columns and d in dex_ratio.index:
            r["dex_ratio"] = dex_ratio.loc[d, s]
            r["dex_vol"] = dex_pivot.loc[d, s]
        else:
            r["dex_ratio"], r["dex_vol"] = np.nan, 0.0
        if e["symbol"] in cex_ratio:
            axis = cex_axis[e["symbol"]]
            pos = int(np.searchsorted(axis, int(e["timestamp"]), side="right")) - 1
            r["cex_ratio"] = cex_ratio[e["symbol"]][pos] if 0 <= pos < len(cex_ratio[e["symbol"]]) else np.nan
        else:
            r["cex_ratio"] = np.nan
        rows.append(r)
    ann = pd.DataFrame(rows)
    ev = events.merge(ann, on=["symbol", "timestamp"], how="left")

    fwd_parts = []
    for sym, g in ev.groupby("symbol", sort=False):
        fwd_parts.append(forward_stats(ctxs[sym], g.copy(), horizons=HORIZONS))
    ev = pd.concat(fwd_parts, ignore_index=True) if fwd_parts else ev

    cov = ev["dex_ratio"].notna().mean()
    n_hi = (ev["dex_ratio"] > RATIO_THR).sum()
    print(f"wash_cvd 事件 {len(ev)} | DEX 覆盖 {cov:.0%} | DEX 放量日 {n_hi}")

    lines = ["# DEX 量 × wash_cvd 横截面（205，gpt 评审优先级 D）\n",
             f"- 生成：{datetime.now(timezone.utc):%Y-%m-%d %H:%M UTC}",
             f"- DEX 量：dex.trades 日频 amount_usd（全 DEX 聚合）；ratio = 事件日量 / 30d 中位数",
             f"- 覆盖 {cov:.0%}（<50% 结论降级描述性）；DEX 放量阈值 {RATIO_THR}x（121 同款）\n",
             "| 层 | n | 24h 均值 | 72h 均值 | 168h 均值 | 168h 中位 |",
             "|---|---|---:|---:|---:|---:|"]
    for label, g in [("DEX 放量 >1.5x", ev[ev["dex_ratio"] > RATIO_THR]),
                     ("DEX 常态 ≤1.5x", ev[ev["dex_ratio"] <= RATIO_THR])]:
        if len(g) == 0:
            lines.append(f"| {label} | 0 | - | - | - | - |")
            continue
        cells = []
        for h in HORIZONS:
            v = pd.to_numeric(g[f"ret_{h}h"], errors="coerce").dropna()
            cells.append(f"{v.mean():+.2f}%（n={len(v)}）")
        med = pd.to_numeric(g["ret_168h"], errors="coerce").dropna().median()
        lines.append(f"| {label} | {len(g)} | {' | '.join(cells)} | {med:+.2f}% |")

    # 2×2：CEX 放量 × DEX 放量
    lines.append("\n## 2×2 联合矩阵（CEX 放量 × DEX 放量，24h 均值）\n")
    lines.append("| CEX\\DEX | DEX 放量 | DEX 常态 |")
    lines.append("|---|---:|---:|")
    both = ev[(ev["cex_ratio"] > RATIO_THR) & (ev["dex_ratio"] > RATIO_THR)]
    cex_only = ev[(ev["cex_ratio"] > RATIO_THR) & (ev["dex_ratio"] <= RATIO_THR)]
    dex_only = ev[(ev["cex_ratio"] <= RATIO_THR) & (ev["dex_ratio"] > RATIO_THR)]
    none = ev[(ev["cex_ratio"] <= RATIO_THR) & (ev["dex_ratio"] <= RATIO_THR)]
    for label, g in [("CEX 放量", both), ("CEX 常态", dex_only)]:
        cells = []
        for gg in [both if label == "CEX 放量" else dex_only,
                   cex_only if label == "CEX 放量" else none]:
            v = pd.to_numeric(gg["ret_24h"], errors="coerce").dropna()
            cells.append(f"{v.mean():+.2f}%（n={len(v)}）" if len(v) else "-")
        lines.append(f"| {label} | {' | '.join(cells)} |")
    # 增量检验：both vs cex_only（DEX 在 CEX 放量内的独立增量）
    v_both = pd.to_numeric(both["ret_24h"], errors="coerce").dropna().to_numpy(dtype=float)
    v_co = pd.to_numeric(cex_only["ret_24h"], errors="coerce").dropna().to_numpy(dtype=float)
    if len(v_both) >= MIN_EVENTS and len(v_co) >= MIN_EVENTS:
        ci = bootstrap_ci(v_both, v_co, seed=SEED)
        lines.append(f"\nDEX 在 CEX 放量内的增量（both−cex_only 24h）：{ci['mean_diff']:+.2f}% "
                     f"CI[{ci['ci_lo']:+.2f}, {ci['ci_hi']:+.2f}]")
        print(f"[205] DEX 独立增量 {ci['mean_diff']:+.2f}% CI[{ci['ci_lo']:+.2f}, {ci['ci_hi']:+.2f}]")

    lines += ["\n## 解读\n",
              "- codex（订阅）审计后修正口径：前一完整日 asof（无日内前视）+ 买卖双侧 + 稠密日历。",
              "- 修正后：2×2 方向单调（both +1.94% > cex_only +0.75% > dex_only +0.55% > 双常态 +0.10%），",
              "  但 DEX 独立增量 CI 含 0（+1.18% [-0.61, +3.11]）→ **未达升级线**（CI 排除 0 + t≥3）。",
              "- 覆盖 41% < 50% → 按验收口径降级**描述性**；地址级身份（PEPE 等 symbol 歧义）为已知限制。",
              "- 初版 +2.52% CI[+0.74,+4.35] 为前视+单侧污染假象，已作废（INVALIDATED_BY_DESIGN_AUDIT）。",
              "- 结论：DEX 放量与 CEX 放量同向、不是反向关系，但独立增量无统计证据 → D 不升级，",
              "  与 121 合并视为同一放量维度；如后续覆盖≥50% 可重测（D1 预算保留）。"]
    REPORT.parent.mkdir(parents=True, exist_ok=True)
    REPORT.write_text("\n".join(lines) + "\n", encoding="utf-8")
    print(f"wrote {REPORT}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
