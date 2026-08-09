# AlphaHive V3 框架全盘梳理（2026-08-08）

> 目的：回答"框架/策略/逻辑是否梳理归类清楚、有无不清晰"；为后续数据整合、可视化、
> 深度清洗、自动因子提取升级提供基线。本文件是盘点快照，不替代 EDGE_LEDGER/宪法等权威文档。

## 1. 分层架构现状

```
┌─ 治理层 ─────────────────────────────────────────────────────────┐
│ 宪法/墓地/方法论宪法/EDGE_LEDGER(28 edge)/预算/提案池/审批/交接     │
├─ 策略层 ─────────────────────────────────────────────────────────┤
│ strategies/ alpha_card（s001 wash_cvd / s009 新币×确认 / s014 carry │
│ / s015 新币微结构 / s002·s005 已关闭）+ EDGE_LEDGER 生命周期状态机   │
├─ 运行层（Windows 计划任务，每日链）──────────────────────────────┤
│ 07:00 宏观 118 → 07:35 扫描 108 → 08:05 CME 125 → 08:30 Coinalyze 196│
│ → 08:35 前向 109 + 新币 159 → 08:40 纸面 143 → 08:50 cyclez 169 →  │
│ 09:10 看板 174 → 每小时 CEX-DEX 173（+ OTC 197 待挂）               │
├─ 研究层 ─────────────────────────────────────────────────────────┤
│ 100-198 共 97 个编号研究脚本（事件研究 112-198 全量）→ reports/*.md │
├─ 特征/事件研究层（harness/lib，33 测试文件 473 tests）──────────────┤
│ event_study / contract_anomaly_features / regime_engine+gmm /       │
│ funding_semantics / market_cap_provider / asset_identity_registry /  │
│ canonical_data / paper_plan_engine / offline_execution_simulator /   │
│ deep_research_package / local_notification_outbox …（约 30 模块）     │
└─ 数据层 ─────────────────────────────────────────────────────────┘
  历史主源 coinglass_db（🔒 加密资产，klines→07-07，衍生→06-23 停更）
  前向区 binance_free_db（无 emoji，05-31→今，hermes 每小时）
  项目内缓存 data/：pyth_raw / newlisting_raw / delisted_raw /
    coinalyze_liquidation / market_caps / macro / otc_premium /
    delisted_master / coinalyze_symbol_map
  外部 API：FRED / yfinance / akshare-CME / P2P / Uniswap RPC / Pyth
```

## 2. 策略/逻辑归类是否清楚

**清楚的**：
- Edge 生命周期状态机完整（candidate→historical_pass→shadow→forward_pass→live→decaying→retired），EDGE_LEDGER 每行含 state/evidence_grade/independence
- 检验预算记账（QUANT_PRE_REGISTRY，季度 1 主 2 次 + 探索段），提案池机制运转（P1-P7）
- 方法论宪法 10 步管线 + 成本模型 + 统计纪律（t≥3.0、同期基线、前向独立验证）
- 双账户纸面（A 统计口径 / B 风控口径）+ 账户 C（E18 确认）+ 账户 D（s009 新币）分流清晰

**不清晰的（升级对象）**：
1. **数据路径分散**：30+ 脚本硬编码绝对路径（coinglass_db 带 emoji vs binance_free_db 无 emoji），
   emoji 漂移已踩坑 2 次（记忆明确记载）——**无统一数据注册表/访问层**
2. **清洗逻辑重复**：_sanitize_close（108）、vol>0 截断（183/194）、hourly_grid 零填充（196）、
   gap 策略（canonical 快照）、_future_prices_at 断档 NaN（109）——各自实现，无统一清洗管线
3. **事件口径多处复制**：wash_cvd 定义在 115 被 180/195 复制；市场风暴 z 检测在 156/196 两份；
   61/97 研究脚本用 importlib 互引源码（spec_from_file_location）——脆弱、无版本语义
4. **研究脚本无测试**：一次性研究可接受，但 108/109/143/159/169/196/197 等"运行链"脚本
   只有 108/109 有单测；196/197 新增无测试
5. **可视化断层**：174 是静态 matplotlib PNG（OpenBB 只当 FRED 双源对照，未注册 custom provider、
   未用 charting）；旧 web 项目（alpha_hive/dashboard，Plotly+serve.py:8081）是因子研究时代的，
   因子已全 HARD_FAIL 过时——**V3 没有实时 web 看板**（账户净值/回撤/事件流/edge 生命周期）
6. **回撤可视化缺失**：143 输出 equity 序列，但无 drawdown/水下曲线/事件归因图
7. **自动因子提取只有雏形**：153 算子搜索（8 特征×双向×分位=16 候选全 NO_GO，结论"单特征极值
   不构成 edge，唯一有效结构是复合事件"）——无系统性因子挖掘管线
8. **数据整合缺对账层**：klines 三源（coinglass/binance/vision）各自为政；canonical price snapshot
   只服务旧扫描路径；无跨源一致性监控（coinglass 停更断点、空档 06-23→06-30 等靠人肉发现）

## 3. 数据流现状（已打通）

```
拉取：hermes(klines/oi/funding/taker 每小时) + 118 FRED + 107 MC + 125 CME
      + 196 Coinalyze 清算 + 197 OTC 溢价（新）+ 159 新币 + 194 下架（一次性）
清洗：各脚本内联（见上）
特征：contract_anomaly_features → wash_cvd/cvd_bear；regime_engine/gmm；funding_semantics
事件：108 扫描 → 109 前向收益 → 143 纸面（A/B/C/D）→ 174 看板
研究：112-198 事件研究 → reports/*.md → EDGE_LEDGER 决策记录
```

## 4. 升级方向清单（对应外部调研）

| # | 方向 | 现状缺口 | 外部调研问题 |
|---|---|---|---|
| U1 | 统一数据访问层 | 30+ 硬编码路径 | 数据注册表/路径配置最佳实践 |
| U2 | 统一清洗管线 | 4+ 套重复清洗 | 多源 klines 深度清洗/对账/质量监控 |
| U3 | 事件口径收敛 | 61 个 importlib 互引 | 研究代码模块化迁移策略 |
| U4 | OpenBB 升级 | 仅 FRED 对照 | OpenBB custom provider + charting 方案 |
| U5 | Web 看板 + 回撤可视化 | V3 无 web；无回撤图 | Plotly/Dash/Streamlit 对比；drawdown 指标集 |
| U6 | 自动因子提取 | 153 雏形 | 算子搜索/遗传/正交化/IC 管线 + 过拟合控制 |
| U7 | 数据整合对账 | 无跨源监控 | 增量同步/校验/告警架构 |

## 5. 本盘点结论

- 策略/治理/统计纪律层**归类清楚**（台账+预算+宪法三件套是强项）
- **工程层欠整理**：数据路径、清洗、事件口径三处重复/分散是主要"不清晰"；
  可视化断层是能力缺口；因子挖掘是未开发方向
- 优先序建议：U1/U2（数据整合，先做，降低踩坑风险）→ U5（看板+回撤，用户可见）
  → U4（OpenBB）→ U3（口径收敛，工程量最大）→ U6（因子挖掘，研究性）
