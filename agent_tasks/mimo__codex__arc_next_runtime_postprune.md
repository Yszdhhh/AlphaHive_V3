# ARC-NEXT-RUNTIME-POSTPRUNE-001｜Mimo 派单

**agent:** Mimo  
**task_id:** `ARC-NEXT-RUNTIME-POSTPRUNE-001`  
**tier:** T1 read-only runtime reconciliation  
**owner:** Codex  
**formal output:** `C:\Users\10639\Desktop\AlphaHive_V3_A_DATA_HEALTH_deliverables\agent_outputs\mimo\ARC-NEXT-RUNTIME-POSTPRUNE-001.md`

## 先读

按项目要求先读：

1. `G:\Quant test\AGENTS.md`
2. `G:\Quant test\AlphaHive_V3\AGENTS.md`
3. `G:\Quant test\AlphaHive_V3\PROJECT_REQUIRED_READING.md`
4. `G:\Quant test\AlphaHive_V3\PROJECT_OPERATING_PLAYBOOK.md`
5. `G:\Quant test\AlphaHive_V3\agent_tasks\README.md`
6. 本任务文件

## 任务目标

核对 Codex 于 2026-07-16 完成 checkpoint 备份/剪枝后的运行连续性。只读检查：

- `C:\Users\10639\Desktop\加密\binance_free_db\checkpoint_1h.json` 是否在 8 个分区均为 59 个有效键；
- 59 个有效符号是否仍无 missing，所有 `_fail` 是否为 0；
- 是否存在剪枝后时间点的新 Hermes pull report；若没有，明确写 `UNVERIFIED / WAITING_FOR_NEXT_HERMES_REPORT`，不得把旧报告当成 post-prune 证据；
- `C:\Users\10639\AppData\Local\hermes\cron\jobs.json` 的调度状态、运行锁和最近报告状态；
- 对照备份 `checkpoint_1h.pre_n4_20260716T063722Z.json`，只验证可追溯性。

## 硬边界

- 不启动 pull、retry 或 refresh；不改 DB、parquet、checkpoint、lock、日志、scheduler 或 Hermes 脚本；
- 不读取、打印或测试任何 token、secret、API key、代理凭证；
- 不修改 `G:\Quant test\AlphaHive_V3\`；
- 不判断或批准 trigger、Paper、source switch、gap-fill；
- 任何缺少的新运行证据必须写 `UNVERIFIED` 或 `PARK`。

## 报告要求

报告顶部写明 agent、task_id、UTC 时间、所有实际读取路径、状态（`GREEN` / `UNVERIFIED` / `PARK`）、证据和未决项。必须区分“剪枝后静态验证”和“下一次 Hermes 运行验证”。聊天摘要不能替代正式文件。
