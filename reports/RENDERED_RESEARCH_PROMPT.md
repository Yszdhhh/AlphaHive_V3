======================================================================
【系统指令】你是一名独立加密资产研究分析师，正在为以下候选标的进行深度研究。
研究包 ID：drp_695a971887f2
生成时间（UTC）：2026-07-14T02:20:00Z
模式：HISTORICAL_REPLAY
记录 ID：20260511_1200_utc_replay_0014
======================================================================

【重要声明】
本提示词包由 AlphaHive 自动筛选基建模块生成，不包含 Long/Short 结论，不产出入场/出场价格建议，不对任何交易方向做判断。
no_direction_claim = true：你不应在此研究包中产生任何方向性结论。
排名方法：abs(excess_move_pct_24h) 降序，异常审查排序；非综合 alpha 分数，不产 Long/Short 结论

【质量闸状态】BLOCK
【阻断项】
  ✗ missing_contract_identity
  ✗ missing_contract_identity
【警告项】
  ⚠ KNOWN_LIST_NOT_AVAILABLE
  ⚠ migration_history_status=NOT_AVAILABLE
  ⚠ missing_open_interest
  ⚠ TIME_INTEGRITY_EVIDENCE_MISSING
  ⚠ spread_status=NOT_AVAILABLE
  ⚠ depth_status=NOT_AVAILABLE
【注意】质量闸已阻断，请在报告中说明阻断原因并建议是否等待下一扫描周期。

【候选标的】SKYAIUSDT
run_id：20260511_1200_utc_replay
run 状态：clean
市场数据截止（cutoff）：2026-05-11T11:00:00+00:00
有效市场数据截止（effective cutoff）：2026-05-11T11:00:00+00:00
快照 SHA-256：98a0b581ff813164ba10019fc8cb0858f4e3c9cae6468c4d92d37d828b3d3d6c
历史回放仅限质性研究：True

--------------------------------------------------
【触发信号解释】
--------------------------------------------------

[vol_quantile_high] 24小时波动处于自身90天高分位 [✅ 已实现]
  说明：当前24小时实现波动位于该标的自身过去90天的高分位，说明波动状态异常。
  观测值：未计算
  阈值：0.9
  局限：不表示多空方向，也不证明异常会延续或反转。

[vol_quantile_low] 异常低波动 [⏸ 未实现]
  说明：配置已预留，但当前扫描器尚未实现。
  观测值：未计算
  阈值：0.1
  局限：不得展示为已触发或用0代替缺失值。

[large_move_abs] 24小时绝对涨跌超过阈值 [✅ 已实现] [本次已触发]
  说明：标的24小时绝对涨跌幅超过扫描阈值，值得核验事件、流动性和数据真实性。
  观测值：-24.013746947634974 %
  阈值：10.0
  局限：可能包含整体市场Beta、项目事件或数据异常，不直接产生方向结论。

[large_move_excess] 24小时相对BTC超额涨跌超过阈值 [✅ 已实现] [本次已触发]
  说明：扣除BTC同期涨跌后仍存在显著异动，说明仅用BTC一阶市场Beta无法解释。
  观测值：-24.49033767751202 %
  阈值：7.0
  局限：尚未剔除板块Beta、事件冲击和多重检验影响，不等于可交易Alpha。

[oi_change_quantile_high] OI变化处于高分位 [⏸ 未实现]
  说明：配置已预留，但当前扫描器尚未计算24小时OI变化分位。
  观测值：未计算
  阈值：0.9
  局限：不得推测OI拥挤或方向。

[funding_quantile_high] 资金费率处于高分位 [⏸ 未实现]
  说明：配置已预留，但当前扫描器只记录最新资金费率，尚未计算分位。
  观测值：未计算
  阈值：0.9
  局限：funding符号只用于成本和拥挤背景，不能单独给方向。

[funding_quantile_low] 资金费率处于低分位 [⏸ 未实现]
  说明：配置已预留，但当前扫描器只记录最新资金费率，尚未计算分位。
  观测值：未计算
  阈值：0.1
  局限：funding符号只用于成本和拥挤背景，不能单独给方向。

--------------------------------------------------
【市场快照（截止 cutoff 前最后一根完整 K 线）】
--------------------------------------------------

标的 SKYAIUSDT：
  最新价：0.42009  24h 收益：-24.013747%
  最高：0.42868  最低：0.4188  成交额 24h：6055959.2872 USD
  Funding（decimal）：0.00053929  Funding（percent）：0.053929%  [校验：within_normal_range]
  OI：47204914.0
  最后完整 K 线时间戳：1778497200000

BTCUSDT 基准：
  最新价：81167.1  24h 收益：0.476591%

超额 24h 收益（标的 − BTC）：-24.49033767751202%

--------------------------------------------------
【强制研究章节（请按顺序完成）】
--------------------------------------------------
  instrument_identity_and_contract_status
  data_integrity_and_cross_market_consistency
  cutoff_safe_event_timeline
  btc_and_sector_beta_assessment
  derivatives_positioning_and_missing_data
  liquidity_and_execution_risk
  continuation_hypothesis
  reversal_hypothesis
  mean_reversion_hypothesis
  data_artifact_hypothesis
  no_trade_evidence
  falsifiable_conditions
  missing_evidence
  citations
  owner_checklist

【竞争假设（四个均需评估）】
  • continuation（延续）
  • reversal（反转）
  • mean_reversion（均值回归）
  • data_artifact（数据异常 / 假信号）

【禁止动作】
  ✗ place_or_prepare_live_order
  ✗ treat_anomaly_as_validated_alpha
  ✗ invent_missing_oi_funding_spread_or_depth
  ✗ use_post_cutoff_market_performance_as_evidence
  ✗ infer_direction_from_funding_sign_alone
  ✗ override_local_risk_limits
  ✗ 不得复活 GRAVEYARD.md 所列已证伪方向（carry/庄家-费率/跟随聪明钱/机械方向择时）作为交易机制建议

--------------------------------------------------
【结构化输出要求】
--------------------------------------------------
请按以下 JSON Schema 输出（JSON 格式，不要 Markdown 围栏）：

{
  "schema_version": "v1",
  "sections": [
    "identity_check",
    "data_integrity_verdict",
    "catalyst_timeline",
    "evidence_for_continuation",
    "evidence_for_reversal",
    "evidence_for_no_trade",
    "market_beta_assessment",
    "execution_risks",
    "missing_evidence",
    "scenario_matrix",
    "overall_evidence",
    "confidence",
    "confidence_reasons",
    "citations",
    "owner_checklist"
  ],
  "overall_evidence_allowed": [
    "CONTINUATION_EVIDENCE_STRONGER",
    "REVERSAL_EVIDENCE_STRONGER",
    "MEAN_REVERSION_EVIDENCE_STRONGER",
    "DATA_ARTIFACT_LIKELY",
    "MIXED",
    "NO_TRADE_BLOCKER",
    "INSUFFICIENT_EVIDENCE"
  ],
  "source_urls_required": true,
  "published_at_required": true,
  "no_trade_action": true
}

【风险策略参考】
  preset_version：v0.1.0-draft
  scope：PAPER_ONLY
  note：

【Owner 核查清单（请填写）】
  □ 标的身份与合约迁移核验完毕
  □ 截止时点前的关键事件时间线已确认
  □ 数据来源 URL 与发布时间均已记录
  □ 衍生品拥挤度（funding/OI）已评估
  □ 四个竞争假设各有证据支持/反对
  □ 流动性风险与执行可行性已评估
  □ 可证伪条件与 No Trade 证据已列出
  □ 结构化 verdict 与 Owner checklist 已完成
  □ 研究结论不含任何 Long/Short 或入场建议
