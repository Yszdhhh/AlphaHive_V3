# ARC-NEXT-F21-PC-PREVIEW-002｜Agy / antigravity 派单

**agent:** Agy / antigravity  
**task_id:** `ARC-NEXT-F21-PC-PREVIEW-002`  
**tier:** T1/T2 review-only  
**owner:** Codex  
**replaces:** Sonnet `ARC-NEXT-F21-PC-PREVIEW-001` for future dispatch  
**formal output:** `C:\Users\10639\Desktop\AlphaHive_V3_A_DATA_HEALTH_deliverables\agent_outputs\antigravity\ARC-NEXT-F21-PC-PREVIEW-002.md`

## 先读

按项目要求先读：

1. `G:\Quant test\AGENTS.md`
2. `G:\Quant test\AlphaHive_V3\AGENTS.md`
3. `G:\Quant test\AlphaHive_V3\PROJECT_REQUIRED_READING.md`
4. `G:\Quant test\AlphaHive_V3\PROJECT_OPERATING_PLAYBOOK.md`
5. `G:\Quant test\AlphaHive_V3\agent_tasks\README.md`
6. 本任务文件
7. `C:\Users\10639\Desktop\AlphaHive_V3_A_DATA_HEALTH_deliverables\agent_outputs\antigravity\ARC-NEXT-F21-ARCH-REVIEW-001.md`

## 任务目标

由 Agy / Gemini 3.1 Pro 替代 Sonnet，完成 F2.1 的独立 PC 预审。核对：

- 历史回放 cutoff 与 `LIVE_DISABLED` 是否在 PC 端入口一致执行；
- 90d 覆盖阈值、1h completed-bar cutoff、funding 单位和 OI 变化百分比语义；
- `data_contracts.yaml` v3 的 additive-only 兼容性；
- OI/funding trigger 是否仍未点火；
- `paper_eligibility=ALLOW` 是否仍被强制 PARK/REVIEW_REQUIRED；
- 是否存在 source、credential、方向或交易路径越界；
- 与 `OWNER_DECISIONS_NEEDED.md`、`KNOWN_LIMITATIONS.md`、`reports/PROMPT_RERENDER_AUDIT.md` 的边界描述是否一致。

## 硬边界

- 只读，不修改 repo、DB、parquet、checkpoint、scheduler、日志或 credentials；
- 不改阈值、schema、source path、trigger、Paper 或交易路径；
- 不把审阅结论写成 Owner 对 T3 的批准；
- 任务文件或输入缺失时输出 `PARK`，不得用 Sonnet 报告冒充 Agy 原文。

## 报告要求

报告顶部写明 agent=Agy/antigravity、task_id、UTC 时间、实际输入路径、审阅 commit 和状态。逐项给出 `PASS`、`ADVISORY`、`PARK`，引用文件/行号，单列 Owner 决策项。正式报告只能写入指定 Desktop 路径。
