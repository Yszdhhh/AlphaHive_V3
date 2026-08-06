# ARC 下一波 F2.1 派单计划 — 2026-07-16

**状态：** `PAYLOAD_PREPARED_EXTERNAL_DISPATCH_PENDING`  
**范围：** F2.1 OI/funding 历史回放闸的独立预审与运行连续性核对。  
**单写者：** 只有 Codex 可修改 `G:\Quant test\AlphaHive_V3`；外部 Agent 只能写各自指定的 Desktop 报告。  
**明确不做：** 不补数据、不切换 scanner source、不点火 OI/funding trigger、不放行 Paper、不改阈值/凭证/交易路径。

## 任务表

| 顺序 | agent | task_id | tier | 任务文件 | 精确输出 |
|---|---|---|---|---|---|
| 并行 A | Mimo | `ARC-NEXT-RUNTIME-POSTPRUNE-001` | T1 | `agent_tasks/mimo__codex__arc_next_runtime_postprune.md` | `C:\Users\10639\Desktop\AlphaHive_V3_A_DATA_HEALTH_deliverables\agent_outputs\mimo\ARC-NEXT-RUNTIME-POSTPRUNE-001.md` |
| 并行 B | Agy / antigravity | `ARC-NEXT-F21-ARCH-REVIEW-001` | T1/T2 | `agent_tasks/antigravity__codex__arc_next_f21_gate_review.md` | `C:\Users\10639\Desktop\AlphaHive_V3_A_DATA_HEALTH_deliverables\agent_outputs\antigravity\ARC-NEXT-F21-ARCH-REVIEW-001.md` |
| 后续 B2 | Agy / antigravity | `ARC-NEXT-F21-PC-PREVIEW-002` | T1/T2 | `agent_tasks/antigravity__codex__arc_next_f21_pc_preview.md` | `C:\Users\10639\Desktop\AlphaHive_V3_A_DATA_HEALTH_deliverables\agent_outputs\antigravity\ARC-NEXT-F21-PC-PREVIEW-002.md` |
| 顺序 C | DeepSeek V4 | `ARC-NEXT-F21-FINAL-AUDIT-001` | T1/T2 | `agent_tasks/deepseek__codex__arc_next_f21_final_audit.md` | `C:\Users\10639\Desktop\AlphaHive_V3_A_DATA_HEALTH_deliverables\agent_outputs\deepseek\ARC-NEXT-F21-FINAL-AUDIT-001.md` |

## 先后关系

1. Mimo 与 Agy 架构审计已完成；Mimo 的 post-prune 结论为 `UNVERIFIED`，不能升级为 GREEN。
2. 后续只向 Agy / Gemini 3.1 Pro 单独发送 `ARC-NEXT-F21-PC-PREVIEW-002`，替代 Sonnet；必须使用新的 task_id 和新的输出文件。
3. Codex 验收 Agy PC 预审原文，整理 F2.1 review package，运行全量测试并记录结果。
4. 只有 package 完成后才派 DeepSeek；DeepSeek 不得审自己或另一 Agent 的摘要。
5. DeepSeek 通过后，Codex 更新里程碑与 Owner 决策项；是否点火 trigger 仍需 Owner 单独 T3 签字。

## 当前 Codex 工作

- 读取并核对 F2.1 代码、测试、`scan_rules.yaml`、`data_contracts.yaml v3`、`KNOWN_LIMITATIONS.md` 和 prompt rerender audit；
- 收到并验收 A/B/C 后生成只读 review package；
- 维持 `LIVE_DERIVATIVE_USE_DISABLED`、`paper_eligibility != ALLOW` 和 no-direction 约束；
- 不执行任何数据刷新或历史回填。

## 不派发

- Sonnet：本次报告保留为补充证据，但以后不再派 Sonnet；PC 预审由 Agy / Gemini 3.1 Pro 接替。
- Grok：当前数据补缺已冻结，不派免费数据回填单；Vision 仍为 `PARK / UNVERIFIED`。
- 任何 source switch、S3 gap-fill、OI/funding trigger ignition、Paper ALLOW、credentials、proxy、order-book 或真实交易任务：全部 `OWNER_DECISIONS_NEEDED`。
