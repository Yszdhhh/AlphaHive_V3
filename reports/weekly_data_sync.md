# 周度数据同步 224

- date: 2026-08-12 10:27 UTC
- skip_backfill: False  no_gc: False
- keep_days=7 max_mb=500

| 步骤 | exit |
|---|---|
| 218 klines backfill | 0 |
| 110 funding backfill | 0 |
| 221 hardlink dedupe | 0 |
| 222 aggTrades GC | 0 |
| 220 coverage | 0 |
| 199 health | 0 |

## tails

### 218 klines backfill (exit 0)
```
```

## 说明

- 公开 fapi，无 key；OI 历史仍无法公开回补（见 110 注释）
- coinglass 仍作对照冷库；**主研究/前向应逐步切 binance history/raw**

wrote G:\Quant test\AlphaHive_V3\reports\backfill_klines_218.md
```

### 110 funding backfill (exit 0)
```
[67/69] BTCUSDT: 5054 条 2022-01-01 → 2026-08-12 (2.3s)
[68/69] ETHUSDT: 5054 条 2022-01-01 → 2026-08-12 (2.2s)
[69/69] SOLUSDT: 5129 条 2022-01-01 → 2026-08-12 (3.0s)

=== 回填完成 ===
成功 69/69，共 246213 条 funding 记录
覆盖 2023-01 前的 symbol（可测 2022 磨底/FTX 底）: 24 个
  ['AAVEUSDT', 'ADAUSDT', 'ATOMUSDT', 'AVAXUSDT', 'BCHUSDT', 'BTCUSDT', 'CRVUSDT', 'DASHUSDT', 'DOGEUSDT', 'ETCUSDT', 'ETHUSDT', 'FILUSDT', 'HBARUSDT', 'ICPUSDT', 'INJUSDT', 'LDOUSDT', 'LINKUSDT', 'LTCUSDT', 'OPUSDT', 'SOLUSDT', 'TRXUSDT', 'UNIUSDT', 'XLMUSDT', 'XMRUSDT']
```

### 221 hardlink dedupe (exit 0)
```
done linked=0 skipped_same=69 failed=0 dry=False
```

### 222 aggTrades GC (exit 0)
```
cache files=519 size_mb=1693.4 keep_days=7
delete 409 files free_mb=1206.6 dry=False
```

### 220 coverage (exit 0)
```
2. coinglass 仅作 2026-07 前对照；**新研究默认 binance history/raw**
3. funding 用 `python scripts/110_backfill_history.py` 增量刷新

## 全表

见 CSV（按 symbol）。

wrote G:\Quant test\AlphaHive_V3\reports\coverage_gap_220.md
```

### 199 health (exit 0)
```
| symbol | 行数(清洗前→后) | OK | Gap_FFill | Outlier | Hard_Invalid | 未解gap | 状态 |
|---|---|---|---|---|---|---|---|
| BTCUSDT | 57971→57971 | 57971 | 0 | 0 | 0 | 0 | ✅ |
| ETHUSDT | 57971→57971 | 57971 | 0 | 0 | 0 | 0 | ✅ |
| SOLUSDT | 51796→51796 | 51796 | 0 | 0 | 0 | 0 | ✅ |

**意外过期/异常源：0 个**（预期停更与周末豁免不计）
wrote G:\Quant test\AlphaHive_V3\reports\data_health.md
```
