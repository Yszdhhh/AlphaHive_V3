# ARC-NEXT-N3-AUDIT-001 — DeepSeek V4

**agent:** DeepSeek V4  
**task_id:** `ARC-NEXT-N3-AUDIT-001`  
**tier:** T1/T2 read-only independent final audit  
**output:** `C:\Users\10639\Desktop\AlphaHive_V3_A_DATA_HEALTH_deliverables\agent_outputs\deepseek\ARC-NEXT-N3-AUDIT-001.md`

## Objective

独立终审现有 `liquidity_gate` 半闸实现，确认它只完成成交额/有效 bar 检查，点差/深度缺失时严格 fail-closed，且绝不产生伪 `PASS` 或 `paper_eligibility=ALLOW`。

## Required reading

先按顺序阅读：

1. `G:\Quant test\AGENTS.md`
2. `G:\Quant test\AlphaHive_V3\AGENTS.md`
3. `G:\Quant test\AlphaHive_V3\PROJECT_REQUIRED_READING.md`
4. `G:\Quant test\AlphaHive_V3\PROJECT_OPERATING_PLAYBOOK.md`
5. `G:\Quant test\AlphaHive_V3\agent_tasks\README.md`
6. 本任务文件

## Required inputs

- `G:\Quant test\AlphaHive_V3\harness\lib\deep_research_package.py`
- `G:\Quant test\AlphaHive_V3\tests\test_scan_anomalies.py`
- `G:\Quant test\AlphaHive_V3\tests\test_deep_research_package.py`
- `G:\Quant test\AlphaHive_V3\config\data_contracts.yaml`
- `G:\Quant test\AlphaHive_V3\config\scan_rules.yaml`
- `G:\Quant test\AlphaHive_V3\KNOWN_LIMITATIONS.md`
- 当前 git diff 和相关历史 commit

## Required checks

1. 成交额、有效 bar、缺失值和显式失败状态的正反例是否分别得到 `WARN`/`BLOCK`。
2. spread/depth 缺失是否恒为 `NOT_AVAILABLE` + `WARN`，是否完全禁止估算值冒充真实检查。
3. `paper_eligibility` 是否始终为 `REVIEW_REQUIRED` 或 `BLOCK`，不存在可达 `ALLOW`。
4. 当前 `KNOWN_LIMITATIONS.md` 是否准确描述“成交额半闸已实现、spread/depth 未实现”。
5. 是否存在任何 threshold、source path、trigger、Paper、credential、order-book 或交易行为越界。

## Hard boundaries

- 只读审计；不得修改仓库、Desktop 报告、数据库、Parquet、scheduler、Hermes、凭证或浏览器状态。
- 不运行真实拉取，不改变阈值，不触发 Paper/trigger，不提出未经证据支持的完整闸结论。
- 缺少输入或路径不一致时输出 `PARK`。

## Deliverable

只将原始报告写入指定 output path。报告头必须包含 agent、task_id、UTC 时间、精确输入、最终 verdict 和未决项。最终 verdict 只能是 `PASS_FOR-LIQUIDITY-HALF-GATE`、`PARK` 或 `FAIL`，并逐条提供文件/行号证据。
