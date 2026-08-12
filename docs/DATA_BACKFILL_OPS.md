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

# ★ 推荐：一键周同步（回补+去重+GC+覆盖+健康）
python scripts/224_weekly_data_sync.py

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
| 221 klines 硬链接去重 | 218 大批量后跑一次 |
| 222 aggTrades 缓存 GC | 月 1 次或缓存 >800MB |

## P1 去重与缓存

```bash
# history 与 raw_1h/klines 共用同一文件（硬链接，省 ~146MB 逻辑双份）
python scripts/221_dedupe_klines_hardlink.py

# aggTrades 缓存控制（默认保留 7 天且总上限 500MB）
python scripts/222_aggtrades_cache_gc.py --keep-days 7 --max-mb 500 --dry-run
python scripts/222_aggtrades_cache_gc.py --keep-days 7 --max-mb 500
```

218 新回补会优先写 history 再硬链到 raw（失败才拷贝）。

## K 线还原 / 可视化（跑策略对照）

统一读库：`harness/lib/klines_store.py`（auto：history → raw → coinglass）

```bash
# 最近 60 天 BTC 蜡烛图 + CSV
python scripts/223_kline_view.py --symbol BTCUSDT --days 60

# 指定区间
python scripts/223_kline_view.py --symbol ARBUSDT --start 2025-01-01 --end 2025-06-01

# 只要 CSV
python scripts/223_kline_view.py --symbol ETHUSDT --days 30 --no-plot
```

产出目录：`reports/kline_views/{SYMBOL}_{start}_{end}.csv|.png`

策略脚本示例：

```python
from harness.lib.klines_store import load_klines, to_datetime_index
df = load_klines("BTCUSDT", start="2024-01-01", end="2026-08-01")
px = to_datetime_index(df)  # index=UTC datetime，列 open/high/low/close/volume
```
