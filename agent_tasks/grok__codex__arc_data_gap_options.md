# ARC-DATA-GAP-OPTIONS-001 — Grok（可选成本侦察）

**agent:** Grok  
**task_id:** `ARC-DATA-GAP-OPTIONS-001`  
**tier:** T1 read-only research  
**output:** `C:\Users\10639\Desktop\AlphaHive_V3_A_DATA_HEALTH_deliverables\agent_outputs\grok\ARC-DATA-GAP-OPTIONS-001.md`

## Objective

仅调查 OI/taker 约 2026-05-26/27 至 2026-06-16 的三周数据缺口是否存在免费或低成本、可审计的补全路径，并给出成本—证据—风险比较。此任务不作回填决策，不授权任何购买、下载、写库或数据源切换。

## Required reading

按顺序阅读：

1. `G:\Quant test\AGENTS.md`
2. `G:\Quant test\AlphaHive_V3\AGENTS.md`
3. `G:\Quant test\AlphaHive_V3\PROJECT_REQUIRED_READING.md`
4. `G:\Quant test\AlphaHive_V3\PROJECT_OPERATING_PLAYBOOK.md`
5. `G:\Quant test\AlphaHive_V3\agent_tasks\README.md`
6. 本任务文件

## Required inputs

- `G:\Quant test\AlphaHive_V3\reports\DATA_CANONICAL_COVERAGE_20260715.md`
- `G:\Quant test\AlphaHive_V3\reports\DATA_HISTORY_RESEARCH_ACCEPTANCE_20260716.md`
- `G:\Quant test\AlphaHive_V3\config\data_contracts.yaml`
- `G:\Quant test\AlphaHive_V3\config\universe.json`
- `G:\Quant test\AlphaHive_V3\OWNER_DECISIONS_NEEDED.md`

## Required checks

对每个候选方案分别记录：

- 是否真的覆盖目标区间、OI 和 taker 两个维度、59 个有效符号；
- 时间分辨率、字段语义、单位、symbol/contract identity 和 checksum/provenance；
- 免费额度、一次性费用、持续费用、注册/信用卡/许可限制；
- 是否能在不依赖估算、插值或 synthetic history 的情况下取得原始对象；
- 是否允许研究/回测使用，是否存在再分发或合规限制；
- 预计接入成本、失败模式、回填后如何与 Binance/CoinGlass 做 reconciliation；
- 推荐等级：`FREE_CANDIDATE`、`LOW_COST_CANDIDATE`、`NOT_VIABLE` 或 `UNVERIFIED`。

至少比较：公开 Binance REST/历史归档、Binance Vision/S3 对象、公开镜像/社区归档、低价历史数据供应商；如果某一类不存在可验证证据，明确写 `UNVERIFIED`，不要用搜索摘要替代。

## Hard boundaries

- 只做方案研究，不购买、不注册、不调用需要凭证的 API，不下载批量数据，不写 DB/Parquet/checkpoint。
- 不修改 `data_contracts.yaml`，不切换 scanner source path，不填补断洞，不改变 Paper/trigger/threshold。
- 不把“找到供应商”写成 Owner 已批准；所有 gap-fill 继续 T3/PARK。
- 必需输入或输出路径缺失时输出 `PARK`。

## Deliverable

原始报告只能写入指定 Desktop output path。报告头必须包含 agent、task_id、UTC 时间、精确输入/来源、状态（`GREEN`/`UNVERIFIED`/`PARK`）和未决项。正文须有候选方案比较表、成本区间、证据链接/对象路径、推荐顺序、停止条件和 `SELF_CHECK`。
