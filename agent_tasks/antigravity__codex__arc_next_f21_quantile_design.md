# ARC-NEXT-F21-QUANTILE-DESIGN-001｜Agy / antigravity 派单

**agent:** Agy / antigravity  
**task_id:** `ARC-NEXT-F21-QUANTILE-DESIGN-001`  
**tier:** T1/T2 read-only design review  
**formal output:** `C:\Users\10639\Desktop\AlphaHive_V3_A_DATA_HEALTH_deliverables\agent_outputs\antigravity\ARC-NEXT-F21-QUANTILE-DESIGN-001.md`

## 先读

按顺序阅读：

1. `G:\Quant test\AGENTS.md`
2. `G:\Quant test\AlphaHive_V3\AGENTS.md`
3. `G:\Quant test\AlphaHive_V3\PROJECT_REQUIRED_READING.md`
4. `G:\Quant test\AlphaHive_V3\PROJECT_OPERATING_PLAYBOOK.md`
5. `G:\Quant test\AlphaHive_V3\agent_tasks\README.md`
6. 本任务文件
7. `G:\Quant test\AlphaHive_V3\reports\F21_REVIEW_PACKAGE_20260716.md`
8. `C:\Users\10639\Desktop\AlphaHive_V3_A_DATA_HEALTH_deliverables\agent_outputs\deepseek\ARC-NEXT-F21-FINAL-AUDIT-001.md`

## 任务

对当前已定义但未激活的 OI/funding quantile 规则做只读设计审阅：

- 对照 `config/scan_rules.yaml` 中的 `oi_change_quantile_high`、`funding_quantile_high/low` 与候选构建循环；
- 明确当前未激活的事实、未来若要激活所需的最小代码入口、覆盖测试、回放验证和审计证据；
- 检查是否会破坏历史-only、LIVE_DISABLED、no-direction、Paper fail-closed 和数据单位语义；
- 给出 Owner T3 决策前的 DoD 清单，不给出点火批准。

## 硬边界

不得修改代码、阈值、schema、source path、Paper、trigger、credentials、DB、parquet、scheduler 或交易路径；不得写实现 patch；不得把设计建议写成已完成。证据不足输出 `PARK` / `UNVERIFIED`。

## 报告

报告必须区分事实、推断、最小实现建议和 Owner 决策项，包含文件/行号和真实 UTC 时间，只能写入指定 Desktop 输出路径。
