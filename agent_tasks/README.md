# AlphaHive agent task pack

F21 的历史派单状态、原文 provenance 和 `MISSING` 记录见 `agent_tasks/DISPATCH_MATRIX.md`。
当前的 Charter 弧线派单以 `agent_tasks/ARC_NEXT_STAGE_DISPATCH_PLAN.md` 为准。

## 一句话派单

请先阅读 `G:\Quant test\AlphaHive_V3\agent_tasks\README.md`，再按你被派发的提示词执行；只把原始结果写入提示词指定的 Desktop 输出路径，不修改 `AlphaHive_V3/`。

## 防串单规则（必须遵守）

所有 agent 共享同一个工作区，**但不共享任务所有权**。agent 不得从目录名、表格或其他 agent 的文件中自行选择任务，也不得执行未被调度消息明确点名的 task 文件。调度者必须在消息中写清楚 `task_id` 与完整任务文件路径；agent 只读这个任务文件及其列出的前置必读。若 task id、角色或输出路径与自身收到的调度消息不一致，立即停止并交付 `PARK` 说明，不猜测、不转派。

## 当前派单：Autonomous Arc Charter v1

`AUTONOMOUS_ARC_CHARTER_v1`（2026-07-14）是当前阶段的节奏附录。开始任何新单前，先读：

- `agent_tasks/ARC_NEXT_STAGE_DISPATCH_PLAN.md`（当前任务、顺序与边界）
- 本文件的共享必读与角色边界
- 自己被派发的 `agent_tasks/*arc*` 指令文件

新单不会覆盖 F21 的原文或 `MISSING` 记录。每个新 task id 有独立 Desktop 输出目录；收到外部原文前，codex 不得以 pc_fallback 冒充 agent provenance。

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

## v2 重新派单（本轮）

旧的 `F21-RECON-001` 与 `F21-PROMPT-001` 曾被记录为 `MISSING`，不得覆盖或冒充新原文。本轮使用新的 task id：

| task_id | 派给 | 五段式派单 | 原始输出 |
|---|---|---|---|
| `F21-RECON-002` | Mimo | `agent_tasks/mimo__codex__data_refresh_recon_v2.md` | `agent_outputs/mimo/F21-RECON-002_DATA_REFRESH_RECON.md` |
| `F21-PROMPT-002` | Agy / antigravity | `agent_tasks/antigravity__codex__prompt_rerender_v2.md` | `agent_outputs/antigravity/F21-PROMPT-002_*` |

这两单由 Owner 分别交给对应 agent；codex 只在收到原文后验收、复制到 `_bus/`、交叉核对并打包。

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
