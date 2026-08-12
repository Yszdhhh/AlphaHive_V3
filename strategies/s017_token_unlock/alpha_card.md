# s017 Alpha Card — Token Unlock 卖压窗口（预注册）

> 预注册 2026-08-12。**exploratory / S0**。测试前锁定；禁止事后改定义。  
> 主槽候选（Owner：Unlock 主、carry 副）。在数据可得性审计通过前，不得宣称 GO。

## 1. 基础
- **ID**: s017
- **名称**: Token Unlock 归属解锁卖压窗口（残差空 / 低配）
- **edge 类别**: E-D 结构性供需（Predictable Flows — 合约归属日历造成可预期 float 冲击）
- **寿命论证**: 归属时间表是合约约束，团队/投资人解锁前后存在对冲与抛售动机；中小盘 float 薄、OTC 不能完全抹平冲击。机制消失条件：大所 OTC 对冲完善 + 仅剩高 VtMC 大盘解锁（文献显示效应主要在较早期/较薄 float）。
- **报酬来源四问**:
  1. **谁付钱**: 接住稀释/叙事卖盘的持币人与被迫跟随的多头
  2. **为何不立刻消失**: 日历公开但执行分散；薄盘冲击非机构主场
  3. **容量**: 单名通常偏小（中小盘）；组合分散解锁事件
  4. **成本后**: 必须扣除双边摩擦 + funding；残差相对 BTC/ETH，避免空 beta

## 2. 定义（测试前锁定）
- **universe**: 币安 USDT-M 永续中，能匹配到解锁日历且 ADV/流通市值过门槛的山寨（排除稳定币；BTC/ETH 仅作残差基准，不作交易腿）。首测可限非 BTC/ETH 山寨 + 有日历。
- **数据**:
  - 价格: coinglass / binance_free 1h OHLCV（已有）
  - **解锁日历（缺口，必须新建派生库，不改现有库结构）**: 事件日、解锁量、占流通比、接收方类别（team/investor/community/其他）、cliff vs linear
  - 流通/市值: CoinGecko 或现有 MC 快照（允许 asof，标 stale）
- **事件/信号（主规格，只此一条进 S1）**:
  - 事件日 T0 = 解锁执行日（UTC 日界，预注册后不改）
  - 入场: **T0−14d** 当日 00:00 UTC 后第一根完整 1h bar open（若当时无永续则跳过）
  - 方向: **空头**（残差：symbol_ret − β·BTC_ret，β 用事件前 30d 日收益回归，β clip 到 [0, 1.5]）
  - 过滤（全部满足）:
    1. 单次解锁量 / 流通量 ≥ 0.5%（敏感性预声明：0.25% / 0.5% / 1.0%，主规格 0.5%）
    2. 接收方 ∈ {team, investor}（community-only 为次形态，S0 可看但主规格不含）
    3. 事件前 7d ADV ≥ $2M（报价成交额）
  - 冷却: 同一 symbol 两次事件入场间隔 ≥ 7d
- **horizon**: 主评估 **T0−14d → T0**（解锁前窗口）；次报告 T0→T0+14d（只描述，不作主判定）
- **基线**:
  1. 同 symbol 随机 14d 窗口（匹配 ADV 分位）
  2. 同期有永续、无解锁事件的对照币横截面
- **成本**: 悲观 **27bps 单边 ×2**（开平）；持有期 funding 按实际结算计入
- **判定（S0 描述 → S1 holdout 一次评）**:
  - 主指标: 残差收益均值；bootstrap 95% CI（seed=20260812）
  - S0: 覆盖率、分桶单调（解锁占比）、两段时间同向（以 2024-01 切）
  - S1: 前 80% 只用于确认形态不改规格；后 20% **只评一次**；CI 下界>0 且中位数≥0 才可申请 historical_pass 候选
  - n 门槛: 主规格事件 ≥ 80（否则样本不足不升级）

## 3. 约束
- **不改** coinglass / binance_free / AlphaHive data 源结构；日历进派生目录（建议 `G:\Quant test\derived_data\token_unlocks\`）
- 禁止与 wash_cvd / 清算风暴事件简单 OR 合并成新主信号（正交族；重叠只报告）
- 禁止用解锁日当天高低点做入场（防前视）
- 多重检验: 本卡占 **2026-Q3 主槽概念族 1**（Unlock）；族内仅允许预声明的占比阈值敏感性
- 与关闭族: 非 funding_family / 非 coil / 非 netflow 主信号

## 4. failure（什么算证伪）
- S1 holdout 残差 CI 含 0 或中位数 < 0
- 成本 2× 后净期望 ≤ 0
- 效应仅存在于单年或单交易所叙事币（去掉 top 10% 事件后失效）
- 仅 BTC beta，残差化后消失
- 数据源日历与链上实际解锁系统性错位（可得性审计失败）

## 5. 里程碑
- [x] Owner 确认本卡锁定（2026-08-12 执行线）
- [x] 数据可得性审计（`scripts/s017_unlock_data_audit.py`；77 币探针）
- [x] 派生库首版（`derived_data/token_unlocks/`）
- [x] S0 沙盒本地（`scripts/s017_s0_local.py`）→ WEAK_OR_MIXED @0.5%
- [x] S1 holdout（`scripts/s017_s1_holdout.py`）→ 选中 **1%**；eval 统计门控过；**Lead：SEI 集中冻结升级**
- [x] 扩日历（Mobula×coinglass 109 币）+ 冻结1%再诊断 → SEI 46%；Verdict 仍 MIXED；**免费源触顶**
- [x] **Owner 2026-08-12：A 为主** — 停扩历；本卡降 **观察**；不进增量/前向默认队列
- [ ] 增量检验 vs s001 — **暂停**（重开条件见 Lead 简报 §7）
- [ ] 前向影子 — **暂停**
- [ ] Tokenomist — **仅 Owner 改口 B 时**

## 6. 与调研对齐
- 外部调研 2026-08-12：Unlock 为个人小资金首选新事件族
- 明确 **不是** 价格形态 / coil / 方向 funding