r"""201_dune_stablecoin_history.py — Dune 链上稳定币价格历史回填（P7/P4 恐慌日回测数据层）。

数据源对比（2026-08-09 实测）：
- Uniswap v3 USDT/USDC 0.01% 池（0x3416cf...）：**1030 天全部钉在 1.000000**（套利太紧，
  不是有效脱锚 gauge）→ 已弃用，历史保留 data/dune/usdt_usdc_v3_daily.csv 作负结果记录。
- **Curve 3pool（0xbebc44782c7db0a1a60cb6fe97d0b483032ff1c7，DAI/USDC/USDT）**：
  经典脱锚 venue（2022-05 LUNA 时 USDT/DAI ~0.95-0.97）→ 主源。

本脚本：3pool TokenExchange → 日频 USDT 价格（DAI per USDT，micro 精度）：
  price = dai_amount / usdt_amount（DAI 18 位 / USDT 6 位换算）
  只取 sold_id∈{0,2} 且 bought_id∈{2,0}（DAI↔USDT 腿，不含 USDC）
  清洗：价格区间 [0.5, 2]、日 swap 数 ≥20
存 data/dune/usdt_3pool_daily.csv（幂等）。

用法：python scripts/201_dune_stablecoin_history.py
"""
from __future__ import annotations

import sys
from pathlib import Path

import pandas as pd

PROJECT_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(PROJECT_ROOT))

from harness.lib.dune_mcp import DuneMCP  # noqa: E402

OUT = PROJECT_ROOT / "data" / "dune" / "usdt_3pool_daily.csv"
POOL = "0xbebc44782c7db0a1a60cb6fe97d0b483032ff1c7"
MIN_SWAPS = 20
PRICE_LO, PRICE_HI = 0.5, 2.0

SQL = f"""
WITH legs AS (
  SELECT evt_block_time,
         CASE WHEN sold_id = 0 THEN tokens_sold * 1e-18
              WHEN sold_id = 2 THEN tokens_bought * 1e-18 END AS dai_amt,
         CASE WHEN sold_id = 2 THEN tokens_sold * 1e-6
              WHEN sold_id = 0 THEN tokens_bought * 1e-6 END AS usdt_amt,
         CASE WHEN sold_id = 0 THEN tokens_sold * 1e-18 / (tokens_bought * 1e-6)
              WHEN sold_id = 2 THEN tokens_bought * 1e-18 / (tokens_sold * 1e-6) END AS px
  FROM curvefi_ethereum.threepool_swap_evt_tokenexchange
  WHERE contract_address = {POOL}
    AND sold_id IN (0, 2) AND bought_id IN (2, 0)
    AND tokens_sold > 0 AND tokens_bought > 0
)
SELECT date_trunc('day', evt_block_time) AS d,
       count(*) AS n_swaps,
       approx_percentile(round(px * 1e6), 0.5) AS med_px_micro,
       approx_percentile(round(px * 1e6), 0.25) AS q25_px_micro,
       approx_percentile(round(px * 1e6), 0.75) AS q75_px_micro
FROM legs
WHERE px BETWEEN {PRICE_LO} AND {PRICE_HI}
GROUP BY 1 ORDER BY 1
"""


def main() -> int:
    d = DuneMCP()
    d.initialize()
    rows = d.run_query("ah_3pool_daily", SQL, max_polls=90, poll_sleep_s=6)
    if not rows:
        print("查询无结果/超时")
        return 1
    df = pd.DataFrame(rows)
    df["date"] = pd.to_datetime(df["d"], utc=True).dt.date.astype(str)
    for c in ("n_swaps", "med_px_micro", "q25_px_micro", "q75_px_micro"):
        df[c] = pd.to_numeric(df[c], errors="coerce")
    df["med_dai_per_usdt"] = df["med_px_micro"] / 1e6
    df["premium_bps"] = (df["med_dai_per_usdt"] - 1.0) * 1e4
    df = df[df["n_swaps"] >= MIN_SWAPS].sort_values("date")
    out = df[["date", "n_swaps", "med_dai_per_usdt", "q25_px_micro", "q75_px_micro",
              "premium_bps"]]
    OUT.parent.mkdir(parents=True, exist_ok=True)
    out.to_csv(OUT, index=False, encoding="utf-8")
    print(f"wrote {OUT}: {len(out)} 天（{out['date'].iloc[0]} → {out['date'].iloc[-1]}）")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
