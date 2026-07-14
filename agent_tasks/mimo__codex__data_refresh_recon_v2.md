# F21-RECON-002｜Mimo 派单

【角色】
你是 Mimo，角色是杂活/只读侦察；本单属于 F21 Batch B，T1 GREEN。codex 是唯一 repo 写者，你只负责本地数据刷新机制盘点。

【任务】
1. 先读取：
   - `G:\Quant test\AGENTS.md`
   - `G:\Quant test\AlphaHive_V3\PROJECT_CONSTITUTION.md`
   - `G:\Quant test\AlphaHive_V3\GRAVEYARD.md`
   - `G:\Quant test\AlphaHive_V3\AGENT_ORCHESTRATION_PROTOCOL.md`
2. 只读侦察 `C:\Users\10639\Desktop\加密\coinglass_db`：找出 OI/funding 的 puller、入库脚本、checkpoint/日志/排程机制和最后成功时间。
3. 估算 OI 缺口 `2026-05-26 → now`、funding 缺口 `2026-06-23 → now` 的天数、已有文件/最后时间戳、增量方式、重复范围，以及 720 天、频率、代理、凭证依赖。
4. 判断当前机制是仍排程、失败空转还是已弃置；所有缺失权限或外部状态写 `UNVERIFIED`，不得猜测“可运行”。
5. 报告必须明确：不实际刷新、不发 API 请求、不改 DB；任何 Owner 决策项单列。

【红线】
不得写 `G:\Quant test\AlphaHive_V3`、`_bus`、DB、parquet、checkpoint、lock 或日志；不得运行 puller/refresh 脚本；不得联网拉数据；不得读取、打印、复制或测试 token、secret、API key、代理凭证；不得改代理、Windows 排程、系统配置；不得把旧 `F21-RECON-001` 或 pc_fallback 内容冒充本单原文。

【产出路径】
只将一份完整 Markdown 原文写入：
`C:\Users\10639\Desktop\AlphaHive_V3_F21_deliverables\agent_outputs\mimo\F21-RECON-002_DATA_REFRESH_RECON.md`

【provenance】
文件顶部写明 `agent=Mimo`、`task_id=F21-RECON-002`、UTC 时间、读取路径、`GREEN/PARK/UNVERIFIED` 状态和未解决项。原文须包含脚本/机制清单、OI 表、funding 表、可行性判断、风险与 Owner 决策项，不得只交摘要。冲突时本地文件、代码、日志为准；无法完成就写明阻塞原因，不要静默缺失。codex 收到后保留你的原文并负责交叉核对、整合和打包。
