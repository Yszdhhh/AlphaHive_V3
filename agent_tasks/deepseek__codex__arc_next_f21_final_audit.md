# ARC-NEXT-F21-FINAL-AUDIT-001｜DeepSeek 派单

**agent:** DeepSeek V4  
**task_id:** `ARC-NEXT-F21-FINAL-AUDIT-001`  
**tier:** T1/T2 independent final audit  
**owner:** Codex  
**formal output:** `C:\Users\10639\Desktop\AlphaHive_V3_A_DATA_HEALTH_deliverables\agent_outputs\deepseek\ARC-NEXT-F21-FINAL-AUDIT-001.md`

## 派发时机

本单必须在 Codex 完成 F2.1 review package，并收到 Agy 架构审计、Agy PC 预审和 Mimo runtime 报告后再派发。Sonnet 报告只作为历史补充证据，不是后续派发前置条件。不得提前以摘要代替输入。

## 先读

按项目要求先读：

1. `G:\Quant test\AGENTS.md`
2. `G:\Quant test\AlphaHive_V3\AGENTS.md`
3. `G:\Quant test\AlphaHive_V3\PROJECT_REQUIRED_READING.md`
4. `G:\Quant test\AlphaHive_V3\PROJECT_OPERATING_PLAYBOOK.md`
5. `G:\Quant test\AlphaHive_V3\agent_tasks\README.md`
6. 本任务文件
7. Codex 提供的 F2.1 review package 路径

## 任务目标

独立终审 F2.1 package：

- 核对 Codex diff、测试、Agy 架构审计、Agy PC 预审和 Mimo runtime 报告是否引用真实输入；
- 核对历史-only、覆盖分级、单位语义、fail-closed 和 no-ALLOW 边界；
- 扫描是否存在 trigger 点火、阈值改动、source switch、credential、Paper 或交易路径越界；
- 对任何缺失证据、矛盾或过度结论给出 `PARK` / `FAIL`，不得自行修复 repo。

## 硬边界与报告

只读，不写 repo、DB、parquet、checkpoint、scheduler、日志或凭证。报告顶部写明 agent、task_id、UTC 时间、所有输入路径、测试命令、最终 verdict 和 Owner 决策项。最终审计不是 Owner 对 T3 的批准。
