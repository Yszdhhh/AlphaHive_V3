# AGENT_ORCHESTRATION_PROTOCOL v1

> For the Autonomous Arc Charter v1 batch, the Owner confirmed on 2026-07-14 that this v1 file is the sole governance equivalent of the Charter's referenced v2 file. T3 still requires a separate Owner decision.

## 0. 目的

把“谁执行、谁审、什么自主、什么卡门”写死，让 Owner 只需确认方向 + 签 T3 闸，不必每轮审。运动员/裁判分离不变。

## 1. 角色

- **独立审阅者（机外、provider/model 可替换）**：只读审计 codex 打包成果并保留原文 provenance；不写 repo，不替 Owner 签 T3。
- **codex（PC 枢纽）**：编排、主执行、整合、回归、打包。拥有并唯一写 `AlphaHive_V3/`；按 `_bus` 派子任务给其它 agent；出单一 deliverable 发 Opus。
- **antigravity/Gemini（研究区执行 + 隔离代码）**：深研实拨（provider 多样，产物 `UNVERIFIED`），或执行 codex 指派的隔离代码模块。不写 repo，产隔离产物交 codex 整合。
- **mimo（杂活）**：数据盘点、跑脚本、覆盖报告、机械打包。只读或隔离。
- **Sonnet（独立审计）**：T3 批次在 codex 打包前做 PC 端预审。

## 2. 单写者规则

只有 codex 写 `AlphaHive_V3/`。其它 agent 的原始产物落各自 Desktop 交付目录，由 codex 验收后整合进 repo；禁止多个 agent 并发写同一 git。

## 3. 任务分层

每个 handoff 开头必须声明 `T1`、`T2` 或 `T3`：

- **T1 GREEN**（codex 自主跑 + commit，末尾打包 Opus spot-check）：additive、可回滚、有测试、不点火 trigger、不改 config 数值、不放行 paper、机械性工作。
- **T2 决策**（Opus 快速定，不必 Owner）：工程纪律——schema、cutoff 语义、单一真理源、死代码、命名、归档。
- **T3 RED**（Owner 签字才动）：阈值锁定（只向严）、trigger 点火、paper ALLOW、真钱/下单路径、任何碰 GRAVEYARD thesis 的方向决策、数据源/密钥变更。

codex 遇 T3 一律 park 进 `OWNER_DECISIONS_NEEDED`，继续做 T1，绝不自行跨 T3。

## 4. `_bus` 约定

跨角色 handoff 文件由 codex 验收并写入：

`_bus/<from>__<to>__<topic>.md`

下游直接读取文件，不等 Owner 中转。不建自动触发器或状态机。外部 agent 不写 repo；它们先把原始产物放在 Desktop 交付目录，codex 再原文复制进 `_bus/`。

## 5. 打包与回传

codex 出单一 deliverable，必须包含：

1. 逐 commit git diff（不是摘要）；
2. 各子 agent 原始产物原文；
3. 回归结果；
4. `SELF_CHECK` 对 DoD 逐条核验；
5. `OWNER_DECISIONS_NEEDED`，包括所有 park 的 T3。

T3 相邻批次附独立预审原文（provider/model 可替换并在报告顶部标识）。独立审阅者审一手证据，不审 codex 摘要。

## 6. 红线（不变）

不碰 token/secret；未经 Owner 明确授权不 push；不碰执行层/下单；不假实现闸；不放宽阈值；删文件先问；研究区产物永远 `UNVERIFIED`，直到独立核验。

## 7. 操作手册索引

具体的任务分发模板、并行规则、报告验收、provenance 处理、桌面归档和新对话启动模板统一维护在 [`PROJECT_OPERATING_PLAYBOOK.md`](PROJECT_OPERATING_PLAYBOOK.md)。该手册是本协议的操作层补充，不放宽任何 T3 Owner 审批红线。
