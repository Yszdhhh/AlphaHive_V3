# 基建同步状态（2026-08-12）

## 已落地

| 层 | 内容 |
|---|---|
| 数据回补 | 218 klines 全历史；110 funding；69 币 |
| 去重 | 221 history↔raw 硬链接 |
| 缓存 | 222 aggTrades GC 工具 |
| 观测 | 199 健康；220 覆盖 |
| 编排 | **224 周同步一键** |
| 读源 | klines_store；108 改 data_registry |
| 可视化 | 223 K 线 CSV/PNG |
| 治理 | A 决策、s017 观察、s018 停；gitignore 放大缓存 |

## 建议周节奏

| 日 | 动作 |
|---|---|
| 日 | 既有 AlphaHiveV3_* 计划任务（scan/forward/paper） |
| 周 | `python scripts/224_weekly_data_sync.py` |
| 月 | 审 `reports/weekly_data_sync.md` + harness/runs 是否清旧 |

## 仍可选（未强制）

- 旧研究脚本（105/113…）批量改 registry（非前向关键路径）
- harness/runs 归档脚本
- Windows 计划任务注册 224（需 Owner 本机确认）
- git push（本地可能 ahead）

## 不做什么

- 行情进 Git
- 新数据库中间件
- 复活 s018 / 默扩 Unlock
