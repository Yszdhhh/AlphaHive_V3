# ARC-NEXT-N4-RUNTIME-001 — Mimo

**agent:** Mimo  
**task_id:** `ARC-NEXT-N4-RUNTIME-001`  
**output:** `C:\Users\10639\Desktop\AlphaHive_V3_A_DATA_HEALTH_deliverables\agent_outputs\mimo\ARC-NEXT-N4-RUNTIME-001.md`

**Tier:** T1, read-only evidence + isolated report  
**Owner boundary:** ARC-NEXT 2026-07-16  
**Repository:** `G:\Quant test\AlphaHive_V3`

## Objective

核对 Binance runtime checkpoint 是否确实从 73 条历史键收敛到 59 个有效 live symbols，并为 Codex 提供可回滚的剪枝执行清单。你不直接修改生产 checkpoint、不触发全量拉取。

## Required reading

先按顺序阅读 `G:\Quant test\AGENTS.md`、`G:\Quant test\AlphaHive_V3\AGENTS.md`、`G:\Quant test\AlphaHive_V3\PROJECT_REQUIRED_READING.md`、`G:\Quant test\AlphaHive_V3\PROJECT_OPERATING_PLAYBOOK.md`、`G:\Quant test\AlphaHive_V3\agent_tasks\README.md`，最后阅读本任务。只执行本 task_id。

## Scope

- 只读解析 `C:\Users\10639\Desktop\加密\binance_free_db\checkpoint_1h.json`；核对 `klines`、`funding`、`oi`、`taker_buysell` 及各 `_fail` 分区。
- 只读解析 `config/universe.json`，确认 effective 59、disabled 条目和 benchmark 角色。
- 输出 checkpoint keys − effective universe 的完整差异；逐分区确认差异一致。
- 检查是否存在备份/回滚所需的文件名、时间戳和权限条件；提出建议路径，不执行删除或移动。
- 如果能在不触发生产写入的前提下执行健康检查，只运行只读检查并记录命令与退出结果。

## Forbidden

- 不编辑 `AlphaHive_V3/`。
- 不修改、删除、移动或重写 checkpoint、parquet、lock、Hermes 配置。
- 不启动手工全量 refresh，不改 symbol universe，不触碰 trigger/Paper/凭证。

## Deliverable

将原始报告只写入 `C:\Users\10639\Desktop\AlphaHive_V3_A_DATA_HEALTH_deliverables\agent_outputs\mimo\ARC-NEXT-N4-RUNTIME-001.md`，必须包含 agent/task_id/UTC 时间、输入路径、命令/参数、73→59 证据、14 项差异、备份/回滚建议、限制、`SELF_CHECK` 和明确的 `PARK` 项。路径不存在或与本路径不一致时直接 `PARK`。
