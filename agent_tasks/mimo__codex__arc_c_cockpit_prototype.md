# ARC-C-COCKPIT-001｜Mimo：本地 receipt/candidate 卡片隔离原型

**tier：** `T1 GREEN / isolated static prototype`  
**from：** Mimo  
**to：** codex  
**开始条件：** 仅在 `ARC-A-RECON-001` 已交付，且 codex 确认可开始后执行。

## 开始前必须读

1. `G:\Quant test\AlphaHive_V3\agent_tasks\README.md`
2. `G:\Quant test\AlphaHive_V3\agent_tasks\ARC_NEXT_STAGE_DISPATCH_PLAN.md`
3. `G:\Quant test\AGENTS.md`
4. `G:\Quant test\AlphaHive_V3\AGENT_ORCHESTRATION_PROTOCOL.md`
5. `G:\Quant test\AlphaHive_V3\PROJECT_CONSTITUTION.md`
6. `G:\Quant test\AlphaHive_V3\GRAVEYARD.md`
7. `G:\Quant test\AlphaHive_V3\KARPATHY_GUIDELINES.md`

## 工作

用真实、本地、已存在的 candidate/receipt/交付包 JSON 或 Markdown 作为输入，做一个静态本地卡片原型。先在报告中列出实际选择的输入路径与字段；如果没有适合的结构化输入，标 `PARK` 并停下，不得造 mock 数据替代“真实数据跑通”。

原型必须：

- 从本地文件读取，并在卡片上明确显示输入文件、生成时间、状态、缺失/`UNVERIFIED`/`PARK`、human checks、provenance；
- 不生成方向结论、交易建议、仓位或 `ALLOW`；
- 不显示、读取或请求凭证；
- 可有一个纯本地的 `send_enabled: false` / `disabled` stub，但不可含真实 webhook URL、URL 模式示例、fetch/XHR/HTTP 调用或任何发送按钮的可用实现；
- 产出独立的 HTML/CSS/JS，所有文件只写 Desktop。它是候选，codex 后续才会审阅整合。

## 严禁

- 不得修改 repo、`_bus/`、数据、DB、配置、git、系统设置或历史交付包。
- 不得联网、调用 webhook/API、读取环境变量/secret/proxy。
- 不得开启发送、修改 `paper_eligibility`、修改 trigger，或涉及方向、仓位、纸面/真实执行。

## 原始输出

只写：

`C:\Users\10639\Desktop\AlphaHive_V3_ArcC_MC2_deliverables\agent_outputs\mimo\`

必交：`ARC-C-COCKPIT-001.html`、`.css`、`.js`、`ARC-C-COCKPIT-001_README.md`。README 顶部包含 `agent=Mimo`、task id、UTC 时间、真实输入路径、状态、未解决项和本地打开方法；必须明确“发送保持 disabled，未发生网络调用”。
