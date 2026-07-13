# 自动化信号筛选与深研提示词基建分工方案

日期：2026-07-10

## 1. 角色定义

本轮 DeepSeek V4 Flash 与 Mimo 的角色是并行开发者，不是候选币审核者。

- Codex 主线：负责架构、数据契约、研究时点、核心 API、账本/审计、风险策略、合并和最终验收。
- DeepSeek V4 Flash：负责隔离的纯数据模块，包括候选解释、质量闸、提示词数据包、确定性渲染和单元测试。
- Mimo：负责隔离的候选审查前端原型，包括因子解释、提示词预览/复制、研究结果回填表单和 Paper 计划表单的 mock 交互。
- Owner：批准契约和风险 preset；外部模块完成后将产物交回 Codex 审查合并。

两者都不参与逐币研究结论，不得替 Owner 决定 Long/Short，也不得接入真实交易。

## 2. 目标工作流

```text
冻结快照 + 自动扫描
  → CandidateReviewPackage（为什么被筛出、质量是否可用、缺什么）
  → DeepResearchPromptPackage（可复制给任意云端 AI）
  → 云端研究结果回填
  → Owner 最终决定
  → 版本化 Paper 风险计划
  → 决策完成后的新入场锚
  → Paper 跟踪与纪律检查
```

页面必须区分三句话：

1. 为什么被自动筛选出来。
2. 为什么值得深入研究。
3. 为什么最终允许建立 Paper 计划。

当前 V3 的三个已实现触发器只说明异常，不证明 alpha，也不天然产生方向：

- `vol_quantile_high`：24h 实现波动位于自身 90 天高分位。
- `large_move_abs`：标的 24h 绝对涨跌超过阈值。
- `large_move_excess`：标的相对 BTC 的 24h 超额涨跌超过阈值。

配置中存在但扫描器尚未实现的 `vol_quantile_low`、OI 变化分位和 funding 高低分位必须显示为 `NOT_COMPUTED`，不能伪装成已计算因子。

## 3. 核心数据契约

服务端先生成结构化 `DeepResearchPromptPackage v1`，再由模板确定性渲染提示词。页面与提示词共用同一份 `signal_explanations`，不允许各写一套解释。

最低字段：

- 包信息：schema_version、package_id、template_version、generated_at、package_hash。
- 来源信息：run_id、record_id、symbol、scan_time、market_data_cutoff、snapshot_sha256。
- 模式：`HISTORICAL_REPLAY` 或 `PROSPECTIVE_LIVE`。
- 运行资格：run status、eligible_for_judgment、eligible_for_paper、quality status。
- 质量闸：blockers、warnings、missing_fields、required_human_checks。
- 信号：ranking_method、trigger codes、逐项观测值、阈值、分位、单位、人话解释和局限。
- 市场快照：标的/BTC/超额 24h 收益、波动、成交额、funding、OI、最后完整 K 线。
- 请求：强制研究章节、竞争假设、禁止动作、结构化输出 schema。
- 风险策略引用：preset version 和允许的 preset id；云端 AI 可建议结构性失效条件，但不能改写本地数字上限。

提示词 API 使用字段 allowlist，严禁序列化整行 ledger。

明确禁止进入提示词的数据：

- `exit_price_ref_*`
- `btc_exit_price_*`
- `dir_excess_ret_*`
- `dir_excess_ret_net_*`
- return tape
- evaluation
- 事后 falsified/validated 结论

## 4. 历史回放与实时模式

### HISTORICAL_REPLAY

- 所有市场数据必须 `timestamp <= scan_time_utc`。
- 云端开放搜索结果只能用于质性复盘，不得进入回测绩效。
- 无法证明发布时间不晚于 cutoff 的来源只能进入 excluded sources。

### PROSPECTIVE_LIVE

- 市场特征截止 scan time。
- 外部研究资料可截止 Owner 决策时间，但必须记录发布时间和观察时间。
- 深研完成后必须重新取得 Paper 入场锚。
- 不能继续使用扫描后的第一根 K 线 open 作为实际 Paper 入场价。

## 5. Paper 风险基建

现有 `exec_planner.py` 的固定 -10%/+15% 属于 ETH/SOL 组合底盘，不能继承到异动币。

新增独立且版本化的 `paper_execution_presets.yaml`，每档至少包含：

- preset id/version/status。
- 单笔和组合 Paper 风险预算。
- 波动/结构/成本地板的止损公式。
- TP 的 R 倍数和分批权重。
- time stop、追价上限、批准有效期。
- 禁止摊平、禁止放宽止损、最大 active plan。
- 适用流动性级别和最低数据要求。

数值在回放校准前标记为 `DRAFT`，只允许 Paper；前端不得把 DRAFT 描述为最优参数。

必须新增独立 PaperPlan 账本，分开保存：

- signal scan time / research entry anchor。
- research completed time。
- Owner approval time。
- paper entry time / paper entry price。

## 6. 并行文件边界

### Codex 主线可修改

- 核心契约和架构文档。
- `alpha_hive/server/app.py` 及新的 repository/service/routes/models。
- V3 审计、幂等、时间截断和风险 preset。
- 最终前端集成与回归。

### DeepSeek 只允许新增

- `AlphaHive_V3/harness/lib/deep_research_package.py`
- `AlphaHive_V3/prompts/deep_research_template_v1.md`
- `AlphaHive_V3/tests/test_deep_research_package.py`
- 必要的独立 fixture

禁止修改 app、scanner、ledger、既有 schema 和前端。

### Mimo 只允许新增

- `alpha_hive/dashboard/review.html`
- `alpha_hive/dashboard/review.js`
- `alpha_hive/dashboard/review.css`
- `alpha_hive/dashboard/review_mock.json`

禁止修改现有 `index.html`、`dashboard.js`、后端、扫描器和账本。

这样三路工作不会同时改同一文件；外部产物由 Codex 审查后接入。

## 7. 主线验收

- [ ] 当前已实现与未实现 trigger 状态完全准确。
- [ ] 同一输入和生成时间产生 byte-stable JSON/prompt。
- [ ] 包含 record_id、cutoff、snapshot hash、template version 和 package hash。
- [ ] 决策包/提示词没有任何扫描后数据。
- [ ] run 非 clean、hash 不符或资格不通过时质量状态为 BLOCK。
- [ ] 缺失 OI/funding/depth 显示“未提供/未计算”，不显示 0。
- [ ] 页面解释与复制提示词来自同一解释对象。
- [ ] 外部文本只按安全纯文本回填，不可自动生成 Paper 决定。
- [ ] scan entry 与 deep-research 后 Paper entry 完全分离。
- [ ] 风险 preset 版本化，旧计划始终引用旧版本。
- [ ] Long/Short 价格公式镜像，TP 权重合计 100%。
- [ ] 同一 K 线同时触发 TP/SL 时按止损先发生。
- [ ] 页面不存在真实下单、API Key、杠杆或资金划转入口。
- [ ] 原有因子研究页和接口无回归。

