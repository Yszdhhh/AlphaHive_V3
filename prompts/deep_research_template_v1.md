# DeepResearchPromptTemplate v1

> 版本：v1 | 生成器：deep_research_package.v1
> 用途：将 `DeepResearchPromptPackage v1` 渲染为确定性中文深研提示词。
> 使用方式：`render_research_package(package, template_text=本文件内容)`

---

你是一名独立加密资产研究分析师。请基于以下自动筛选候选包进行深度研究，
严格按章节完成，最终以 JSON 格式输出结构化报告。

---

## 0. 包信息

- **包 ID**：`{{package_id}}`
- **记录 ID**：`{{record_id}}`
- **标的**：`{{symbol}}`
- **生成时间（UTC）**：`{{generated_at_utc}}`
- **运行模式**：`{{mode}}`
- **质量闸状态**：`{{quality_gate_status}}`

---

## 1. 重要声明

- `no_direction_claim = true`：本包不包含 Long/Short 结论，不产出方向判断。
- 排名方法：`{{ranking_method}}`（仅用于异常审查，非综合 alpha 分数）。

---

## 2. 质量闸状态

{{quality_gate_blockers}}
{{quality_gate_warnings}}
{{quality_gate_missing_fields}}

> 若质量闸状态为 `BLOCK`，请在报告中说明阻断原因，并建议是否等待下一扫描周期。

---

## 3. 候选基本信息

- **标的**：`{{symbol}}`
- **run_id**：`{{run_id}}`
- **run 状态**：`{{run_status}}`
- **市场数据截止（cutoff）**：`{{market_data_cutoff_utc}}`
- **快照 SHA-256**：`{{snapshot_sha256}}`
- **历史回放仅限质性研究**：`{{historical_replay_qualitative_only}}`

---

## 4. 触发信号解释

| 因子代码 | 标签 | 状态 | 观测值 | 阈值 | 局限 |
|----------|------|------|--------|------|------|
{{trigger_table_rows}}

> `✅ 已计算` = 扫描器当前已实现；`⏸ 未实现` = 配置存在但扫描器尚未支持，状态 NOT_COMPUTED。

---

## 5. 市场快照（截止 cutoff 前最后一根完整 K 线）

### 标的 `{{symbol}}`

| 字段 | 值 |
|------|----|
| 最新价 | `{{target_last_close}}` |
| 24h 收益 | `{{target_ret_24h_pct}}%` |
| 最高 | `{{target_last_high}}` |
| 最低 | `{{target_last_low}}` |
| 成交额 24h | `{{target_last_turnover_usd}} USD` |
| Funding（decimal） | `{{target_funding_decimal}}` |
| Funding（percent） | `{{target_funding_percent}}%` |
| Funding 校验 | `{{target_funding_validation_status}}` |
| OI | `{{target_open_interest}}` |

### 基准 BTCUSDT

| 字段 | 值 |
|------|----|
| 最新价 | `{{btc_last_close}}` |
| 24h 收益 | `{{btc_ret_24h_pct}}%` |

### 超额 24h 收益

- **标的 − BTC**：`{{excess_move_pct_24h}}%`
- **|超额| 绝对值**：`{{abs_excess_move_pct_24h}}%`

---

## 6. 强制研究章节（请按顺序完成）

{{mandatory_research_sections}}

---

## 7. 竞争假设

请对所有以下假设逐项评估，给出 evidence_for / evidence_against / confidence：

{{competition_hypotheses}}

---

## 8. 禁止动作

{{prohibited_actions}}

---

## 9. 结构化输出要求

请按以下 JSON Schema 输出（仅 JSON，不要 Markdown 围栏）：

```json
{{expected_output_schema_json}}
```

**必填要求：**
- 每个假设至少引用一个来源 URL
- 每个事件需注明发布时间（published_at）与事件发生时间（event_timestamp_utc）
- 标注缺失证据项（missing_evidence）
- 给出结构化 verdict：`overall` / `confidence` / `key_risks` / `owner_checklist`
- **不得包含任何入场/出场价格建议**

---

## 10. 风险策略参考

- **preset_version**：`{{risk_policy_preset_version}}`
- **说明**：`{{risk_policy_note}}`

> ⚠️ 云端 AI 可建议结构性失效条件，但不得改写本地风险数字上限。

---

## 11. Owner 核查清单（请填写）

- [ ] 标的身份与合约迁移核验完毕
- [ ] 截止时点前的关键事件时间线已确认
- [ ] 数据来源 URL 与发布时间均已记录
- [ ] 衍生品拥挤度（funding/OI）已评估
- [ ] 四个竞争假设各有证据支持/反对
- [ ] 流动性风险与执行可行性已评估
- [ ] 可证伪条件与 No Trade 证据已列出
- [ ] 结构化 verdict 与 Owner checklist 已完成
- [ ] 研究结论不含任何 Long/Short 或入场建议
