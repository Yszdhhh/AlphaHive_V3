# 220 多源覆盖缺口报告

- date: 2026-08-12 10:27 UTC
- symbols scanned: 124
- coinglass klines: 124
- binance raw_1h klines: 69
- binance history/klines: 69
- funding history: 69

## 结论（给基建）

| 项 | 值 |
|---|---|
| history 已覆盖币 | 69 |
| raw 仍短（n&lt;500 或无 hist） | 55 |
| CSV | `G:\Quant test\AlphaHive_V3\reports\coverage_gap_220.csv` |

### raw 最短样本

```
  symbol  bn_raw_n bn_raw_min bn_raw_max  bn_hist_n bn_hist_min
SPCXUSDT      1999 2026-05-21 2026-08-12       1999  2026-05-21
  MUUSDT      3046 2026-04-07 2026-08-12       3046  2026-04-07
SNDKUSDT      3046 2026-04-07 2026-08-12       3046  2026-04-07
  BZUSDT      3194 2026-04-01 2026-08-12       3194  2026-04-01
NVDAUSDT      3333 2026-03-26 2026-08-12       3333  2026-03-26
CRCLUSDT      4413 2026-02-09 2026-08-12       4413  2026-02-09
INTCUSDT      4581 2026-02-02 2026-08-12       4581  2026-02-02
TSLAUSDT      4701 2026-01-28 2026-08-12       4701  2026-01-28
```

### 建议

1. 跑 `python scripts/218_backfill_binance_klines.py` 直到 history 与 raw 拉长
2. coinglass 仅作 2026-07 前对照；**新研究默认 binance history/raw**
3. funding 用 `python scripts/110_backfill_history.py` 增量刷新

## 全表

见 CSV（按 symbol）。
