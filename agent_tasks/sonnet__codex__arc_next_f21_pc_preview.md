# ARC-NEXT-F21-PC-PREVIEW-001｜Sonnet 派单

**agent:** Sonnet  
**task_id:** `ARC-NEXT-F21-PC-PREVIEW-001`  
**tier:** T1/T2 review-only, T3 boundary pre-review  
**owner:** Codex  
**formal output:** `C:\Users\10639\Desktop\AlphaHive_V3_A_DATA_HEALTH_deliverables\agent_outputs\sonnet\ARC-NEXT-F21-PC-PREVIEW-001.md`

## 先读

按项目要求先读：

1. `G:\Quant test\AGENTS.md`
2. `G:\Quant test\AlphaHive_V3\AGENTS.md`
3. `G:\Quant test\AlphaHive_V3\PROJECT_REQUIRED_READING.md`
4. `G:\Quant test\AlphaHive_V3\PROJECT_OPERATING_PLAYBOOK.md`
5. `G:\Quant test\AlphaHive_V3\agent_tasks\README.md`
6. 本任务文件

## 任务目标

对 F2.1 做独立 PC 端预审，为后续 Codex review package 提供输入：

- 历史回放 OI/funding 是否在 scan date 超过 `2026-05-31T23:59:59Z` 时保持禁用；
- 90d 覆盖阈值、1h completed-bar cutoff、funding 单位、OI 变化百分比和 schema v3 兼容性是否可解释；
- 研究包中的 OI/funding trigger 是否仍为未点火状态；
- Paper `ALLOW`、方向性 thesis、source switch、credentials 和交易路径是否没有被间接放行；
- 测试是否覆盖边界和失败闭锁路径。

## 硬边界

- 不修改 repo 或任何生产/运行时文件；
- 不启动真实刷新，不点火 trigger，不改变 Paper 状态，不改阈值；
- 不把预审写成 Owner 签字；
- 输入或历史包缺失时输出 `PARK`，不得用旧 pc_fallback 冒充新证据。

## 报告要求

报告顶部写明 agent、task_id、UTC 时间、输入路径、审阅 commit 和状态。逐项给出 `PASS`、`ADVISORY`、`PARK`，引用文件/行号，单列 Owner 决策项。聊天摘要不能替代正式文件。
