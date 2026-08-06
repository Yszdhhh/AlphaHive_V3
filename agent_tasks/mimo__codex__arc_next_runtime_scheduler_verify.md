# ARC-NEXT-RUNTIME-SCHEDULER-VERIFY-001｜Mimo 派单

**agent:** Mimo  
**task_id:** `ARC-NEXT-RUNTIME-SCHEDULER-VERIFY-001`  
**tier:** T1 read-only  
**formal output:** `C:\Users\10639\Desktop\AlphaHive_V3_A_DATA_HEALTH_deliverables\agent_outputs\mimo\ARC-NEXT-RUNTIME-SCHEDULER-VERIFY-001.md`

## 先读

按顺序阅读：

1. `G:\Quant test\AGENTS.md`
2. `G:\Quant test\AlphaHive_V3\AGENTS.md`
3. `G:\Quant test\AlphaHive_V3\PROJECT_REQUIRED_READING.md`
4. `G:\Quant test\AlphaHive_V3\PROJECT_OPERATING_PLAYBOOK.md`
5. `G:\Quant test\AlphaHive_V3\agent_tasks\README.md`
6. 本任务文件

## 任务

只读核对 Hermes scheduler 在 checkpoint 剪枝后的连续性：

- `binance-hourly-pull` 是否仍 enabled、scheduled；
- 是否出现新的 pull report（必须晚于 `2026-07-16T06:37:22Z`）；
- 新报告若存在，核对 59 符号 × klines/funding/OI/taker、fail counters 和 freshness；
- checkpoint 8 个分区是否保持 59 键；
- `next_run_at`、`last_run_at`、lock 和进程状态是否一致；
- 若没有新报告，明确输出 `UNVERIFIED / WAITING_FOR_NEXT_HERMES_REPORT`。

## 硬边界

不启动、重试、停止或重启 Hermes；不修改 scheduler、lock、日志、checkpoint、DB、parquet、credentials 或 repo；不点火 trigger、不改 Paper。缺证据输出 `PARK`，不得用旧报告冒充 post-prune 运行证据。

## 报告

报告必须包含实际读取路径、UTC 时间、前后运行时间、逐维度证据、状态和 Owner/Codex 未决项。只能写入指定 Desktop 输出路径。
