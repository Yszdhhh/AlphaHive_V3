# ARC-B-AUDIT-001｜antigravity：Harness 闸门独立设计审计

**tier：** `T1 GREEN / read-only independent audit`  
**from：** antigravity  
**to：** codex  
**目的：** 为 Charter 弧线 B 的 M-B1/M-B2/M-B3 提供独立、可审计的最小改动与回归设计；不改仓库。

## 开始前必须读

1. `G:\Quant test\AlphaHive_V3\agent_tasks\README.md`
2. `G:\Quant test\AlphaHive_V3\agent_tasks\ARC_NEXT_STAGE_DISPATCH_PLAN.md`
3. `G:\Quant test\AGENTS.md`
4. `G:\Quant test\AlphaHive_V3\AGENT_ORCHESTRATION_PROTOCOL.md`
5. `G:\Quant test\AlphaHive_V3\PROJECT_CONSTITUTION.md`
6. `G:\Quant test\AlphaHive_V3\GRAVEYARD.md`
7. `G:\Quant test\AlphaHive_V3\KARPATHY_GUIDELINES.md`
8. `C:\Users\10639\Desktop\AlphaHive_V3_F21_deliverables\AlphaHive_V3_F21_DELIVERABLE\agent_outputs\sonnet\SONNET_F21_PC_PRE_REVIEW.md`

## 审计范围

只读审查当前实现、配置与测试，重点是：

- `harness/lib/deep_research_package.py` 的 identity、liquidity 与 `paper_eligibility` 逻辑；
- `scripts/99_validate_schema.py` 与 funding 校验路径；
- `config/data_contracts.yaml`、`config/deep_research_contract.yaml`；
- 相关 `tests/` fixture 和单测。

输出一份设计审计，必须逐项包含：

1. F3：现有 funding 校验 WARN 到真正 BLOCK 的最小变更点，以及下限 `0.0008`、上限 `3.0` 不产生第二套口径的回归断言。
2. F2：现有 identity/liquidity 是否已经是真实的有界计算；若仍含占位或语义缺口，给出最小改动方案。必须证明“已实现但 identity/liquidity 不足”仍绝不产生 `paper_eligibility=ALLOW`。
3. P7：spread/depth 缺失时，为何必须 `REVIEW_REQUIRED`，不得调用 `friction_config` 的估计值充当真实点差/深度。列出正反例测试。
4. P4：funding 8h 去重应仅在 `config/data_contracts.yaml` 声明；指出当前最小且不重复真源的写入位置与需同步的行为测试。
5. fixture：找出所有残留的 `LONG_THESIS_STRONGER` / `SHORT_THESIS_STRONGER`，并将建议的中立集合与 `config/deep_research_contract.yaml` 精确对照。
6. 按 M-B1、M-B2、M-B3 分列测试清单、预计受影响文件与任何 T2/T3 邻接面。遇到歧义则 `PARK`，不要自行选择语义。

## 严禁

- 不得修改任何仓库文件、`_bus/`、git、配置、测试、DB、数据或交付包。
- 不得执行 scanner/puller、联网、调用 API，或接触凭证/代理。
- 不得批准/建议启用 trigger、paper ALLOW、任何方向、仓位或飞书发送。

## 原始输出

只写这一份原文：

`C:\Users\10639\Desktop\AlphaHive_V3_ArcB_Audit_deliverables\agent_outputs\antigravity\ARC-B-AUDIT-001_GATE_AUDIT.md`

开头必须包含：`agent=antigravity`、`task_id=ARC-B-AUDIT-001`、UTC 时间、已读输入、`GREEN/PARK/UNVERIFIED`、未解决项。采用“观察 → 精确证据路径/行号 → 最小建议 → 需验证测试”的格式；不要提供未验证的结论或直接 patch。
