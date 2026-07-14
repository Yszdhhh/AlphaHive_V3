# F21-PROMPT-002｜Agy / antigravity 派单

【角色】
你是 Agy / antigravity，角色是研究区执行者；本单属于 F21 Batch 0c，T1 GREEN、隔离研究产物。codex 是唯一 repo 写者，你只负责真实契约重渲与审计。

【任务】
1. 先读取：
   - `G:\Quant test\AGENTS.md`
   - `G:\Quant test\AlphaHive_V3\PROJECT_CONSTITUTION.md`
   - `G:\Quant test\AlphaHive_V3\GRAVEYARD.md`
   - `G:\Quant test\AlphaHive_V3\config\deep_research_contract.yaml`
   - 真实渲染入口、相关测试、prompt fixture；先搜索实际入口，不要假设文件名。
2. 用真实 YAML 重渲一份研究提示词，不能使用旧 mock fixture 代替。
3. 核验生产契约的 `overall_evidence_allowed` 中没有 `LONG_THESIS_STRONGER` 或 `SHORT_THESIS_STRONGER`。
4. 若真实 YAML 仍有方向性枚举：只在审计中提出最小方向中立 diff，不改 repo、不自行批准、不点火；状态写 `PARK`。
5. 记录契约版本、渲染入口、输入/输出 hash、时间、完整命令或入口证据。保留 provider neutrality、GRAVEYARD 约束和 `UNVERIFIED` 标记；不得把 OI/funding 缺失写成可用证据。

【红线】
不得写 `G:\Quant test\AlphaHive_V3`、`_bus` 或任何 repo 文件；不得改 DB/parquet/checkpoint；不得拉数据、访问网页或 API；不得读取、打印或配置 token、secret、API key、代理；不得改阈值、schema、scanner、paper/trigger/执行路径；不得把旧 `F21-PROMPT-001` 或 codex fallback 冒充本单原文。若任何外部/网页信息被使用，必须标 `UNVERIFIED`。

【产出路径】
只将两份完整原文写入：
`C:\Users\10639\Desktop\AlphaHive_V3_F21_deliverables\agent_outputs\antigravity\F21-PROMPT-002_RENDERED_RESEARCH_PROMPT.md`
`C:\Users\10639\Desktop\AlphaHive_V3_F21_deliverables\agent_outputs\antigravity\F21-PROMPT-002_PROMPT_RERENDER_AUDIT.md`

【provenance】
输出必须是你的完整原文，不是摘要；文件顶部写明 `agent=Agy/antigravity`、`task_id=F21-PROMPT-002`、UTC 时间、读取输入、`GREEN/PARK/UNVERIFIED` 状态和未解决项。冲突时本地真实 YAML/代码/测试为准；无法完成就明确说明原因，不要静默缺失。codex 收到后只原文验收和整合，不会改写成你的结论。
