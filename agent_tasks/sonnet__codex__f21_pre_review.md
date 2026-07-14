# Handoff: T3 boundary / review-only

**task_id:** `F21-PREVIEW-001`  
**from:** Sonnet  
**to:** codex  
**Do not write:** `G:\Quant test\AlphaHive_V3\`  
**Output:** `C:\Users\10639\Desktop\AlphaHive_V3_F21_deliverables\agent_outputs\sonnet\SONNET_F21_PC_PRE_REVIEW.md`

## 先读

1. `G:\Quant test\AlphaHive_V3\agent_tasks\README.md`
2. `G:\Quant test\AlphaHive_V3\AGENT_ORCHESTRATION_PROTOCOL.md`
3. `G:\Quant test\AlphaHive_V3\PROJECT_CONSTITUTION.md`
4. `G:\Quant test\AlphaHive_V3\GRAVEYARD.md`
5. codex 已完成的 F2.1 diff、测试结果、`OWNER_DECISIONS_NEEDED` 和 prompt rerender audit。

## 任务

对历史回放 OI/funding 开发做 PC 端独立预审，不修改任何文件：

- 检查 OI/funding 只在历史回放（scan date ≤ `2026-05` 且有数据）验证，实时 now run 不伪装为可用。
- 检查 90d 有效点阈值分级（≥60% `COMPUTED`、30–60% `PARTIAL`、<30% `NOT_COMPUTED`）是否可配置、边界是否明确、测试是否覆盖。
- 检查 1h 完成 bar cutoff、funding 单位、OI 变化百分比/绝对值语义、schema v2 additive 和旧消费者兼容。
- 明确所有 T3：实际 OI/funding 候选 trigger 点火、paper 联动、任何方向性 thesis 变化；这些只能 `PARK`，不得批准。

## 输出要求

报告写明审阅 commit、输入文件、逐项 PASS/FAIL/PARK、证据引用、发现的问题和建议。不得改代码、不得运行真实刷新、不得将预审写成 Owner 签字或 trigger 批准。
