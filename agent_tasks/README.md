# F2.1 agent task pack

## 一句话派单

请先阅读 `G:\Quant test\AlphaHive_V3\agent_tasks\README.md`，再按你被派发的提示词执行；只把原始结果写入提示词指定的 Desktop 输出路径，不修改 `AlphaHive_V3/`。

## 共享必读

- `G:\Quant test\AGENTS.md`
- `G:\Quant test\AlphaHive_V3\AGENT_ORCHESTRATION_PROTOCOL.md`
- `G:\Quant test\AlphaHive_V3\PROJECT_CONSTITUTION.md`
- `G:\Quant test\AlphaHive_V3\GRAVEYARD.md`

## 角色边界

- `codex` 是唯一 repo 写者；代码、配置、测试、`_bus/` 均由 codex 整合和提交。
- `antigravity/Gemini`、`mimo`、`Sonnet` 只读或隔离执行，不改 repo，不碰真实交易。
- 研究产物必须标 `UNVERIFIED`；涉及凭证、代理或外部数据刷新时只报告，不尝试配置、不发请求、不改 DB。
- T3（阈值锁定、trigger 点火、paper 放行、数据源/凭证变化）只能进入 `OWNER_DECISIONS_NEEDED`，不能自行执行。

## 输出约定

原始输出根目录：

`C:\Users\10639\Desktop\AlphaHive_V3_F21_deliverables\agent_outputs\`

各 agent 只能写自己的目录：

- `mimo/`：数据刷新侦察原文
- `antigravity/`：研究提示词重渲与审计原文
- `sonnet/`：PC 端预审原文

完成后在输出文档顶部写明：`agent`、`task_id`、UTC 时间、读取过的输入、`GREEN/PARK/UNVERIFIED` 状态、未解决项。不要把摘要代替原文。

## 提示词索引

| task_id | 派给 | tier | 提示词 | 原始输出 |
|---|---|---|---|---|
| `F21-RECON-001` | mimo | GREEN / read-only | `agent_tasks/mimo__codex__data_refresh_recon.md` | `agent_outputs/mimo/DATA_REFRESH_RECON.md` |
| `F21-PROMPT-001` | antigravity | GREEN / isolated | `agent_tasks/antigravity__codex__prompt_rerender.md` | `agent_outputs/antigravity/` 下两份文件 |
| `F21-PREVIEW-001` | Sonnet | T3 boundary / review-only | `agent_tasks/sonnet__codex__f21_pre_review.md` | `agent_outputs/sonnet/SONNET_F21_PC_PRE_REVIEW.md` |

## 回传到 `_bus`

外部 agent 完成后，codex 原文验收并复制为：

- `_bus/mimo__codex__data_refresh_recon.md`
- `_bus/antigravity__codex__prompt_rerender.md`
- `_bus/sonnet__codex__f21_pre_review.md`

复制前保留原始文本和路径信息；若 agent 没有产物，codex 记录 `MISSING`，不得代写成已完成。
