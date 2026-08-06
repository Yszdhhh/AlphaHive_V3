# ARC-NEXT-F21-ARCH-REVIEW-001｜Agy / antigravity 派单

**agent:** Agy / antigravity  
**task_id:** `ARC-NEXT-F21-ARCH-REVIEW-001`  
**tier:** T1/T2 read-only architecture and contract review  
**owner:** Codex  
**formal output:** `C:\Users\10639\Desktop\AlphaHive_V3_A_DATA_HEALTH_deliverables\agent_outputs\antigravity\ARC-NEXT-F21-ARCH-REVIEW-001.md`

## 先读

按项目要求先读：

1. `G:\Quant test\AGENTS.md`
2. `G:\Quant test\AlphaHive_V3\AGENTS.md`
3. `G:\Quant test\AlphaHive_V3\PROJECT_REQUIRED_READING.md`
4. `G:\Quant test\AlphaHive_V3\PROJECT_OPERATING_PLAYBOOK.md`
5. `G:\Quant test\AlphaHive_V3\agent_tasks\README.md`
6. 本任务文件

## 任务目标

独立审阅当前 F2.1 OI/funding 历史回放闸，不修改任何文件。核对：

- `406f78f`、`044d4c4` 涉及的 `scripts/02_scan_anomalies.py`、`harness/lib/derivative_metrics.py`、`config/scan_rules.yaml` 和相关测试；
- `derivative_use_mode` 是否只允许显式且有界的历史回放，实时 now run 是否保持 `LIVE_DISABLED`；
- 90d 覆盖分级（`>=0.60 COMPUTED`、`0.30–<0.60 PARTIAL`、`<0.30 NOT_COMPUTED`）是否单一配置源、边界明确、行为测试覆盖；
- funding 单位归一化、8h 去重、OI 变化百分比的单位中立语义是否与 `config/data_contracts.yaml` v3 一致；
- F2.1 是否仍没有把 OI/funding 状态转成候选 trigger，也没有改变 Paper 或方向性输出；
- `OWNER_DECISIONS_NEEDED.md`、`KNOWN_LIMITATIONS.md` 和 `reports/PROMPT_RERENDER_AUDIT.md` 的边界描述是否一致。

## 硬边界

- 只读；不得写 repo、Desktop 以外目录、DB、parquet、checkpoint、scheduler 或日志；
- 不改阈值、schema、trigger、Paper、source path、凭证或交易路径；
- 不把审计结论写成 Owner 对 trigger 点火或 Paper 放行的批准；
- 若输入、commit 或测试证据不足，输出 `PARK` / `UNVERIFIED`，不得猜测。

## 报告要求

报告顶部写明 agent、task_id、UTC 时间、输入路径和 commit。按“事实 / 推断 / 建议 / Owner 决策”分栏，逐项给出 `PASS`、`ADVISORY` 或 `PARK`，保留文件和行号证据。聊天摘要不能替代正式文件。
