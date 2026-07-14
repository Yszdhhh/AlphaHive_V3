# ARC-A-RECON-002｜Mimo：Binance 侦察报告事实校正

**tier：** `T1 GREEN / read-only correction`  
**from：** Mimo  
**to：** codex  
**前提：** 这是 `ARC-A-RECON-001` 的补正，不覆盖、删除或改写其原文。

## 开始前必须读

1. `G:\Quant test\AlphaHive_V3\agent_tasks\README.md`
2. `G:\Quant test\AlphaHive_V3\agent_tasks\ARC_NEXT_STAGE_DISPATCH_PLAN.md`
3. `G:\Quant test\AlphaHive_V3\agent_tasks\mimo__codex__arc_a_binance_recon.md`
4. 原文：`C:\Users\10639\Desktop\AlphaHive_V3_ArcA_MA1_deliverables\agent_outputs\mimo\ARC-A-RECON-001_BINANCE_RECON.md`
5. 任务文件列出的全部治理前置文件。

## 只校正以下事实

1. 对 BTCUSDT funding 的实际非零样本，展示原始中位数绝对值、`×100` 结果、现有 raw 下限 `0.0008` 与比较方向。若中位数是 `4.1725e-05`，则必须明确 `4.1725e-05 × 100 = 0.0041725`，它**大于** `0.0008`。不要以数据源路径不同为由回避该算术事实；路径是否接入另列为 codex 实现问题。
2. 用 UTC、可复算的 epoch 转换重新给 BTCUSDT klines/OI/funding 的最早和最新时间。不要把 `1778018400000` 写成 2026-09；若工具结果与旧报告冲突，保留新证据并标记旧报告错误。
3. 对 `fundingRate_raw` 和 `fundingRate_decimal` 做数据级相等性/差异检查，不能仅凭列名假定含义；若二者相同，明确该命名不能独立证明单位转换已完成。
4. Windows Task Scheduler 的 `Last Result` 只按可核实的返回码解释：不得把 `1` 叫作 success。若无法读取任务的真实最后运行结果/定义，写 `UNVERIFIED`，不要推断每 4 小时的调度含义。
5. 区分已证实事实、不能证实的 stale-loop 风险、以及不需要 Owner 的既定代码实现（Decision B 的 binance free 映射）。不要把现有 Charter 已确定的实现范围误报为 Owner 决策。

## 禁止项

不得修改 repo、原 `-001` 报告、DB/parquet/checkpoint/日志、排程、系统设置或任何凭证；不得运行 puller、联网或 API 请求。

## 原始输出

只写：

`C:\Users\10639\Desktop\AlphaHive_V3_ArcA_MA1_deliverables\agent_outputs\mimo\ARC-A-RECON-002_FACT_CORRECTION.md`

开头写 `agent=Mimo`、`task_id=ARC-A-RECON-002`、UTC、全部输入、`GREEN/PARK/UNVERIFIED`、未决项。该文只做可复算的补正，不重写完整侦察报告。
