# DeepSeek V4 Flash 并行开发任务

你在 Windows 项目 `G:\Quant test` 中工作。你的身份是 AlphaHive 基建开发者，不是交易审核者。你要实现“自动筛选候选解释 + 深研提示词数据包”的隔离纯模块，供主线后端以后接入。

## 目标

输入候选行、run registry 信息、run manifest、symbol meta，以及已经由调用方裁剪到 cutoff 以内的 snapshot 行；输出：

1. `DeepResearchPromptPackage v1` 结构化字典。
2. 确定性中文深研提示词。
3. 候选质量状态 `PASS/WARN/BLOCK`、缺失字段和阻断原因。
4. 自动筛选因子的人话解释、观测值、阈值、分位、实现状态和局限。

你不负责 HTTP API、账本写入、真实交易或逐币研究结论。

## 文件边界

只允许新增：

- `AlphaHive_V3/harness/lib/deep_research_package.py`
- `AlphaHive_V3/prompts/deep_research_template_v1.md`
- `AlphaHive_V3/tests/test_deep_research_package.py`
- 如确有必要，可在 `AlphaHive_V3/tests/fixtures/deep_research/` 新增最小 fixture

禁止修改任何已有文件，尤其禁止修改：

- `alpha_hive/server/app.py`
- `AlphaHive_V3/scripts/02_scan_anomalies.py`
- `AlphaHive_V3/ledger/*`
- 任何现有 schema/config
- `alpha_hive/dashboard/*`

## 必须先阅读

- `AlphaHive_V3/config/scan_rules.yaml`
- `AlphaHive_V3/config/data_contracts.yaml`
- `AlphaHive_V3/harness/run_registry.yaml`
- `AlphaHive_V3/harness/schemas/anomaly_ledger_schema.yaml`
- `AlphaHive_V3/scripts/02_scan_anomalies.py`
- `AlphaHive_V3/reports/AUTOMATED_SIGNAL_RESEARCH_INFRA_PLAN_20260710.md`

## 当前实现事实

只有以下 trigger 已实现：

- `vol_quantile_high`
- `large_move_abs`
- `large_move_excess`

以下虽在配置出现，但当前扫描器没有实现，必须标记 `NOT_COMPUTED`，不得补造数值：

- `vol_quantile_low`
- `oi_change_quantile_high`
- `funding_quantile_high`
- `funding_quantile_low`

当前候选按 `abs(excess_move_pct_24h)` 排序。包内必须写明这是异常审查排序，不是综合 alpha 分数，也不产 Long/Short 结论。

## 必须实现

建议公开纯函数：

```python
build_signal_explanations(candidate, scan_rules) -> list[dict]
evaluate_quality_gate(candidate, run_info, manifest, symbol_meta) -> dict
build_prompt_package(candidate, run_info, manifest, symbol_meta, snapshot_rows, generated_at_utc) -> dict
render_research_prompt(package, template_text=None) -> str
hash_prompt_package(package) -> str
```

允许调整函数名，但必须保持无文件写入、无网络请求、无全局状态。

包必须包含：

- schema/template/generator version。
- package id/hash 和显式 generated time。
- mode、run/record/symbol/scan time/cutoff/snapshot hash。
- run status、judgment/paper eligibility、quality gate。
- ranking method、trigger items 和 `no_direction_claim=true`。
- 标的/BTC/超额 24h 收益、波动、成交额、funding、OI、最后完整 bar。
- mandatory research sections、competition hypotheses、prohibited actions。
- expected output schema。
- risk policy reference，但不自行发明或覆盖风险数字。

funding 同时提供 decimal 和 display percent，并带 source unit / validation status。单根 funding 接近 0 只能说明信息弱或需核验，不能直接判单位错误。

## 防未来数据泄漏

- snapshot 中任何 `timestamp > market_data_cutoff` 必须拒绝或过滤，并在质量闸说明。
- manifest data cutoff 不能晚于 scan time。
- 使用字段 allowlist，禁止序列化整行 ledger。
- 输出中严禁出现 `exit_price_ref_*`、`btc_exit_price_*`、`dir_excess_ret_*`、`dir_excess_ret_net_*`、return tape、evaluation 或事后 falsified 结论。
- HISTORICAL_REPLAY 必须标 `qualitative_only_for_open_web_research=true`。

## 提示词内容

提示词应要求未来使用它的云端 AI 核验：

- 标的/合约身份、迁移和交易所状态。
- 数据真实性与跨市场一致性。
- 截止时点前的事件时间线。
- 市场 beta、板块 beta 和 BTC 相对表现。
- 衍生品拥挤、资金费率、OI 与缺失项。
- continuation、reversal、mean reversion、data artifact 四个竞争解释。
- 流动性、执行风险、可证伪条件和 No Trade 证据。

输出必须要求来源 URL、发布时间、事件发生时间、证据支持/反对、缺失证据、结构化 verdict 和 Owner checklist。不得要求云端 AI 下单。

## 测试验收

- 相同输入与 generated time 生成 byte-stable 包和 prompt。
- package hash 可复算。
- cutoff 边界值测试。
- denylist 全量测试，扫描后字段 0 次出现。
- 当前 3 个已实现 trigger 的解释测试。
- 4 个未实现 trigger 显示 NOT_COMPUTED。
- Missing 显示 null/未提供，不显示为 0。
- funding decimal/percent 换算测试。
- clean/dirty/quarantined/hash mismatch/partial history 的质量闸测试。
- 不修改已有文件的检查。

完成后只提交：变更文件清单、设计说明、运行测试命令、测试输出和已知限制。不要修改任务边界外文件。

