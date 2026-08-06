# ARC-NEXT-N2-RECON-001 — Grok (optional / not in current fixed wave)

> 本文件仅保留为 Owner 另行启用 Grok 时的草案。当前固定派单不包含 Grok；不得自行执行或将其输出当作正式 handback。

**Tier:** T1 read-only reconciliation  
**Owner boundary:** ARC-NEXT 2026-07-16  
**Repository:** `G:\Quant test\AlphaHive_V3`

## Objective

对 Binance 与 CoinGlass funding 在 2026-06-07 至 2026-06-23 的重叠区做可复核的只读 reconciliation，服务 HB-1。Grok 的任务集中在机械对齐、偏差计算和证据表达，不做任何决策性改动。

## Required reading

先完整阅读 `PROJECT_REQUIRED_READING.md` 指向的共享治理文件，再阅读本任务。所有数据质量不确定性必须显式标注，不得用估计值补齐。

## Scope

- 只读加载 CoinGlass 与 Binance funding 原始文件，使用现有 canonical adapter 的单位语义；不要自行猜单位。
- 按 symbol + UTC settlement timestamp 对齐 6/7–6/23 重叠区。
- 输出逐符号：共同样本数、缺行数、绝对偏差、相对偏差、bps 或等价单位；说明零值和缺失值处理。
- 使用预先声明的容差；如输入中没有已锁定阈值，报告“阈值待 Codex/Owner 依据既有契约确认”，不得事后调阈值。
- 给出超阈值清单和二选一结论：`两源一致(可互信)` 或 `发现质量问题(列明)`。

## Forbidden

- 不写数据库或 parquet，不切换 scanner source path。
- 不修改阈值、不做插值/回填、不把缺洞隐藏成一致。
- 不触发 trigger、Paper、凭证、代理或交易动作。

## Deliverable

将原始报告写入 `C:\Users\10639\Desktop\ARC_NEXT_DELIVERIES\grok\ARC-NEXT-N2-RECON-001.md`，附：输入路径、运行时间、对齐规则、计算公式、每符号结果、阈值与超阈值清单、缺失/限制、`SELF_CHECK` 和明确的 `PARK` 项。
