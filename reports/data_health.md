# 数据源健康报告（199）

- 生成：2026-08-11 01:15 UTC
- 来源：config/data_paths.yaml + harness/lib/data_registry.py

| 源 | 存在 | 最后 bar | 距今(h) | 状态 |
|---|---|---|---|---|
| coinglass_klines | ✓ | 2026-07-07 03:00 | 838.3 | ⚠️ 过期（预期停更：coinglass 公共接口 klines 停于 2026-07-07（记忆：klines 实际到 07-07）） |
| coinglass_liquidation | ✓ | 2026-06-23 03:00 | 1174.3 | ⚠️ 过期（预期停更：coinglass 清算停于 2026-06-23，E21 前向已切 Coinalyze（196）） |
| binance_klines | ✓ | 2026-08-10 23:00 | 2.3 | ✅ 正常 |
| coinalyze_liquidation | ✓ | 2026-08-11 00:00 | 1.3 | ✅ 正常 |
| otc_premium | ✓ | 2026-08-11 | 9.3 | ✅ 正常 |
| macro_sp500 | ✓ | 2026-08-07 00:00 | 105.3 | ✅ 正常 |
| macro_vix | ✓ | 2026-08-07 00:00 | 105.3 | ✅ 正常 |
| cme_bitcoin | ✓ | 2026-08-07 00:00 | 105.3 | ⚠️ 过期 |

**意外过期源：1 个**（预期停更不计）
