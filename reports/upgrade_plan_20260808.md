# AlphaHive V3 全盘升级计划（2026-08-08，codex 出计划版）

> 输入：框架梳理报告（framework_audit_20260808.md）+ gemini 外部调研（数据清洗/可视化/
> OpenBB）+ grok 外部调研（自动因子提取/统计纪律）。调研原文见 reports/external_intel/
> gemini_dataclean_viz_research_20260808.md、grok_factormining_research_20260808.md。

## 0. 核心判断

- **治理/策略/统计纪律层已清楚**（EDGE_LEDGER+预算+宪法三件套是强项），**不重建**。
- **工程层欠整理**（数据路径、清洗、事件口径三处重复分散）→ 本计划的主战场。
- **可视化断层**：V3 无交互看板、无回撤图；旧 web 项目（alpha_hive/dashboard）是因子研究
  时代的（因子已全 HARD_FAIL），需按 V3 口径重建而非复用。
- **自动因子提取**：grok 明确裁决——**停止全市场自动挖 edge**；自动提取降级为"wash_cvd
  事件条件分布内的强约束交互/正交边际搜索"，算子搜索只作假设生成器。
- **OpenBB**：gemini 明确裁决——**不注册 custom provider**（非标衍生数据建模僵硬、
  升级频繁 breaking），自研 Streamlit+Plotly+DuckDB 更务实；OpenBB 保留 FRED 双源对照用途。

## 1. 已完成（本会话，U1/U5 打底）

| 交付 | 说明 |
|---|---|
| framework_audit_20260808.md | 分层架构盘点 + 8 条不清晰点 + U1-U7 升级方向 |
| config/data_paths.yaml + harness/lib/data_registry.py | 统一路径注册表（emoji 坑终结）+ 新鲜度检查 |
| scripts/199_data_health.py | 数据源健康监控（已抓到一个真问题：macro SP500/VIX 过期 74h） |
| scripts/200_drawdown.py | 回撤统计 + 水下曲线图（A 账户 -0.6% / D 账户最大 -39.4% 步 203，当前 -5.1%） |
| 外部调研 2 份 | gemini（清洗/架构/可视化）+ grok（因子挖掘纪律）已落 external_intel/ |

## 2. 分期计划

### Phase 1：数据整合层（0-2 周，T1 为主）
1. **数据访问层迁移**：data_registry 已建 → 逐脚本替换硬编码路径（优先运行链 108/109/143/159/196/197/174，研究脚本按需）。验收：`grep Desktop` 只剩 data_paths.yaml。
2. **统一清洗管线**（gemini 5 步金字塔落地到 harness/lib）：
   - `clean_hourly_klines`（时间网格对齐/去重/硬校验/720h 中位数软校验/vol>0/ffill≤3h/零填充稀疏列/quality_flag 位掩码）——吸收 108 `_sanitize_close`、183/194 vol 截断、196 `hourly_grid` 为同一函数
   - 验收：同一函数的单测锁住（新增 tests/test_data_cleaning.py）
3. **跨源对账监控**：199 扩展——klines 双源（coinglass vs binance 重叠窗）价差 >1.5% 连续 2 bar 告警；停更/空档自动发现。
4. **DuckDB 查询层（可选，T2 决策）**：partitioned parquet + duckdb 视图做统一查询（gemini 建议）；先行方案 = 保持 parquet + registry，DuckDB 仅当跨文件聚合变痛时引入——**避免过度工程，先不做**。

### Phase 2：可视化升级（2-4 周，T1 + Owner 选型）
5. **回撤/净值交互看板**（Streamlit+Plotly，gemini 推荐）：
   - 面板：四账户净值+HWM+水下曲线（已可复用 200 逻辑）、MDD 区间标注、Top-N 回撤事件归因、事件流表（108 候选+109 收益+143 结算）、E21/E28 前向日志
   - 离线 HTML 导出
   - **Owner 决策点**：Streamlit（最快）vs Dash（生产级）——建议 Streamlit
6. **174 静态看板升级**：并入 200 回撤面板 + 数据健康状态条（199 输出）；OpenBB FRED 双源保留
7. 定时任务：199 数据健康并入每日链（如 09:05）

### Phase 3：事件口径收敛 + 因子挖掘纪律（3-8 周，T1/T2）
8. **事件口径收敛**：wash_cvd 检测/市场风暴 z/滚动 z 移入 harness/lib（当前 115/156/196/180/195 各有一份）→ 研究脚本 import 库而非互引源码（61 个 importlib 场景逐步消解）
9. **Hypothesis Registry**（grok 建议）：
   - 新假设必须注册：id/叙事/特征公式/预算消耗=1/黑名单族（funding 极值、单特征 high、稳定币/ETF/GDELT）
   - 已测族相关 >0.7 → HARD REJECT；季度正式假设 ≤20-50 次记账
10. **正交边际三关（M1/M2/M3）**：仅 wash_cvd 事件集内做——条件分层（≥3/4 episode 同号）、回归边际（date cluster）、嵌套策略（n 保留 ≥40%）；purged k-fold + embargo（168h purge、2-3d embargo、date-level split、leave-one-episode-out）
11. **明确不做**（grok P3）：全域因子动物园、meta-label 2.0、规则五条件再叠、无预算算子网格、OpenBB custom provider

### Phase 4：前向验证衔接（持续）
12. E21/P7 前向积累不变；新增因子一律走 shadow（事件计数窗 n≥30/60 + L0-L3 衰减状态机）

## 3. 风险与 Owner 决策点

| # | 决策点 | 建议 |
|---|---|---|
| D1 | web 看板技术栈 | Streamlit + Plotly（最快落地，离线导出） |
| D2 | DuckDB 引入 | 暂缓（避免过度工程），registry+parquet 先行 |
| D3 | 因子挖掘季度预算 | 正式假设 ≤20-50/季；黑名单族硬拒 |
| D4 | 199/200 并入每日链 | 建议：199 每日 09:05、200 并入 174 |

## 4. 一句话总纲

> 治理层不动，工程层收敛（统一路径→统一清洗→统一口径），可视化补齐（Streamlit 回撤看板），
> 因子挖掘从"全市场找新 edge"转向"wash_cvd 内正交边际 + 生命周期工程"。
