# ARC-B-PREVIEW-001｜Claude/Sonnet：M-B2 里程碑独立预审

**tier：** `T3-adjacent / read-only independent review`  
**from：** Claude/Sonnet  
**to：** codex  
**派发时机：** 不得现在执行。只在 codex 完成 M-B2、跑完回归并准备打包时派发。

## 开始前必须读

1. `G:\Quant test\AlphaHive_V3\agent_tasks\README.md`
2. `G:\Quant test\AlphaHive_V3\agent_tasks\ARC_NEXT_STAGE_DISPATCH_PLAN.md`
3. `G:\Quant test\AGENTS.md`
4. `G:\Quant test\AlphaHive_V3\AGENT_ORCHESTRATION_PROTOCOL.md`
5. `G:\Quant test\AlphaHive_V3\PROJECT_CONSTITUTION.md`
6. `G:\Quant test\AlphaHive_V3\GRAVEYARD.md`
7. `G:\Quant test\AlphaHive_V3\KARPATHY_GUIDELINES.md`
8. codex 提供的 M-B2 里程碑包：完整 commit diff、测试日志、变更前后相关文件和 `OWNER_DECISIONS_NEEDED.md`。

## 审计问题

独立审查并只回答以下问题：

1. funding 校验是否从 WARN 变为 BLOCK，且只使用 `data_contracts.yaml` 的 raw `0.0008`/`3.0`，没有第二套阈值或绕过路径？
2. identity/liquidity 是否为真实、有界计算，还是仍为占位/伪实现？缺失或不足时，`paper_eligibility` 是否必不为 `ALLOW`？
3. spread/depth 缺失时是否显式 `REVIEW_REQUIRED`，没有把估计 friction 当真实市场检查？
4. 回归是否覆盖上述负例，且现有中立方向与 live safety gate 无回归？
5. 是否碰到任何 T3 项：trigger 点火、paper 放行、数据源/凭证变更、阈值放宽、方向/执行路径？

每项结论标 `PASS`、`FAIL` 或 `PARK`，附精确文件/行号和必要的最小修复建议。不得批准 Owner 决策；`PASS` 仅代表实现证据充分。

## 严禁

- 不得修改仓库、交付包、`_bus/`、git、DB、配置、测试或系统设置。
- 不得运行数据刷新、联网、调用 API、接触 secret/proxy。
- 不得自行点火 trigger、改变 paper 状态、方向、仓位或飞书发送。

## 原始输出

只写：

`C:\Users\10639\Desktop\AlphaHive_V3_ArcB_MB2_deliverables\agent_outputs\claude\ARC-B-PREVIEW-001_INDEPENDENT_REVIEW.md`

顶部必须包含：实际 Claude/Sonnet 模型标识、`task_id=ARC-B-PREVIEW-001`、UTC 时间、全部输入路径、`PASS/FAIL/PARK` 总结、未解决项。若输入不全，交付 `PARK` 原文，不要补写或猜测缺失的 diff/测试结果。
