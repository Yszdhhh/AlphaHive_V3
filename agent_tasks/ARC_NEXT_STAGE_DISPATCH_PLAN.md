# Autonomous Arc Charter v1 — 下一阶段派单计划

> **Historical dispatch baseline — 2026-07-14.** Preserve task IDs and evidence in this file, but do not treat its initial `T1_PREPARATION` state or its pre-approval data-refresh prohibition as the current operating state. Read `PROJECT_REQUIRED_READING.md`, `OWNER_APPROVALS.md`, and the actual task-specific dispatch before acting.

**状态：** `ARC-NEXT_AUTHORIZED`（N1–N5 已获限范围 T1/T2 授权；T3/D5 继续 PARK）
**生效范围：** `G:\Quant test\AlphaHive_V3`  
**单写者：** 只有 codex 可修改仓库、配置、测试、`_bus/` 或 git。所有外部 agent 只可读取输入，并向各自指定的 Desktop 目录写原始产物。

本计划落实 `AUTONOMOUS_ARC_CHARTER_v1` 的 A/B/C 三条弧线；不替代项目宪法、墓地、编排协议或 Charter。冲突时，以那些治理文件和 Charter 为准。

## ARC-NEXT agent dispatch overlay — 2026-07-16

本节覆盖上方的历史派单基线，仅适用于 N1–N5。单写者、隔离产物、handback 和 T3 红线保持不变。

**执行通道说明：** 本文件和三个 task file 是外部派单 payload，不是发送回执。当前 Codex 运行环境未连接 Mimo/Grok/Antigravity/DeepSeek CLI 或 Agent Orchestrator；正式执行须由 Owner 在对应 agent 会话/Orchestrator 中发送各自 task file 的独立原文。Codex 内部协作结果不得冒充外部 agent handback。

| agent | 任务 | Tier | 允许范围 | 交付 |
|---|---|---|---|---|
| Mimo | `ARC-NEXT-N4-RUNTIME-001` | T1 | 只读核对 73→59 checkpoint、生成剪枝清单、验证下一次 Hermes 运行条件；不得直接改生产 checkpoint | `agent_outputs/mimo/ARC-NEXT-N4-RUNTIME-001.md` |
| Antigravity / Gemini 3.1 Pro | `ARC-NEXT-N1-COVERAGE-001` | T1/T2 | 独立审 canonical 视图全文件覆盖和契约边界；不得切源或改 paper | `agent_outputs/antigravity/ARC-NEXT-N1-COVERAGE-001.md` |
| DeepSeek V4 | `ARC-NEXT-N3-AUDIT-001` | T1/T2 | 独立终审 liquidity 半闸 fail-closed 语义；不得改阈值、切源或放行 paper | `agent_outputs/deepseek/ARC-NEXT-N3-AUDIT-001.md` |

**当前派单状态：** `FORMAL_HAND_BACKS_ACCEPTED_CODEX_CLOSURE_COMPLETE`。上表保留原始目标与隔离路径，不表示 Codex 内部协作可冒充外部 CLI。Grok 不在当前固定角色表中；N2 reconciliation 已由 Codex 完成，若 Owner 另行授权 Grok，仍须新增独立 task_id 和 `agent_outputs/grok/` 路径。

**可选成本侦察：** 若 Owner 要求评估三周 OI/taker gap-fill，可单独启用 `ARC-DATA-GAP-OPTIONS-001`（Grok，T1 只读）及其独立输出 `agent_outputs/grok/ARC-DATA-GAP-OPTIONS-001.md`。该单只比较免费/低价路径，不授权回填、购买、下载、写库或 source switch。

Grok 已提交该可选报告；方向性结论仍有价值，但因报告内部的 HEAD 矩阵计数矛盾暂 `PARK / CORRECTION_REQUIRED`。纠正单只核对符号/日期/请求数，不扩大范围。全量 59×date 矩阵、ZIP 内容 schema、OI 单位和 taker 语义对齐仍未验证，不得据此启动 gap-fill。

**本批回传纠正单：** Mimo `ARC-NEXT-N4-RUNTIME-002` 已接受为 `GREEN`，实际 checkpoint 备份/剪枝已由 Codex 执行；DeepSeek `ARC-NEXT-N3-AUDIT-002` 已接受为 `ACCEPTED_WITH_ADVISORY_CORRECTION`，`KNOWN_LIMITATIONS.md` 修正已由 Codex 收口。Agy N1 继续为 `ACCEPTED_WITH_ADVISORY_CORRECTION`，全文件覆盖和 data-contract 文档修正已由 Codex 收口。

**Codex HB-1/HB-2/HB-3 closure — 2026-07-16：** N1 full-file coverage、N2 funding overlap、N3 limitation wording、N4 checkpoint prune 和 N5 contract v3 已完成并留存于 `reports/`。N2 仍是只读对齐证据；Grok Vision 候选、OI/taker gap-fill、scanner source switch、trigger 和 Paper ALLOW 继续 `PARK`。

### 派单顺序

1. Mimo、Antigravity/Gemini、DeepSeek 三单可并行，各写自己的 Desktop 子目录。
2. Codex 自行完成 N2 reconciliation，并保留逐符号原始证据。
3. Codex 验收三份正式原文和 N2 结果后，才整合仓库并执行 HB-1/HB-2/HB-3。

### Agent handback 纪律

- 各 agent 只能写各自 Desktop 交付目录，不写 `AlphaHive_V3/`。
- 缺少真实数据或发现 T3 越界时输出 `PARK`，不要用估计值补齐。
- 原始产物必须包含输入路径、运行时间、命令/参数、结果、限制和 `SELF_CHECK`。
- provider/model 结论不是 Owner 决策；所有 source switch、gap-fill、trigger、Paper ALLOW、order-book 事项继续写入 `OWNER_DECISIONS_NEEDED.md`。

## 先后关系

1. Mimo `ARC-A-RECON-002` 与 antigravity `ARC-B-AUDIT-002` 已经 codex 原始文件复核通过，分别作为 M-A1 映射证据和 M-B1–M-B3 设计审计证据；原 `-001` 仍保留，不能单独引用。
2. DeepSeek `ARC-C-PACK-002` 的模板、diff 标记与字段校验已有进展，但仍可能覆盖同名 DELIVERABLE/log，也未排除历史 Desktop 交付包作为输出目录，结论为 `CODEx_FIX_REQUIRED`。不发 `-003`；由 codex 在 C1 单写者整合时修正。
3. Mimo 的 `ARC-C-COCKPIT-001` 继续等待 C1 helper 被 codex 验收后再开始；它只做本地、无发送的隔离原型。
4. Claude/Sonnet 的 `ARC-B-PREVIEW-001` **现在不派**。仅在 codex 完成 M-B2 改动、测试与里程碑包之后，且打包前派发。它只审计，不编码。
5. codex 验收每份原文、决定是否整合，并在每个 M-A1/M-B1/M-B2/M-B3/M-C1/M-C2 停点独立打包。未收到原文即记录 `MISSING`，不等待也不代写。

## 调度协议（防串单）

共享工作区不等于共享执行授权。每次只向一个 agent 发送一个明确的 `task_id` 和完整任务文件路径；agent 只能执行收到消息点名的那一单，不能从本计划自行领取、转发或合并其它任务。模型身份与 task 文件标题不一致、输出目录冲突或前置输入缺失时，输出 `PARK` 原文并停止。

## 任务分配

| task_id | 角色 | 对应弧线/里程碑 | 属性 | 指令文件 | 是否立即派发 |
|---|---|---|---|---|---|
| `ARC-A-RECON-001` | Mimo | A / M-A1 前置证据 | T1、只读 | `mimo__codex__arc_a_binance_recon.md` | 是 |
| `ARC-B-AUDIT-001` | antigravity | B / M-B1、M-B2 设计审计 | T1、只读、独立 | `antigravity__codex__arc_b_gate_audit.md` | 是 |
| `ARC-C-PACK-001` | DeepSeek V4 | C / M-C1 隔离 helper 候选 | T1、隔离代码 | `deepseek__codex__arc_c_pack_helper.md` | 是 |
| `ARC-C-COCKPIT-001` | Mimo | C / M-C2 隔离静态原型 | T1、隔离代码 | `mimo__codex__arc_c_cockpit_prototype.md` | 后续 |
| `ARC-B-PREVIEW-001` | Claude/Sonnet | B / M-B2 打包前独立预审 | T3 邻接、只读 | `claude__codex__arc_b_pre_review.md` | 仅 M-B2 后 |

## 首轮复核与修正单

| 原 task_id | 复核结论 | 必须修正的事实/缺口 | 修正 task_id | 指令文件 |
|---|---|---|---|---|
| `ARC-A-RECON-001` | `REWORK_REQUIRED` | funding ×100 后为 `0.0041725 >= 0.0008`，原报告反向判断；kline UTC 日期误换算；Task Scheduler `Last Result=1` 不可标为 success。 | `ARC-A-RECON-002` | `mimo__codex__arc_a_binance_recon_correction.md` |
| `ARC-B-AUDIT-001` | `REWORK_REQUIRED` | 禁止枚举不等于允许枚举；`.pyc` 不是待清理 fixture，且删除它碰红线；P4 的 8h 去重单一真源声明没有被审计到。 | `ARC-B-AUDIT-002` | `antigravity__codex__arc_b_gate_audit_correction.md` |
| `ARC-C-PACK-001` | `REWORK_REQUIRED` | helper 未生成命名后的 `DELIVERABLE.md`，七项和完整 diff 只做关键词/非空检查，输出路径没有安全边界。 | `ARC-C-PACK-002` | `deepseek__codex__arc_c_pack_helper_correction.md` |

`ARC-C-PACK-002` 在修正模板、基本 patch 结构和部分字段证据后，仍被 codex 复核为 `CODEx_FIX_REQUIRED`：`create`/日志写入可覆盖同名文件，路径检查未排除已有历史 Desktop 交付包。该候选不直接整合；不再外派第三轮，由 codex 在 M-C1 实现时以新包路径、非覆盖写入和严格目录 allowlist 修正。

## 明确不派发

- OI/funding trigger 点火、90 天后是否启用、CoinGlass 订阅、数据源或凭证变更。
- 任何 `paper_eligibility=ALLOW`、纸面执行、方向、仓位或真实交易相关操作。
- 飞书 webhook 的真实调用或将开关置为 `on`。
- 数据刷新脚本、Windows 排程、DB/parquet/checkpoint/lock/日志的写入。

这些事项全部为 `PARK`，只能记录到里程碑包的 `OWNER_DECISIONS_NEEDED.md`。

## 验收方式

外部产物是证据或候选，不是可直接合并的结论。codex 必须逐项核对输入路径、原始文本、禁止项、实现范围和测试证据；隔离代码需由 codex 手工审阅、最小化整合、独立测试。任何缺少的产物保留 `MISSING` 状态。
