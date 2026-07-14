# ARC-A-RECON-001｜Mimo：Binance 数据映射与 puller 健康只读侦察

**tier：** `T1 GREEN / read-only`  
**from：** Mimo  
**to：** codex  
**目的：** 为 Charter 弧线 A 的 M-A1 提供可复核的本地事实；不实现代码、不刷新数据。

## 开始前必须读

1. `G:\Quant test\AlphaHive_V3\agent_tasks\README.md`
2. `G:\Quant test\AlphaHive_V3\agent_tasks\ARC_NEXT_STAGE_DISPATCH_PLAN.md`
3. `G:\Quant test\AGENTS.md`
4. `G:\Quant test\AlphaHive_V3\AGENT_ORCHESTRATION_PROTOCOL.md`
5. `G:\Quant test\AlphaHive_V3\PROJECT_CONSTITUTION.md`
6. `G:\Quant test\AlphaHive_V3\GRAVEYARD.md`
7. `G:\Quant test\AlphaHive_V3\KARPATHY_GUIDELINES.md`

## 工作

只读检查 `C:\Users\10639\Desktop\加密\binance_free_db`（若路径不存在，要明确记录），以及 AlphaHive 中现有的 Binance 导入/映射/coverage 代码、测试、数据契约和与 daily puller 有关的本地脚本、日志、Windows 排程**定义**。不要访问任何凭证或外部网络。

报告必须分别给出：

1. 40 币 universe 覆盖的实际证据：符号清单/数量与缺失项。
2. klines、funding、OI、taker_buysell 的真实文件/表结构、时间字段、值字段、最早/最新时间、抽样行数；其余五类缺失指标也要显式列出。
3. funding 从 Binance 原始小数转换为现有 raw-percent 口径的证据：用实际非零样本计算说明 `raw = binance_value * 100` 后，是否满足现有 `data_contracts.yaml` 唯一 raw 下限 `0.0008`；若无法安全读取样本，写 `PARK`，不得猜测。
4. OI 的真实列名、单位声明（若没有则 `NOT_DECLARED`）、能否映射为现有 `oi_change_pct_24h` 所需序列的事实；不得把绝对 OI 猜成美元。
5. daily puller 的存在位置、调度证据、最后成功/失败证据、checkpoint 推进条件。特别检查“空返回仍推进 checkpoint”的 stale-loop 风险；无法证明时写 `UNVERIFIED`。
6. 一张给 codex 的最小映射建议表（源字段 → 目标字段 → 转换/不可转换原因 → 证据路径）。这是建议，不写代码。

## 严禁

- 不得修改 `G:\Quant test\AlphaHive_V3`、`_bus/`、git、DB、parquet、checkpoint、lock、日志、Windows 排程或系统设置。
- 不得运行 puller/refresh，联网/API 请求，读取、打印、复制、配置或验证 token、secret、API key、proxy。
- 不得改变阈值、trigger、paper 状态、数据源选择、方向或执行路径。

## 原始输出

只写这一份原文：

`C:\Users\10639\Desktop\AlphaHive_V3_ArcA_MA1_deliverables\agent_outputs\mimo\ARC-A-RECON-001_BINANCE_RECON.md`

文件开头必须包含：`agent=Mimo`、`task_id=ARC-A-RECON-001`、UTC 时间、已读输入路径、`GREEN/PARK/UNVERIFIED` 状态、未解决项。保留实际路径、命令观察结果和数字；不要用摘要替代原始证据。无法完成也必须交付说明原因的原文。
