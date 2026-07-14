# Handoff: T1 GREEN / isolated research artifact

**task_id:** `F21-PROMPT-001`  
**from:** antigravity/Gemini  
**to:** codex  
**Do not write:** `G:\Quant test\AlphaHive_V3\`  
**Outputs:**

- `C:\Users\10639\Desktop\AlphaHive_V3_F21_deliverables\agent_outputs\antigravity\RENDERED_RESEARCH_PROMPT.md`
- `C:\Users\10639\Desktop\AlphaHive_V3_F21_deliverables\agent_outputs\antigravity\PROMPT_RERENDER_AUDIT.md`

## 先读

1. `G:\Quant test\AlphaHive_V3\agent_tasks\README.md`
2. `G:\Quant test\AlphaHive_V3\AGENT_ORCHESTRATION_PROTOCOL.md`
3. `G:\Quant test\AlphaHive_V3\PROJECT_CONSTITUTION.md`
4. `G:\Quant test\AlphaHive_V3\GRAVEYARD.md`
5. 真契约：`G:\Quant test\AlphaHive_V3\config\deep_research_contract.yaml`
6. 相关渲染器、测试和 prompt fixture；先搜索实际入口，不要假设文件名。

## 任务

用生产真实 YAML（不是旧 mock fixture）重渲一份研究提示词，并审计渲染结果：

- 验证 `overall_evidence_allowed` 中不存在 `LONG_THESIS_STRONGER`、`SHORT_THESIS_STRONGER`。
- 如果真实 YAML 仍含方向性枚举，做最小、方向中立的修正建议并在审计中给出逐行 diff；不要自行放宽研究闸、不要点火 trigger、不要改 paper/执行路径。
- 明确渲染使用的契约版本、入口、输入 hash/时间和输出 hash/时间。
- 结果必须保留 provider neutrality、GRAVEYARD 约束和 `UNVERIFIED` 标记；不能把 OI/funding 缺失写成可用证据。

## 输出要求

`RENDERED_RESEARCH_PROMPT.md` 放完整重渲文本；`PROMPT_RERENDER_AUDIT.md` 放输入、命令/入口、枚举核验、逐行 diff（如有）、结论和未解决项。状态写 `GREEN` 或 `PARK`，不要写“已批准”。
