# ARC F2.1 外部派单消息 — 2026-07-16

**重要：以下是彼此独立的复制消息。一次只能复制其中一条，不能合并发送。**
当前 Codex 没有连接 Mimo/Agy/DeepSeek 的真实 CLI 或 Agent Orchestrator；本文件是精确派单 payload，不是已发送回执。Sonnet 不再作为后续派单模型。

## Mimo — 独立消息

你是 Mimo，执行 `task_id=ARC-NEXT-RUNTIME-POSTPRUNE-001`，tier=T1。先阅读 `G:\Quant test\AGENTS.md`、`G:\Quant test\AlphaHive_V3\AGENTS.md`、`G:\Quant test\AlphaHive_V3\PROJECT_REQUIRED_READING.md`、`G:\Quant test\AlphaHive_V3\PROJECT_OPERATING_PLAYBOOK.md`、`G:\Quant test\AlphaHive_V3\agent_tasks\README.md`，以及任务文件 `G:\Quant test\AlphaHive_V3\agent_tasks\mimo__codex__arc_next_runtime_postprune.md`。只执行这一单。正式报告只能写入 `C:\Users\10639\Desktop\AlphaHive_V3_A_DATA_HEALTH_deliverables\agent_outputs\mimo\ARC-NEXT-RUNTIME-POSTPRUNE-001.md`。只读核对 checkpoint 剪枝后的 59 键、失败计数、锁/调度和是否存在剪枝后的新 Hermes 报告；没有新报告就写 `UNVERIFIED / WAITING_FOR_NEXT_HERMES_REPORT`。不得启动 pull、不得写 repo/DB/parquet/checkpoint/lock/log/scheduler、不得碰 trigger/Paper/凭证。

## Agy / antigravity — 独立消息

你是 Agy / antigravity，执行 `task_id=ARC-NEXT-F21-ARCH-REVIEW-001`，tier=T1/T2。先阅读 `G:\Quant test\AGENTS.md`、`G:\Quant test\AlphaHive_V3\AGENTS.md`、`G:\Quant test\AlphaHive_V3\PROJECT_REQUIRED_READING.md`、`G:\Quant test\AlphaHive_V3\PROJECT_OPERATING_PLAYBOOK.md`、`G:\Quant test\AlphaHive_V3\agent_tasks\README.md`，以及任务文件 `G:\Quant test\AlphaHive_V3\agent_tasks\antigravity__codex__arc_next_f21_gate_review.md`。只执行这一单。正式报告只能写入 `C:\Users\10639\Desktop\AlphaHive_V3_A_DATA_HEALTH_deliverables\agent_outputs\antigravity\ARC-NEXT-F21-ARCH-REVIEW-001.md`。独立审 F2.1 历史-only derivative gate、覆盖分级、单位语义、no-trigger/no-ALLOW 边界；不得改 repo、阈值、schema、source、Paper、凭证或交易路径。路径缺失或证据不足就输出 `PARK`。

## Agy / Gemini 3.1 Pro — 后续独立消息

你是 Agy / antigravity，执行 `task_id=ARC-NEXT-F21-PC-PREVIEW-002`，tier=T1/T2 review-only。先阅读 `G:\Quant test\AGENTS.md`、`G:\Quant test\AlphaHive_V3\AGENTS.md`、`G:\Quant test\AlphaHive_V3\PROJECT_REQUIRED_READING.md`、`G:\Quant test\AlphaHive_V3\PROJECT_OPERATING_PLAYBOOK.md`、`G:\Quant test\AlphaHive_V3\agent_tasks\README.md`，以及任务文件 `G:\Quant test\AlphaHive_V3\agent_tasks\antigravity__codex__arc_next_f21_pc_preview.md`。只执行这一单。正式报告只能写入 `C:\Users\10639\Desktop\AlphaHive_V3_A_DATA_HEALTH_deliverables\agent_outputs\antigravity\ARC-NEXT-F21-PC-PREVIEW-002.md`。在已完成的 `ARC-NEXT-F21-ARCH-REVIEW-001` 基础上完成 PC 端预审，核对历史-only、LIVE_DISABLED、覆盖阈值、单位语义、no-trigger、no-ALLOW 和 T3 红线。不得修改任何文件或把预审写成 Owner 批准；路径或输入缺失就输出 `PARK`。

## DeepSeek — 延后独立消息

现在可以发送。Codex 已生成 review package：`G:\Quant test\AlphaHive_V3\reports\F21_REVIEW_PACKAGE_20260716.md`。你是 DeepSeek V4，执行 `task_id=ARC-NEXT-F21-FINAL-AUDIT-001`，tier=T1/T2。先阅读 `G:\Quant test\AGENTS.md`、`G:\Quant test\AlphaHive_V3\AGENTS.md`、`G:\Quant test\AlphaHive_V3\PROJECT_REQUIRED_READING.md`、`G:\Quant test\AlphaHive_V3\PROJECT_OPERATING_PLAYBOOK.md`、`G:\Quant test\AlphaHive_V3\agent_tasks\README.md`、任务文件 `G:\Quant test\AlphaHive_V3\agent_tasks\deepseek__codex__arc_next_f21_final_audit.md` 和 review package。正式报告只能写入 `C:\Users\10639\Desktop\AlphaHive_V3_A_DATA_HEALTH_deliverables\agent_outputs\deepseek\ARC-NEXT-F21-FINAL-AUDIT-001.md`。审计 Codex diff、340 项测试、Agy 两份正式报告和 Mimo runtime 报告；Sonnet 报告仅作为历史补充证据。不得改 repo、DB、parquet、checkpoint、scheduler、日志或凭证，不得点火 trigger，不得放行 Paper。缺失证据、scheduler blocker 或 T3 事项必须分别写 `PARK` / `UNVERIFIED`，不得自行修复或批准。
