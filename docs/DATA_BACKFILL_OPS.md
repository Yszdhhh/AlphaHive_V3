# 数据回补与基建操作（2026-08-12）

## 问题

| 源 | 状态 |
|---|---|
| coinglass 1h klines | 停更 ~2026-07-07（冷库/对照） |
| binance raw_1h klines | 曾仅 2026-05-31 起；**218 回补后应含全历史** |
| funding | `history/funding` 由 110 维护 |
| OI 长历史 | **公开 API 无法回补**（接受缺口） |

## 标准命令

```bash
cd "G:\Quant test\AlphaHive_V3"

# 1) klines 全历史回补并并入 raw_1h（可重复，增量）
python scripts/218_backfill_binance_klines.py
# 子集：python scripts/218_backfill_binance_klines.py --symbols BTCUSDT,ETHUSDT

# 2) funding 历史刷新
python scripts/110_backfill_history.py

# 3) 覆盖缺口报告
python scripts/220_coverage_gap_report.py

# 4) 健康检查
python scripts/199_data_health.py
```

## 路径（data_registry / data_paths.yaml）

| 逻辑 | 物理 |
|---|---|
| `paths.binance_free.raw_1h / klines` | `...\binance_free_db\raw_1h\klines` |
| history klines | `...\binance_free_db\history\klines` |
| history funding | `...\binance_free_db\history\funding` |
| coinglass | `Desktop\🔒 加密资产\coinglass_db\...`（仅对照） |

## 研究默认源（Owner A 后）

1. **价格主源**：binance `raw_1h` 或 `history/klines`（回补后等价加长）  
2. **funding 主源**：`history/funding` + semantics  
3. **coinglass**：停更前对照 / 旧脚本兼容；新脚本禁止当唯一活源  

## Git

- **不**提交 parquet 行情  
- **提交** 218/220 脚本、本 ops 文档、reports/*.md 结论  

## 频率建议

| 任务 | 频率 |
|---|---|
| 前向 puller（已有计划任务） | 小时/日 |
| 218 增量（从 last-48h） | 周 1 次或 raw 落后时 |
| 110 funding | 周 1 次 |
| 199 + 220 | 日/周 |
