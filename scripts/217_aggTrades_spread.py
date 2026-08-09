r"""217_aggTrades_spread.py — 真实执行成本校准（Phase 1 收口，gemini 方案 1：Realized Spread）。

问题：216 用 friction_config 悲观代理（131bps 双边）vs 27bps 统计锚，区间太宽。
答案：币安官方免费归档 data.binance.vision 有**全标的** aggTrades（含股票代币），
is_buyer_maker 可还原真实吃单方向 → Realized Spread（真成交成本，含冲击）。

方法（gemini 方案 1，逐笔 D 账户交易）：
- 入场日 = 事件 ts + 5h 所在日；出场日 = 入场 + 163h 所在日
- 当日 aggTrades → VWAP_taker_buy（is_buyer_maker=false）− VWAP_taker_sell（true）
- realized_spread_bps = 差 / mid × 1e4
- 真实双边成本 = realized_spread（进+出各半幅，合计一个 spread）+ 2 × taker_fee(5.5)
- 对每笔交易：cost_real_bps = spread_day_in + spread_day_out + 11
- α 重估：pnl_net − notional × (cost_real − 54)/1e4（相对 legacy 双边 54bps 的差）
缓存：data/aggTrades_cache/（幂等）

输出：reports/execution_phase1_D_real.csv + execution_phase1_D_real.md
用法：python scripts/217_aggTrades_spread.py
"""
from __future__ import annotations

import io
import sys
import urllib.request
import zipfile
from datetime import datetime, timezone
from pathlib import Path

import numpy as np
import pandas as pd

PROJECT_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(PROJECT_ROOT))

POS_CSV = PROJECT_ROOT / "reports" / "paper_positions_D.csv"
CACHE = PROJECT_ROOT / "data" / "aggTrades_cache"
OUT_CSV = PROJECT_ROOT / "reports" / "execution_phase1_D_real.csv"
OUT_MD = PROJECT_ROOT / "reports" / "execution_phase1_D_real.md"
TAKER_BPS = 5.5
LEGACY_ROUND_BPS = 54.0
NOTIONAL = 1000.0
HOUR_MS = 3_600_000
ZIP_URL = "https://data.binance.vision/data/futures/um/daily/aggTrades/{sym}/{sym}-aggTrades-{day}.zip"


def day_str(ts_ms: int) -> str:
    return datetime.fromtimestamp(ts_ms / 1000, tz=timezone.utc).strftime("%Y-%m-%d")


def realized_spread(sym: str, day: str) -> float | None:
    """当日 aggTrades → realized spread bps（VWAP_buy − VWAP_sell）/ mid。缓存幂等。"""
    CACHE.mkdir(parents=True, exist_ok=True)
    cp = CACHE / f"{sym}_{day}.parquet"
    if cp.exists():
        df = pd.read_parquet(cp)
    else:
        url = ZIP_URL.format(sym=sym, day=day)
        try:
            with urllib.request.urlopen(url, timeout=60) as r:
                data = r.read()
        except Exception:  # noqa: BLE001
            return None
        if not data:
            return None
        try:
            z = zipfile.ZipFile(io.BytesIO(data))
            name = z.namelist()[0]
            with z.open(name) as f:
                df = pd.read_csv(f)
        except Exception:  # noqa: BLE001
            return None
        df["transact_time"] = pd.to_numeric(df["transact_time"], errors="coerce")
        df.to_parquet(cp, index=False)
    if len(df) < 2:
        return None
    price = pd.to_numeric(df["price"], errors="coerce")
    qty = pd.to_numeric(df["quantity"], errors="coerce")
    maker = df["is_buyer_maker"].astype(str).str.lower().isin(["true", "1"])
    nv = (price * qty)
    buy_vwap = nv[~maker].sum() / qty[~maker].sum() if qty[~maker].sum() > 0 else np.nan
    sell_vwap = nv[maker].sum() / qty[maker].sum() if qty[maker].sum() > 0 else np.nan
    if not (np.isfinite(buy_vwap) and np.isfinite(sell_vwap)) or (buy_vwap + sell_vwap) <= 0:
        return None
    mid = (buy_vwap + sell_vwap) / 2
    return 1e4 * (buy_vwap - sell_vwap) / mid


def main() -> int:
    pos = pd.read_csv(POS_CSV)
    rows = []
    for _, r in pos.iterrows():
        sym = r["symbol"]
        entry_ms = int(r["timestamp_ms"]) + 5 * HOUR_MS
        exit_ms = entry_ms + 163 * HOUR_MS
        d_in, d_out = day_str(entry_ms), day_str(exit_ms)
        s_in, s_out = realized_spread(sym, d_in), realized_spread(sym, d_out)
        if s_in is None or s_out is None:
            rows.append({"symbol": sym, "alert_id": r["alert_id"], "pnl_net": r["pnl_net"],
                         "spread_bps_in": np.nan, "spread_bps_out": np.nan,
                         "cost_real_bps": np.nan, "status": "SPREAD_MISSING"})
            continue
        # 市价单只吃半幅 spread（入场 half-spread + 出场 half-spread = 合计一个 full spread）
        cost_real = 0.5 * (s_in + s_out) + 2 * TAKER_BPS
        rows.append({"symbol": sym, "alert_id": r["alert_id"], "pnl_net": r["pnl_net"],
                     "spread_bps_in": round(s_in, 2), "spread_bps_out": round(s_out, 2),
                     "cost_real_bps": round(cost_real, 2), "status": "OK"})
    df = pd.DataFrame(rows)
    OUT_CSV.parent.mkdir(parents=True, exist_ok=True)
    df.to_csv(OUT_CSV, index=False)

    ok = df[df["status"] == "OK"]
    n_ok = len(ok)
    n_miss = len(df) - n_ok
    lines = ["# 执行层 Phase 1：真实执行成本校准（217，aggTrades Realized Spread）\n",
             f"- 生成：{datetime.now(timezone.utc):%Y-%m-%d %H:%M UTC}",
             f"- 数据：data.binance.vision aggTrades（全标的，is_buyer_maker → 真实吃单方向）",
             f"- 真实双边成本 = 0.5×(入场日 spread + 出场日 spread) + 2×taker({TAKER_BPS}bps)",
             f"- 样本：{n_ok} 笔可校准 / {len(df)} 总（缺失 {n_miss}，NaN 不补）\n",
             "## 真实成本 vs 两锚\n",
             "| 指标 | 值 |",
             "|---|---:|",
             f"| 真实双边成本中位 | {ok['cost_real_bps'].median():.1f} bps |",
             f"| 真实成本 P75 | {ok['cost_real_bps'].quantile(.75):.1f} bps |",
             f"| 真实成本 P90 | {ok['cost_real_bps'].quantile(.90):.1f} bps |",
             f"| legacy 双边锚 | {LEGACY_ROUND_BPS:.0f} bps |",
             f"| 悲观 config 双边中位（216） | 131.0 bps |",
             f"| 入场日 spread 中位 | {ok['spread_bps_in'].median():.1f} bps |",
             f"| 出场日 spread 中位 | {ok['spread_bps_out'].median():.1f} bps |\n",
             "## α 重估（真实成本，相对 legacy 双边 54bps 的差）\n"]
    if n_ok:
        extra = ok["cost_real_bps"] - LEGACY_ROUND_BPS
        pnl_adj = ok["pnl_net"] - NOTIONAL * extra / 1e4
        lines += [f"| 当前净盈亏 | ${ok['pnl_net'].sum():,.0f} |",
                  f"| 按真实成本重估 | **${pnl_adj.sum():,.0f}** |",
                  f"| 额外成本合计 | ${NOTIONAL * extra.sum() / 1e4:,.0f} |",
                  f"| 单笔成本差中位 | {extra.median():+.1f} bps |",
                  "\n## 结论（真实数据，非代理）\n",
                  "- 真实双边成本中位 vs 27bps 锚（54 双边）：偏紧还是偏松由中位差决定；",
                  "- vs 216 悲观 131bps：真实数据应显著低于代理上界 → 区间收窄；",
                  "- 缺失行（当日无 aggTrades/下载失败）：不补零，如实标注。"]
    else:
        lines.append("| 无可用样本 | - |")
    OUT_MD.write_text("\n".join(lines) + "\n", encoding="utf-8")
    if n_ok:
        extra = ok["cost_real_bps"] - LEGACY_ROUND_BPS
        print(f"真实双边成本中位 {ok['cost_real_bps'].median():.1f}bps | P90 {ok['cost_real_bps'].quantile(.9):.1f}bps | "
              f"α 重估 ${(ok['pnl_net'] - NOTIONAL*extra/1e4).sum():,.0f}（原 ${ok['pnl_net'].sum():,.0f}）| 缺失 {n_miss}")
    print(f"wrote {OUT_CSV} + {OUT_MD}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
