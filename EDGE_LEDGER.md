# EDGE_LEDGER — edge 生命周期台账（AlphaHive V3）

> 用途：每个候选/验证 edge 的唯一生命周期记录。`state` 是唯一当前状态；`evidence_grade` 与 `independence` 单独记录证据强度，不等同部署资格。
> 状态机：`candidate → historical_pass → shadow → forward_pass → live → watch → decaying → retired`。
> 规则：任何规则修改 = 新版本 + 新样本起点；退役入 GRAVEYARD.md 但保留本条历史。
> 历史 bootstrap 只授予 `historical_pass`，不授予部署资格；晋级 live 必须前向样本独立通过（见 109 --all）。
> 多重检验预算：每季度 ≤1 主研究问题 + 2 个预注册次假设；未预注册结果必须标为 `exploratory`。

## 状态摘要（2026-08-07）

| id | edge | state | evidence_grade | independence | 关键证据 | 备注 |
|---|---|---|---|---|---|---|
| E01 | wash_cvd 基础信号 | **shadow** | historical | primary | n=1348，24h +1.31% CI[+0.66,+1.63]，168h +2.70%，3/4 episode GO_LONG | 唯一核心 edge；版本=scan_rules v3 |
| E02 | 空头强平激增 liq_short_z>1 | **shadow** | subset_robust | re-slice | +4.44% CI[+1.98,+7.25]（131 n=123）；141 表3 子集 +5.13%（n=100） | 131 为主结果；134/141 为同窗子集稳健，不称独立确认 |
| E03 | 放量 >1.5x | **shadow** | historical | re-slice | +1.90%，4/4 episode，增量 +0.78pp 显著（126） | 历史条件化结果，前向仍待独立 |
| E04 | VIX q75 门控 | **shadow** | historical | re-slice | +0.27pp 增量，3/3 episode 同向（123） | 108 仅 runtime_wired/annotate，不代表 forward_pass |
| E05 | 广度 ≥5% 分层 | **historical_pass** | historical | re-slice | 中 5-15% 层 +1.85%（124）；2025 级联翻正 +1.52%（135） | 宜分层不作硬门控；2022 反噬 |
| E06 | 贪婪层 fng≥60 | **historical_pass** | historical | re-slice | +1.48% CI[+0.87,+2.10]（132） | 丢正期望，有真实机会成本 |
| E07 | 高 OI 分位 oi_z>1.5 | **historical_pass** | historical | re-slice | +2.23% CI[+0.99,+3.64]（136） | 2025 单期 NO_GO |
| E08 | 谷歌趋势高分位周 | **candidate** | exploratory | primary | +2.35% CI[+1.30,+3.44]（138，n=435） | 单测，未交叉验证；不当半验证 edge |
| E09 | 组合 ≥2 条件档 | **shadow** | historical | re-slice | +1.60%/事件，72.7% 样本，总期望最大（133/134） | 稳健默认，但共享事件池 |
| E10 | 四条件全开 | **historical_pass** | historical | re-slice | +8.45% CI[+3.55,+13.70]（134，n=57） | 仅容量允许时用 |
| E11 | 交易所净流入高日 | **descriptive** | exploratory | primary | +2.24%（140） | 不构成信号 |
| E12 | OI×价格四象限 | **candidate** | exploratory | primary | 清洗 vs 堆集 Δ=+0.01pp CI[-2.12,+1.98]；82% 事件在清杠杆象限 | 主对照不显著且功效不足以排除 1pp 级增量；不纳入筛选栈 |
| E13 | LCS 清算易感度 | **candidate** | exploratory | primary | 142 事件化实测：holdout q75 +1.38pp CI[-1.58,+5.33]、q90 +2.04pp CI[-1.42,+5.39]，样本不足/未确认（`reports/lcs_susceptibility.md`） | 事件化版本测完，不升级；老版横截面 net −1.8（换手 365/yr） |
| E14 | CVD 背离陷阱布尔 | **candidate** | exploratory | primary | botv2 面板 9,810+ 次未分层检验 | 与 wash_cvd 概念重叠，增量预期低 |
| E15 | funding 加速度拥挤 | **candidate** | exploratory | primary | botv2：4h 轴 8h funding 二阶差分=噪声 | 粒度错配已证，搁置 |
| E16 | 链上传统资产 washout（Pyth） | **candidate** | exploratory | primary | NVDA +1.90% CI[+0.13,+3.76] n=45（144，2022-06→2026-08）；黄金/白银/英镑 NO_GO；SPY/QQQ 样本不足但 168h 方向正 | **s002 已关闭**：扩展 4 股 + 半导体 3 股全未复制，NVDA 单资产特异性（观察项） |
| E17 | funding 拥挤度反转（s005） | **retired** | exploratory | primary | 146 首测显著为基线 bug（ret_24h 误作 168h 基线）；修正后 B 168h +1.88% NO_GO、147 独立窗口不显著 + 尾部切除转负；A 168h 做空期望负 | 2026-08-07 关闭；认知：拥挤多头 24h 弱回落仅作减仓提示 |
| E18 | wash_cvd + 4h 反弹确认（148） | **shadow**（143 账户 C 已接线） | historical | re-slice | 168h +3.56% vs V_ref +1.48%、中位数 +0.51% 转正；confirm−reject +5.04% CI[+2.95,+7.46]（n=792 vs 556） | s001 增强，shadow 接线待 Owner 签批 |
| E19 | 新上市 washout × 4h确认（s009） | **candidate**（全验证通过） | subset_robust | primary | 168h +5.82% CI[+2.30,+9.85] n=282、中位数 +1.97%、尾切 +1.54%、独立窗口 W1+9.47/W2+4.32、与 wash_cvd 重叠 24%（157） | 首个完整独立 edge 候选，待阈值敏感性与前向 |
| E20 | 低流动性 wash_cvd（s010） | **candidate** | historical | re-slice | 低层 168h +2.60% CI[+0.37,+4.63] n=445、单调 2.60/1.12/0.73、独立窗口两段一致（155） | 容量锚成立，成本敏感性待做 |
| E21 | 市场级清算风暴（s011） | **candidate**（前向已接线） | historical | primary | 58 次风暴后 168h 篮子 +2.86% CI[+0.09,+5.83]、中位数 +2.08% 转正、尾切 +1.99%（156） | 市场级择时，频率 2.4 次/月；2026-08-08 Coinalyze 源接通（196），前向积累中 |
| E22 | funding 测量语义（基建，非 edge） | **infra** | n/a | n/a | 2026-08-08 外部调研 + `funding_semantics` + 170 审计 | 删失/封顶样本不得当真实压力；不恢复 s005 方向 |
| E23 | GMM/HMM regime 过滤（服务 s001） | **candidate** | exploratory | primary | `regime_gmm` 2 态 EM smoke（171）；未接事件研究 | 只过滤/缩放，不作交易信号 |
| E26 | 选举周期门控（s016） | **candidate** | historical | primary | 选举前 6 月 wash_cvd -3.18% GO_SHORT vs 选举后 6 月 +5.89% GO_LONG（185，n=206/321）；SPX 中期后 12 月 19/19 上涨 +17.3%（1928-2026） | 2026-11-03 中期临近：当前=选举前窗口，wash_cvd 前向保守；11/3 后转强 |
| E27 | 宏观状态联合（184） | **candidate** | exploratory | primary | 降息×BTC低波动 = wash_cvd 最差环境（-4.81% GO_SHORT）；SPX 新高期强（+2.66%）；EASING 单状态弱 | 与 182 VIX_SYNTH 高波动发现一致（低波动弱） |
| E24b | VIX_SYNTH 高门控（182 复核） | **candidate** | historical | re-slice | 高波动环境 wash_cvd +4.26% CI[+2.04,+6.50] 中位数 +1.67% 转正、独立窗口同向（182） | s001 环境门控增强候选 |
| E24 | funding 市场中性 carry（s014） | **candidate** | exploratory | primary | alpha_card 预注册 2026-08-08 | 强制中性；与 s005 方向假设分离 |
| E25 | 新币微观结构增强（s015） | **candidate** | exploratory | primary | alpha_card 预注册；叠加 E19/E20 | 代理点差/冲击；池漂移约束 |
| E28 | U 场外溢价 × BTC 抄底（P7） | **candidate**（前向积累中） | exploratory | primary | 197 日快照已建（Binance/OKX P2P + USDCNH；首值 -92.6bps）；198 事件框架；**Dune 历史版（202）**：Curve 3pool USDT/DAI 1830 天（2020-09→今，仅耗 4.4/2500 credits）——**3pool 脱锚与 BTC 大跌日几乎不重叠（56 大跌日中仅 1 深脱锚），大跌日 7d 超额 -3.99% CI[-6.83,-0.92] 显著负（大跌不反弹，与 164 一致）→ 链上 USDT 折价不是 BTC 抄底同日信号**；P2P 场外溢价（资金流 gauge）前向继续积累 | 信用风险 vs 资金流双 gauge 互补；n=1 深脱锚样本（2020-09-17 V 底 +13.3%/7d） |
| E29 | 本地-全球冲击分解（211 因子 8） | **candidate**（环境门控） | exploratory | primary | local_shock = z(alt 横截面波动+广度压力) − z(VIX)；高 T3 24h +1.90% vs 低 +0.16%，**高−低 +1.74% CI[+0.55,+3.02]（独立日 369）**——加密内部清杠杆后的 wash_cvd 反弹更强（score 已正交 VIX）；与 E24b（VIX_SYNTH 高门控）互补 | 环境门控候选（与 E24b/E26/E27 同类，接 108 需 Owner 签批）；需复核与 VIX 门控/regime 重叠度 |

## 检验预算（多重检验纪律，P1_5_B_GAUNTLET §9 迁移）

- 累计已测研究线：~22（112-141 + 旧项目 20+ 因子 HARD_FAIL 记录）；旧结果不能自动获得 `historical_pass`。
- Harvey-Liu-Zhu 门槛对照：M≈20-100 区间 → 新因子 t-stat 门槛 **≥3.0**（传统 2.0 不够）。
- 季度配额：1 主问题 + 2 预注册次假设；需要预注册文件和消耗日志，未登记结果强制标注 `exploratory`。
- 前向晋级规则：历史显著 → 仅 shadow；前向事件计数窗口（n≥60-100 或 2 个独立时间块）通过 → `forward_pass`，再由 Owner 决定 live。

## Decay 监测（与 109 --all 配套）

- 判决单位：**事件计数窗口**（非日历窗口）——30 事件预警块、60-100 事件正式块。
- 判定对象：**净超额收益**（相对 wash_cvd 默认档）；E01 母边另报告扣除成本/滑点后的现金收益。
- 经济阈值：若滚动 30 事件点估计低于 **+0.30pp 净超额**，进入 watch；正式 60-100 事件块需同时满足点估计持续低于阈值且功效足够，连续 2 个独立块才可 decaying/retired。
- CI 跨零 = 证据不足，不触发退役；CI 上界<0 是强恶化信号但不是唯一退出条件。
- 每个前向事件保留 regime/流动性/触发条件标签（108 已输出 regime/vix/liquidity 列）。
- 若仅特定 regime 衰退 → 先按预注册适用域限缩，不用事后挑 regime。


## 幸存者偏差声明（2026-08-08，183 修正版 + 195 完整版）

- 历史 universe 仅含活跃币；但 183 下架币复测（31 个已摘牌永续，1h 数据，s009 同口径）证明：
  **washout+4h 确认机制在下架币池同样有效（168h +6.25%，中位数 +2.58%，n=877）**——核心机制不是幸存者运气。
- **195 完整版（2026-08-08）**：master 差分重建 158 下架永续（SETTLING 127 ∪ GONE 31，可用 156），
  **带 CVD 层的完整 wash_cvd 复测（3307 事件）**：全组 168h +2.42%（超额 +3.30% CI[+2.36,+4.35]）、
  +4h 确认 +4.53%（超额 +5.42% CI[+4.06,+6.81]、中位 +0.42% 转正）、无确认 -0.31%（超额 +0.57% NO_GO）。
  分 episode 24h 超额：2022 +0.34 NO_GO / 2023 +0.66 GO / 2024 +0.21 NO_GO / 2025+ +1.39 GO（幸存池 115 引用
  +1.21/+1.75/+1.46/+0.85）→ **核心机制（卖压枯竭 + CVD 枯竭 + 4h 确认）跨幸存/下架池一致成立，
  但幅度系统性薄于幸存池（2023 约 40%、2024 不显著）→ E01 历史幅度含真实幸存者成分，前向预期下修**。
- 偏差真实影响面：裸 washout 无确认（下架币 +0.07% vs 幸存 +1.40%，日线口径）和 30 天长 horizon（179）。
- 之前"新币高估 5.7pp"判断基于日线近似，已撤回（1h 粒度下确认机制跨幸存/下架池一致）。
- 对冲不变：前向影子验证无偏差，为最终裁判。详见 reports/survivorship_bias.md + delisted_s009_retest.md + delisted_full_retest.md。

## 决策记录

- 2026-08-08：**E21 前向接线（196，Coinalyze 源）**：Owner 注册 Coinalyze free key（local_secrets.yaml）→ 66/66 universe 符号映射（**56 币安 .A + 10 股票/商品代币降级 OKX .3**，映射表 data/coinalyze_symbol_map.csv 留档；⚠️ 首版映射混所 bug 已修：DOGE→BitMEX 等，修复后标定大幅改善）、回填 2026-05-01→今 1h 清算（稀疏事件序列，零填充整点网格）。标定（reports/coinalyze_calibration.md）：市场级 **corr=0.955、ratio(cl/cg)=0.92（≈1:1，证实 coinglass 本地即币安口径）**；共享窗风暴 coinglass 8 / coinalyze 5，**命中 5/5（72h 内）**，频率≈2 次/月。前向风暴日志 e21_forward_storms.csv 已建（6 次：05-18/05-23/05-26/06-02/06-05/07-27），3 次有篮子收益（24h +0.37% n=3 样本不足）；binance klines 05-31 起，早于该点的风暴只记账不判。**计划任务 AlphaHiveV3_Coinalyze_Sync（每日 08:30，sync+storm）Owner 已签批 2026-08-08**；30 事件块约需 12 个月。
- 2026-08-08：**P6 下架 universe 重建完成（193-195）**：193 master（S3 986 ∪ exchangeInfo 854 差分，10 类）；194 全量 1h klines（158 下架永续，含 taker 列，vision zip 回退 4 个 -1121，vol>0 截断；SXP/AERGO/BDXN 表头 bug 修复）；195 wash_cvd 下架池复测（见幸存者偏差声明）。**E01 机制跨池成立但幅度下修**——历史 168h +2.70% 的幸存者成分估计约 20-50%（episode 依赖），前向判决（2026-09-18 首批）成为幅度真相的唯一裁判。脚本 193/194/195 头部有完整说明。
- 2026-08-08：**外部 X 量化深度调研落地**（`reports/external_intel/x_quant_digest_2026-08.md`）：StepOneAi 资金费率测量/删失口径 → `harness/lib/funding_semantics.py` + `config/funding_measurement.yaml` + 脚本 170；套利豪仔 GMM regime → `regime_gmm.py` + 171 smoke；非方向小钱 → s014 carry / s015 新币微结构预注册。**不复活 s005**。下一季主槽建议：S1 语义基建（已开工）+ S2 GMM 过滤（smoke 完成，事件接合待预算）。
- 2026-08-08：**B2 止损验证 + 签批落地**：-10% 止损在 wash_cvd 事件上是负优化（均值 +2.42%→+1.12%、胜率 47%→39%，180）——V 型反弹被插针止损砍掉；4h 确认（E18）是更优尾部控制。**Owner 签批（2026-08-08）：账户 B 止损 -10% → -20%**（补测：均值 +1.82%、胜率 45%、触发率 46%→13%、最差单笔 -40.9%，trailing 50% 几乎不触发）；143 已改，旧 PENDING 按新规则结算。B 账户从"负优化参数基线"转为"折中风控基线"。
- 2026-08-07：**双账户虚拟交易上线**（`scripts/143_paper_trade.py`，08:40 计划任务，复用 alpha_hive 旧基建参数）：账户 A=固定持有 24h 时间退出（与统计口径一致），账户 B=止损 -10%/trailing 50%/168h 上限 + MDD 断路器（chassis/cluster1 参数）；成本 27bps 单边；$1000/事件、$10000 初始。B 未满 168h 标 PENDING 不误判。已实测 2 笔（A：ONDO -5.12% 与 109 ret_24h 完全吻合、ADA +6.27% 与 +7.23% 差 1% 因入场用下一 bar open），468 tests 全过。
- 2026-08-07：**全市场交叉验证首轮（144，Pyth 六资产 washout）**：NVDA GO_LONG +1.90% CI[+0.13,+3.76] n=45 胜率 64%、168h +4.83%；SPY/QQQ 样本不足但方向正（+0.56/+0.59%，168h +4.5/+6.0%）；黄金/白银/英镑 NO_GO——**washout edge 是高波动资产特性**（山寨/NVDA 有，贵金属/外汇无），机制理解强化。探索性 6 次检验，NVDA 需独立样本复核；Pyth 时间戳单位是秒（冷却 bug 已修）。
- 2026-08-07：**s002 扩展复核（TSLA/MSTR/COIN/AMD）+ s006 跨市场避险**：① 扩展池 4 股全 NO_GO → "美股高波动 washout 类别效应"**未复制**，NVDA 单资产符合 10 检验假阳性画像（CI 下界 +0.13 贴 0），降为观察项——预注册复核成功拦截假 edge；② BTC 崩盘（n=28）后黄金 -0.41% CI[-0.65,-0.16]、白银 -1.11% CI[-1.51,-0.66] 显著**负**超额（72h XAG -7.9%）→ 加密崩盘 = 全球流动性事件、避险资产同跌，**避险脉冲假设证伪**（认知资产：崩盘日不做多贵金属）。
- 2026-08-07：Grok 审计 141/台账；修正 E02 为“131 主结果+134/141 同窗子集稳健”，E12 为“主对照不显著、功效不足”，补 `state/evidence_grade/independence` 与经济退出阈值。
- 2026-08-07：E12 完成 141 研究；作为不纳入筛选栈的候选/认知资产保留，不宣称已证无增量或机制完毕。
- 2026-08-07：E02 的 141 表3作为清洗子集内稳健性证据，不称独立确认或超可加。
- 2026-08-07：EDGE_LEDGER 建立（gpt plan 评审 + gemini 行业实践调研后落地）。

## 冻结规格绑定表（2026-08-09 增补，三级漏斗 S1 产物登记处）

| spec_id | family_id | 冻结公式 | forward_start | 状态 |
|---|---|---|---|---|
| FAM-001 | FAM-001 | score_vol = clip((log(qv24_ratio)-log(1))/(log(2)-log(1)), 0, 1) | 待 S1 冻结后填 | 管道已部署（108/109 标注，NA 门控，2026-08-09） |
