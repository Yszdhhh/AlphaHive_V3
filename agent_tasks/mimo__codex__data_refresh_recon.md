# Handoff: T1 GREEN / read-only reconnaissance

**task_id:** `F21-RECON-001`  
**from:** mimo  
**to:** codex  
**Do not write:** `G:\Quant test\AlphaHive_V3\`  
**Output:** `C:\Users\10639\Desktop\AlphaHive_V3_F21_deliverables\agent_outputs\mimo\DATA_REFRESH_RECON.md`

## 先读

1. `G:\Quant test\AlphaHive_V3\agent_tasks\README.md`
2. `G:\Quant test\AlphaHive_V3\AGENT_ORCHESTRATION_PROTOCOL.md`
3. `G:\Quant test\AlphaHive_V3\PROJECT_CONSTITUTION.md`
4. `G:\Quant test\AlphaHive_V3\GRAVEYARD.md`

## 任务

只读侦察 `C:\Users\10639\Desktop\加密\coinglass_db` 的 OI/funding 衍生数据：

- 找出 OI/funding 由哪个脚本或机制拉取、入库脚本在哪里、在不触碰凭证的前提下判断脚本是否仍可运行。
- 估算增量缺口：OI 从 `2026-05-26` 到当前，funding 从 `2026-06-23` 到当前；报告天数、已有文件/最后时间戳、增量方式和潜在重复范围。
- 只做静态/本地检查，评估 720 天限制、频率限制、代理依赖和凭证依赖；不发 API 请求、不启动刷新、不改 DB、不读取或打印 token/key/代理密钥。
- 若任何结论依赖缺失权限或外部状态，明确写 `UNVERIFIED`，不要猜测。

## 输出必须包含

用 Markdown 写完整原文到指定路径，包含：检查时间、读取路径、脚本/机制清单、OI、funding 两个缺口表、可行性判断、风险/凭证红线、建议的 Owner 决策项。结论只能是侦察结论，不能写成“已刷新”。
