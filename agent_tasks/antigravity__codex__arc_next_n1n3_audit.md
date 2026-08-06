# ARC-NEXT-N1-COVERAGE-001 — Antigravity / Gemini 3.1 Pro

> 本文件曾是未派发草案。当前正式 task_id 改为 `ARC-NEXT-N1-COVERAGE-001`，仅审 N1；N3 由 DeepSeek 独立终审。

**agent:** antigravity / Gemini 3.1 Pro  
**task_id:** `ARC-NEXT-N1-COVERAGE-001`  
**output:** `C:\Users\10639\Desktop\AlphaHive_V3_A_DATA_HEALTH_deliverables\agent_outputs\antigravity\ARC-NEXT-N1-COVERAGE-001.md`

**Tier:** T1/T2 independent audit  
**Owner boundary:** ARC-NEXT 2026-07-16  
**Repository:** `G:\Quant test\AlphaHive_V3`

## Objective

独立审阅 N1 canonical 逻辑视图的全文件覆盖深度和数据契约边界，识别 DoD 缺口并提供隔离测试候选。只审一手代码、配置和测试，不审 Codex 摘要。

## Required reading

先按顺序阅读 `G:\Quant test\AGENTS.md`、`G:\Quant test\AlphaHive_V3\AGENTS.md`、`G:\Quant test\AlphaHive_V3\PROJECT_REQUIRED_READING.md`、`G:\Quant test\AlphaHive_V3\PROJECT_OPERATING_PLAYBOOK.md`、`G:\Quant test\AlphaHive_V3\agent_tasks\README.md`，最后阅读本任务。只执行本 task_id；不得把未验证结论当成 Owner 批准。

## Scope

- 审阅 `harness/lib/canonical_data.py`、`tests/test_canonical_data.py`、`scripts/100_dual_source_coverage.py`，核对 N1 的 8 个维度×源统一 schema、来源 provenance、单位语义和 scanner source-path 不变性。
- 对 `scripts/100_dual_source_coverage.py` 的首文件采样限制做全文件验证设计；核对 8 个维度×源、provenance、单位语义、scanner source-path 不变性。
- 审阅 `config/data_contracts.yaml` 的文档路径与当前真实 CoinGlass/Binance 目录是否一致，只提出证据和文档修正建议，不修改配置。
- 可在隔离 Desktop 目录生成候选测试或小型只读审计脚本；不得修改仓库、切换 source path 或改变阈值。
- 明确区分“已有实现”“需要 Codex 收口”“属于 T3/D5 PARK”。

## Forbidden

- 不写 `AlphaHive_V3/`，不直接整合代码。
- 不审 N3，不实现点差/深度估计，不把 `WARN` 改成 `PASS`，不触发 Paper ALLOW。
- 不改变 `config/data_contracts.yaml` 的生产 source path，不做数据源切换。

## Deliverable

将原始报告只写入 `C:\Users\10639\Desktop\AlphaHive_V3_A_DATA_HEALTH_deliverables\agent_outputs\antigravity\ARC-NEXT-N1-COVERAGE-001.md`，附：审计输入清单、证据定位、N1 DoD 逐条结论、全文件覆盖候选测试、越界风险、限制、`SELF_CHECK` 和 `PARK` 清单。路径不匹配时直接 `PARK`。
