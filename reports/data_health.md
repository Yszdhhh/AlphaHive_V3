# 数据源健康报告（199）

- 生成：2026-08-08 18:21 UTC
- 来源：config/data_paths.yaml + harness/lib/data_registry.py

| 源 | 存在 | 最后 bar | 距今(h) | 状态 |
|---|---|---|---|---|
| coinglass_klines | ✓ | 2026-07-07 03:00 | 783.4 | ⚠️ 过期（预期停更：coinglass 公共接口 klines 停于 2026-07-07（记忆：klines 实际到 07-07）） |
| coinglass_liquidation | ✓ | 2026-06-23 03:00 | 1119.4 | ⚠️ 过期（预期停更：coinglass 清算停于 2026-06-23，E21 前向已切 Coinalyze（196）） |
| binance_klines | ✓ | 2026-08-08 16:00 | 2.4 | ✅ 正常 |
| coinalyze_liquidation | ✓ | 2026-08-08 16:00 | 2.4 | ✅ 正常 |
| otc_premium | ✓ | 2026-08-08 | 26.4 | ✅ 正常 |
| macro_sp500 | ✓ | 2026-08-07 00:00 | 50.4 | ✅ 正常 |
| macro_vix | ✓ | 2026-08-06 00:00 | 74.4 | ✅ 正常 |
| cme_bitcoin | ✓ | 2026-08-06 00:00 | 74.4 | ✅ 正常 |

**意外过期源：0 个**（预期停更不计）
