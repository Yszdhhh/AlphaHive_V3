# 数据源健康报告（199）

- 生成：2026-08-11 03:36 UTC
- 来源：config/data_paths.yaml + harness/lib/data_registry.py

| 源 | 存在 | 最后 bar | 距今(h) | 状态 |
|---|---|---|---|---|
| coinglass_klines | ✓ | 2026-07-07 03:00 | 840.6 | ⚠️ 过期（预期停更：coinglass 公共接口 klines 停于 2026-07-07（记忆：klines 实际到 07-07）） |
| coinglass_liquidation | ✓ | 2026-06-23 03:00 | 1176.6 | ⚠️ 过期（预期停更：coinglass 清算停于 2026-06-23，E21 前向已切 Coinalyze（196）） |
| binance_klines | ✓ | 2026-08-11 02:00 | 1.6 | ✅ 正常 |
| coinalyze_liquidation | ✓ | 2026-08-11 00:00 | 3.6 | ✅ 正常 |
| otc_premium | ✓ | 2026-08-11 | 11.6 | ✅ 正常 |
| macro_sp500 | ✓ | 2026-08-07 00:00 | 107.6 | ✅ 正常 |
| macro_vix | ✓ | 2026-08-07 00:00 | 107.6 | ✅ 正常 |
| cme_bitcoin | ✓ | 2026-08-07 00:00 | 107.6 | ✅ 正常（周末无交易） |

## 清洗质量（binance_free klines 抽样，data_cleaning.clean_hourly_klines）
| symbol | 行数(清洗前→后) | OK | Gap_FFill | Outlier | Hard_Invalid | 未解gap | 状态 |
|---|---|---|---|---|---|---|---|
| BTCUSDT | 1725→1725 | 1725 | 0 | 0 | 0 | 0 | ✅ |
| ETHUSDT | 1725→1725 | 1725 | 0 | 0 | 0 | 0 | ✅ |
| SOLUSDT | 1724→1724 | 1724 | 0 | 0 | 0 | 0 | ✅ |

**意外过期/异常源：0 个**（预期停更与周末豁免不计）
