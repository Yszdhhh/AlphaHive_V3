# Runtime + Quantile 外部派单消息 — 2026-07-16

以下是两条独立消息，必须分开发送；当前环境没有连接 Mimo/Agy CLI 或 Agent Orchestrator。

## Mimo

你是 Mimo，执行 `task_id=ARC-NEXT-RUNTIME-SCHEDULER-VERIFY-001`，tier=T1，只读。先阅读 `G:\Quant test\AGENTS.md`、`G:\Quant test\AlphaHive_V3\AGENTS.md`、`G:\Quant test\AlphaHive_V3\PROJECT_REQUIRED_READING.md`、`G:\Quant test\AlphaHive_V3\PROJECT_OPERATING_PLAYBOOK.md`、`G:\Quant test\AlphaHive_V3\agent_tasks\README.md`，以及任务文件 `G:\Quant test\AlphaHive_V3\agent_tasks\mimo__codex__arc_next_runtime_scheduler_verify.md`。只核对 checkpoint 剪枝后的 scheduler 连续性和是否有晚于 `2026-07-16T06:37:22Z` 的新 pull report。没有新报告就写 `UNVERIFIED / WAITING_FOR_NEXT_HERMES_REPORT`。正式报告只能写入 `C:\Users\10639\Desktop\AlphaHive_V3_A_DATA_HEALTH_deliverables\agent_outputs\mimo\ARC-NEXT-RUNTIME-SCHEDULER-VERIFY-001.md`。不得启动、重试、重启或修改 Hermes、scheduler、lock、日志、checkpoint、DB、parquet、credentials 或 repo。

## Agy / Gemini 3.1 Pro

你是 Agy / antigravity，执行 `task_id=ARC-NEXT-F21-QUANTILE-DESIGN-001`，tier=T1/T2，只读设计审阅。先阅读 `G:\Quant test\AGENTS.md`、`G:\Quant test\AlphaHive_V3\AGENTS.md`、`G:\Quant test\AlphaHive_V3\PROJECT_REQUIRED_READING.md`、`G:\Quant test\AlphaHive_V3\PROJECT_OPERATING_PLAYBOOK.md`、`G:\Quant test\AlphaHive_V3\agent_tasks\README.md`，以及任务文件 `G:\Quant test\AlphaHive_V3\agent_tasks\antigravity__codex__arc_next_f21_quantile_design.md`。核对 dormant OI/funding quantile 规则与候选循环，输出未来 T3 点火所需的最小实现、测试、回放和审计 DoD；不得修改代码、阈值、trigger、Paper、source、credentials 或交易路径。正式报告只能写入 `C:\Users\10639\Desktop\AlphaHive_V3_A_DATA_HEALTH_deliverables\agent_outputs\antigravity\ARC-NEXT-F21-QUANTILE-DESIGN-001.md`。
