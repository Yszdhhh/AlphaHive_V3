# ARC-NEXT 外部 agent 派单文本索引（2026-07-16）

> 说明：当前 Codex 运行环境未暴露 Mimo/Antigravity/DeepSeek CLI 或 Agent Orchestrator connector。以下三段必须分别发送给对应 agent，不能合并成一个任务或一个会话；它们不是已发送凭证。外部 agent 的正式回执必须来自对应 agent 会话或其指定 Desktop 交付目录。

## Mimo — N4 runtime

```text
你是 Mimo，执行 task_id=ARC-NEXT-N4-RUNTIME-001，tier=T1。先按顺序阅读 G:\Quant test\AGENTS.md、G:\Quant test\AlphaHive_V3\AGENTS.md、G:\Quant test\AlphaHive_V3\PROJECT_REQUIRED_READING.md、G:\Quant test\AlphaHive_V3\PROJECT_OPERATING_PLAYBOOK.md、G:\Quant test\AlphaHive_V3\agent_tasks\README.md，以及任务文件 G:\Quant test\AlphaHive_V3\agent_tasks\mimo__codex__arc_next_n4_runtime.md。只执行该 task。正式报告只能写入 C:\Users\10639\Desktop\AlphaHive_V3_A_DATA_HEALTH_deliverables\agent_outputs\mimo\ARC-NEXT-N4-RUNTIME-001.md。路径缺失或不匹配就输出 PARK；不得写 AlphaHive_V3、不得改 checkpoint、不得启动 Hermes。完成后回报正式报告路径、状态、证据和未决项。
```

## Antigravity / Gemini 3.1 Pro — N1 canonical coverage

```text
你是 antigravity / Gemini 3.1 Pro，执行 task_id=ARC-NEXT-N1-COVERAGE-001，tier=T1/T2。先按顺序阅读 G:\Quant test\AGENTS.md、G:\Quant test\AlphaHive_V3\AGENTS.md、G:\Quant test\AlphaHive_V3\PROJECT_REQUIRED_READING.md、G:\Quant test\AlphaHive_V3\PROJECT_OPERATING_PLAYBOOK.md、G:\Quant test\AlphaHive_V3\agent_tasks\README.md，以及任务文件 G:\Quant test\AlphaHive_V3\agent_tasks\antigravity__codex__arc_next_n1n3_audit.md。只执行该 task。正式报告只能写入 C:\Users\10639\Desktop\AlphaHive_V3_A_DATA_HEALTH_deliverables\agent_outputs\antigravity\ARC-NEXT-N1-COVERAGE-001.md。路径缺失或不匹配就输出 PARK；不得写 AlphaHive_V3、不得切 source path、不得改阈值或 Paper。完成后回报正式报告路径、状态、证据和未决项。
```

## DeepSeek V4 — N3 half-gate final audit

```text
你是 DeepSeek V4，执行 task_id=ARC-NEXT-N3-AUDIT-001，tier=T1/T2。先按顺序阅读 G:\Quant test\AGENTS.md、G:\Quant test\AlphaHive_V3\AGENTS.md、G:\Quant test\AlphaHive_V3\PROJECT_REQUIRED_READING.md、G:\Quant test\AlphaHive_V3\PROJECT_OPERATING_PLAYBOOK.md、G:\Quant test\AlphaHive_V3\agent_tasks\README.md，以及任务文件 G:\Quant test\AlphaHive_V3\agent_tasks\deepseek__codex__arc_next_n3_audit.md。只执行该 task。正式报告只能写入 C:\Users\10639\Desktop\AlphaHive_V3_A_DATA_HEALTH_deliverables\agent_outputs\deepseek\ARC-NEXT-N3-AUDIT-001.md。路径缺失或不匹配就输出 PARK；不得写 AlphaHive_V3、不得改阈值、不得切 source path、不得触发 Paper/trigger。完成后回报正式报告路径、状态、证据和未决项。
```

## Grok（仅 Owner 明确需要时）— gap-fill cost reconnaissance

```text
你是 Grok，执行 task_id=ARC-DATA-GAP-OPTIONS-001，tier=T1 read-only research。先按顺序阅读 G:\Quant test\AGENTS.md、G:\Quant test\AlphaHive_V3\AGENTS.md、G:\Quant test\AlphaHive_V3\PROJECT_REQUIRED_READING.md、G:\Quant test\AlphaHive_V3\PROJECT_OPERATING_PLAYBOOK.md、G:\Quant test\AlphaHive_V3\agent_tasks\README.md，以及任务文件 G:\Quant test\AlphaHive_V3\agent_tasks\grok__codex__arc_data_gap_options.md。只比较 OI/taker 三周缺口的免费/低价、公开归档、S3/供应商方案，不购买、不注册、不下载批量数据、不写库、不改 contract/source path、不回填。正式报告只能写入 C:\Users\10639\Desktop\AlphaHive_V3_A_DATA_HEALTH_deliverables\agent_outputs\grok\ARC-DATA-GAP-OPTIONS-001.md。路径缺失或不匹配就输出 PARK。完成后回报正式报告路径、状态、成本/证据比较和未决项。
```

## Codex 验收规则

- 只有从对应外部 agent 会话或指定 Desktop 路径拿到的原始产物，才算正式 handback。
- Codex 内部协作 agent 的结果只能作为辅助线索，不能替代外部 agent 原文或独立审计。
- 收到三份正式 handback 后，Codex 才能按 HB-1/HB-2/HB-3 整合；N2 reconciliation 与 N5 文档更新由 Codex 自己执行；任何 T3/D5 仍保持 PARK。

## Grok correction (send separately only for evidence-count rework)

```text
你是 Grok，执行 task_id=ARC-DATA-GAP-OPTIONS-002，tier=T1 read-only correction。先读取原 task 和正式原报告 ARC-DATA-GAP-OPTIONS-001.md。请只纠正报告内部“26×7/200”与“20×7/140 + 6 单日探针”的 HEAD/Checksum 计数矛盾，列出精确 symbol/date/request 数；无法从原始日志证明的数字标为 UNVERIFIED。保留 Binance Vision FREE_CANDIDATE 的有界结论，但不得声称完成 59×date 矩阵。不得覆盖原报告，不得下载批量数据、写库或回填。正式报告只能写入 C:\Users\10639\Desktop\AlphaHive_V3_A_DATA_HEALTH_deliverables\agent_outputs\grok\ARC-DATA-GAP-OPTIONS-002_CORRECTION.md；路径不匹配就 PARK。
```

## Correction dispatches (send separately only if rework is requested)

### Mimo — N4 arithmetic correction

```text
你是 Mimo，执行 task_id=ARC-NEXT-N4-RUNTIME-002，tier=T1 read-only correction。先读取原 task 和正式原报告 ARC-NEXT-N4-RUNTIME-001.md。请按当前 config/universe.json 的明确规则重新计算：66 symbols − 10 disabled_pull_symbols + 3 benchmark_symbols = 59；核对 73 checkpoint、14 extras、0 missing、_fail 全 0。不得覆盖原报告，不得修改任何生产文件。正式报告只能写入 C:\Users\10639\Desktop\AlphaHive_V3_A_DATA_HEALTH_deliverables\agent_outputs\mimo\ARC-NEXT-N4-RUNTIME-002_CORRECTION.md；路径不匹配就 PARK。
```

### DeepSeek — N3 audit correction

```text
你是 DeepSeek V4，执行 task_id=ARC-NEXT-N3-AUDIT-002，tier=T1/T2 read-only correction。先读取原 task 和正式原报告 ARC-NEXT-N3-AUDIT-001.md。请使用实际 UTC 时间戳重发独立 verdict，并重新核对 KNOWN_LIMITATIONS.md 是否准确区分“成交额/有效 bar 半闸已实现”和“spread/depth 未实现”；文档不准确时必须 PARK。不得覆盖原报告或修改仓库。正式报告只能写入 C:\Users\10639\Desktop\AlphaHive_V3_A_DATA_HEALTH_deliverables\agent_outputs\deepseek\ARC-NEXT-N3-AUDIT-002_CORRECTION.md；路径不匹配就 PARK。
```
