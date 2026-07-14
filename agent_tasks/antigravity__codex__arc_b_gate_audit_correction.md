# ARC-B-AUDIT-002｜antigravity：Harness 审计事实校正

**tier：** `T1 GREEN / read-only correction`  
**from：** antigravity  
**to：** codex  
**前提：** 补正 `ARC-B-AUDIT-001`；不得改写其原文或任何 repo 文件。

## 开始前必须读

1. `G:\Quant test\AlphaHive_V3\agent_tasks\README.md`
2. `G:\Quant test\AlphaHive_V3\agent_tasks\ARC_NEXT_STAGE_DISPATCH_PLAN.md`
3. `G:\Quant test\AlphaHive_V3\agent_tasks\antigravity__codex__arc_b_gate_audit.md`
4. 原文：`C:\Users\10639\Desktop\AlphaHive_V3_ArcB_Audit_deliverables\agent_outputs\antigravity\ARC-B-AUDIT-001_GATE_AUDIT.md`
5. `harness/lib/deep_research_package.py`、`scripts/99_validate_schema.py`、`config/data_contracts.yaml`、`config/deep_research_contract.yaml` 与相关 source fixture/test。
6. 任务文件列出的治理前置文件。

## 只校正以下问题

1. 检查 `.py`、`.yaml`、`.json` 等**源文件**，不要把 `__pycache__/*.pyc` 当 source fixture 或建议删除它；删文件需 Owner 授权，不能列为本轮建议。
2. 明确区分 `VALID_RESEARCH_VERDICTS`（允许集合）和 `PROHIBITED_RESEARCH_VERDICTS`（禁止集合）。后者保留旧名称用于拒绝输入并不代表生产契约有方向性允许项。
3. 精确找到 Charter 所指 `tests` fixture 中 `DEEP_RESEARCH_CONTRACT.expected_output.allowed` 的实际位置；若当前不存在，给出可复现搜索范围与 `NOT_FOUND`，不要虚构残留。
4. 审核 P4 的缺口：`config/data_contracts.yaml` 当前是否真的声明“funding 按 8h 去重”的语义。若没有，指出唯一应添加的声明位置与一个行为测试，但不写 patch、不复制数值阈值。
5. 重列 M-B1/M-B2/M-B3 最小变更与测试，且不得建议触发、paper ALLOW、阈值放宽、方向性结论或删除文件。

## 原始输出

只写：

`C:\Users\10639\Desktop\AlphaHive_V3_ArcB_Audit_deliverables\agent_outputs\antigravity\ARC-B-AUDIT-002_FACT_CORRECTION.md`

开头写 `agent=antigravity`、`task_id=ARC-B-AUDIT-002`、UTC、输入、`GREEN/PARK/UNVERIFIED`、未决项。格式为“观察 → 精确证据路径/行号 → 最小建议 → 验证方式”。
