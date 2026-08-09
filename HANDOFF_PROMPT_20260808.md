# 交接提示词 — AlphaHive V3（2026-08-08 全量版，新对话唯一入口）

> 用途：**整段粘贴给新 agent 作为第一条指令**。本文件是当前唯一接管文档；
> `HANDOFF_PROMPT_20260807.md` 及其前身已归档为历史。新 agent 按 §0 顺序读完后即可无断点接手。

## 0. 动手前必读（按顺序）
1. `G:\Quant test\AlphaHive_V3\AGENTS.md`
2. `G:\Quant test\AlphaHive_V3\PROJECT_REQUIRED_READING.md`（强制阅读顺序 + 安全边界 + 任务分派规则）
3. 项目记忆（单一真相源）：`C:\Users\10639\.claude\projects\C--Users-10639\memory\project_alpha_hive_v3_contract_anomalies.md`
4. `QUANT_METHODOLOGY.md`（量化宪法：edge 分类/10 步管线/统计纪律/执行细则）
5. `EDGE_LEDGER.md`（25 条 edge 生命周期台账 E01-E27，含幸存者偏差声明）
6. `QUANT_PRE_REGISTRY.md`（检验预算账本）+ `QUANT_PROPOSALS.md`（提案池）

## 1. 当前状态（一句话）
**研究侧全量收官+拓展完毕**：wash_cvd 体系（母信号+9 条件+4 层门控）为唯一主线，s009 新币×确认全验证通过并接线前向（D 账户 +$920），选举周期/宏观状态/VIX_SYNTH/SPX 传导等新门控维度已挖出（E26/E27/E24b/s017），meta-labeling 双目标证伪、幸存者偏差修正（核心机制跨下架池有效）、非方向现金流（carry/CEX-DEX/解锁）路径已探明。**前向影子验证期**：6 个每日任务自动运行，s001 首批判决约 2026-09-18。

## 2. 文件索引（全部在 G:\Quant test\AlphaHive_V3）
- `scripts/`（103 个，编号 105-189）：108 扫描 / 109 影子 / 143 四账户虚拟交易 / 159 新币监测 / 169 s013 积累 / 171-189 研究（每脚本头部有完整说明）
- `harness/lib/`：event_study.py（bootstrap_ci/forward_stats）、contract_anomaly_features.py、funding_semantics.py
- `strategies/`（7 卡）：s001 wash_cvd / s002 美股（关闭）/ s005 funding（证伪）/ s009 新币×确认 / s014 carry / s015 新币微结构
- `reports/`：全部输出（研究报告 / paper_positions / 看板 dashboard.png / external_intel/ 外部调研）
- `config/`：规则配置（改动=T3 需 Owner 签批）；`data/`：pyth_raw / newlisting_raw / delisted_raw 缓存
- 外部数据（C 盘）：`C:\Users\10639\Desktop\🔒 加密资产\coinglass_db`（历史主源）、`C:\Users\10639\Desktop\加密\binance_free_db`（前向区）
- 测试：`tests/` + `harness/tests/`（473 passed，`python -m pytest -q`）

## 3. 全部结论速览
### 活跃 edge / 候选（详情见 EDGE_LEDGER）
- **s001 wash_cvd**（shadow）：168h +2.7%；E18 4h 确认 +3.56%（账户 C）；9 条件筛选（E02 liq 激增最强 +4.44%）
- **s009 新币×确认**（shadow，D 账户）：+5.82% 全验证通过；前向 +$920（主要来自股票代币池）
- 候选：E19/E20/E21（全验证待前向）、E24 VIX_SYNTH 高门控（+4.26%）、E26 选举门控（选举后 6 月 +5.89%）、E27 宏观状态联合、s017 SPX 新高传导（24h +1.47%）
- 非方向：E24b carry（KITE +10.1%）、CEX-DEX 扫描（主流池无空间）
### 关键认知（18+ 条）
- wash_cvd 是**趋势内回调工具非抄底工具**（164：牛市插针强/深熊瀑布弱）；新币与成熟池周期行为**相反**
- **幸存者偏差修正**（183）：4h 确认机制在下架币池同样有效（+6.25%）——核心机制非运气；裸 washout 和 30 天窗仍高估
- **-10% 止损是负优化**（180）：V 型反弹被插针砍掉，4h 确认是更优尾部控制
- **山寨是 BTC 负凸性**（189）：跌市 beta 1.46 > 涨市 1.38，高 beta 篮子无 α
- 降息×BTC 低波动 = wash_cvd 最差环境（当前正是）；大选前 6 月弱/后 6 月强（2026-11-03 中期）
- meta-labeling 均值口径证伪（177/178）；资金面全证伪；funding 无 cap 删失
### 证伪清单（预算账本）
s002 美股类别效应 / s005 funding 反转 / s006 避险 / s007 FOMC / s008 meme / s014 部分 / 单特征裸事件 16/16 / GMM 门控 / 止损 / meta-labeling

## 4. 每日任务链（Windows 计划任务，全部用 hermes venv python）
07:35 108 扫描 → 08:35 159 新币监测 → 08:40 143 四账户结算 → 08:50 169 s013 → 09:10 174 看板 → 每小时 173 CEX-DEX。飞书卡片通知（scan/forward/paper 三种）。

## 5. 当前待办
1. **Coinalyze 免费 key**（Owner 注册）→ E21 前向动工（方案在 external_intel/parallel_forward_datasources.md）
2. **P1/P3/P5 测试**（QUANT_PROPOSALS.md：负凸性交易/降息×新币/BTC.D 断裂）——数据全有待跑
3. **账户 B 止损参数**（-10% 负优化，建议弃用/调宽，待 Owner 签批）
4. **187 稳定币溢价**数据源不理想（CoinGecko 聚合价偏离 0.06%），降级待 DEX 数据
5. 下架币完整 universe 重建（binance.vision S3 路径已探明，见 parallel_delisted_history.md）
6. 前向判决等待：s001 30 事件块约 2026-09-18；账户 D 持续积累

## 6. 多通道路由（不变）
ds=opencode 本地算力 / gemini=agy.exe 外部调研 / grok=grok.exe 独立审计 / gpt-5.6-terra+sol=aitokensale 网关（OPENAI_GW_API_KEY 系统环境变量 + 浏览器 UA）。FRED key 在 `config/local_secrets.yaml` 且已配 OpenBB。

## 7. 新 agent 第一步
1. 按 §0 顺序读全部必读文档（含记忆文件、EDGE_LEDGER、方法论宪法）
2. 跑 `python -m pytest -q` 确认 473 基线
3. 读 §3 关键报告（EDGE_LEDGER 决策记录 + external_intel/ 索引）
4. 汇报：当前状态确认、待办优先级建议、可并行派发项
5. 有新产出：更新记忆文件 + 本文件追加交接点段


## 8. 交接点追加（2026-08-08 晚，P 系列 + 宏观状态）
- **P1 负凸性**（190）：空高beta+多BTC 月均 -0.70% 胜率 13%——负凸性不可交易，仅认知（189 结构事实保留）
- **P3 降息×新币**（191）：降息期新币×确认 +2.66% NO_GO vs 非降息 +7.21%——新币不独立于降息
- **P5 BTC.D**（192）：成交额占比代理无调制（低位−高位 -0.71%），关闭
- **选举周期**（185）：SPX 中期后 12 月 19/19 上涨 +17.3%（1928-2026）；wash_cvd 选举前 6 月 -3.18% / 后 6 月 +5.89% → E26
- **宏观状态联合**（184）：降息×低波动=-4.81% 最差；SPX 新高 +2.66%；大选前 -3.42% → E27
- **VIX_SYNTH 高门控**（182）：+4.26% 中位数转正独立窗口同向 → E24b
- **SPX 新高→山寨滞后**（186）：24h +1.47% / 72h +2.16% GO_LONG → s017
- **平静→爆发**（188）：方向不可测，关闭
- **当前窗口判断**：2026-08 = 三重负面（大选前+降息+低波动）→ wash_cvd/s009 前向保守；2026-11-03 后转强
- 提案池机制运转（P1/P3/P5 已处理，见 QUANT_PROPOSALS.md）
- 全量 473 tests 过；handoff 本文件为唯一入口

*交接点：2026-08-08。研究拓展收官，前向验证期；6 任务自动链 + 看板运行中。*

## 9. 交接点追加（2026-08-08 深夜，P6 下架 universe 重建完成）
- **P6 完成**（待办 #5 清项）：193 master（S3 986∪exchangeInfo 854 差分，`data/delisted_master.csv`）+ 194 下架永续全量 1h klines（158 池、156 可用，含 taker 列可算真 CVD）+ 195 wash_cvd 下架池复测（`reports/delisted_full_retest.md`，3307 事件）
- **E01 幸存者偏差终极结论**：核心机制（wash_cvd + CVD 枯竭 + 4h 确认）跨幸存/下架池一致成立（下架池 +4h确认 168h +4.53%、超额 +5.42% CI[+4.06,+6.81]；分 episode 2023/2025+ GO）；**但幅度系统性薄于幸存池**（2023 约 40%、2024 不显著）→ E01 历史幅度含真实幸存者成分，**前向预期下修**（历史 168h +2.70% → 幸存者成分约 20-50% episode 依赖）；2026-09-18 s001 首批前向判决成为幅度真相唯一裁判
- 待办更新：① **Coinalyze key 已接入（196）→ E21 前向动工完成**：66/66 映射（56 币安 .A + 10 OKX 降级，混所 bug 已修）+ 05-01→今回填 + 标定（corr 0.955、ratio 0.92、共享窗风暴命中 5/5）+ 风暴日志建立（6 次，e21_forward_storms.csv）；**同步任务 AlphaHiveV3_Coinalyze_Sync 每日 08:30 已签批**（与 hermes 币安拉取不重复：hermes 拉 klines/OI/funding/taker，196 只拉清算）；② **账户 B 止损已签批：-10% → -20%（143 已改，补测均值 +1.82%、触发 46%→13%）**；③ **P7 新开（Owner 批准）：U 场外溢价 × BTC 抄底**——197 日快照（Binance/OKX P2P + USDCNH，首值 -92.6bps 折价）+ 198 事件框架已建，**纯前向积累（P2P 无免费历史）**，每日快照任务待签批；④ 187 稳定币溢价降级为 P7 附属（场内对仅作旁证）；⑤ 前向判决等待中（s001 30 事件块约 09-18、D 账户 +$1,686/251 笔 持续积累、E21 约 12 个月、P7 约 2-6 个月）
- 新坑记录：vision zip CSV 部分月档带表头行（194 已修）；shell cwd 漂移（用显式 cd/绝对路径）；183 手选清单含 15 个仍在交易币（勿当样本）
- 提案池：P1/P3/P5/P6 已处理，剩 P2（等 11 月）/ P4（等 DEX 数据）
- 全量 473 tests 过；handoff 本文件为唯一入口

## 10. 交接点追加（2026-08-08 深夜，全盘梳理+升级启动）
- **梳理**：`reports/framework_audit_20260808.md`（治理层清楚、工程层 8 条不清晰）+ `reports/upgrade_plan_20260808.md`（4 阶段计划）
- **外部调研**（reports/external_intel/）：gemini 裁决 OpenBB custom provider 不建议（自研 Streamlit+Plotly+DuckDB）；grok 裁决停止全市场自动挖 edge（wash_cvd 内正交边际 + purged CV + 假设注册预算）
- **已执行**：data_paths.yaml + data_registry（统一路径）、199 数据健康（抓到 macro SP500/VIX 过期 74h 待查）、200 回撤可视化、data_cleaning 统一清洗管线（软校验先于硬校验，测试锁住）、196 口径收敛示范；**480 tests**
- **待办/决策点**：D1 Streamlit vs Dash（建议 Streamlit）；D2 DuckDB 暂缓；D3 因子预算 ≤20-50/季；D4 199/200 并入每日链；**查 118 宏观任务为何 08-06 后未更新**
- 旧 web 项目 alpha_hive/dashboard 按 V3 口径重建；新看板面板建议：四账户净值+HWM+水下曲线、MDD 区间、Top-N 回撤归因、事件流、E21/E28 前向日志

## 11. 交接点追加（2026-08-09，签批落地 + 数据源决策）
- **交互看板 Owner 决定搁置**（不急）；D1 待后续
- **两个任务已签批创建**：`AlphaHiveV3_OTC_Premium`（每日 09:00，197+198 链式）→ P7 溢价序列开始每日积累；`AlphaHiveV3_DataHealth_Drawdown`（每日 09:15，199+200 链式）→ 数据健康监控 + 回撤图进每日链。任务链现为 11 个：07:00 宏观/07:35 扫描/08:05 CME/08:30 Coinalyze/08:35 前向+新币/08:40 纸面/08:50 cyclez/09:00 OTC/09:10 看板/09:15 健康+回撤/每小时 CEX-DEX+MC
- **Coinglass 付费 API：不接入（决策）**——维度盘点：klines（coinglass 历史+binance 前向=全史）、funding（110 回填全史）、OI（coinglass+binance 30d+vision 深史）、清算（coinglass 历史+Coinalyze 前向=全史）、CVD 近似（179 证明与真 CVD 事件层面等价 93% 重叠）、np_z 前向缺口（binance topLongShortPositionRatio 30d 弱代理可替代，重测阈值）。付费恢复的只是近似等价/负向过滤器，边际价值低
- **Dune API 已接入（Owner 提供 key）**：`harness/lib/dune_mcp.py`（MCP JSON-RPC 客户端）+ 201 回填 Curve 3pool USDT/DAI 1830 天（2020-09→今）+ 202 恐慌日回测——**结论：3pool 脱锚与 BTC 大跌日几乎不重叠（56 日仅 1 深脱锚）、大跌日 7d 超额 -3.99% CI[-6.83,-0.92] 显著负 → 链上 USDT 折价非 BTC 抄底同日信号**（与 164 认知一致）；v3 USDT/USDC 0.01% 池全史钉 1.0 弃用（负结果记录）；耗 4.4/2500 credits。扩展候选：链上大户储备

## 12. 交接点追加（2026-08-09 深夜，因子漏斗落地）
- **框架落地**：三级漏斗（S0 沙盒 213 / S1 挑战者待建 / S2 前向确认）+ 事件宽表 + 族级记账 + 历史=development 声明（QUANT_METHODOLOGY 2a/2b）。两份外部审查（codex 仓库级 + grok 独立）已归档 external_intel/（codex56sol_factor_mining_practice / codex_upgrade_framework / grok_upgrade_review）。
- **FAM-001 放量 S0 合格**（IC +0.127、单调、两段同号）→ S1 冻结 score_vol 待做（214 脚本）。
- **待办**：VIX 语义冲突核对（108 vs E24b）；S1 挑战者；108/109 score annotation；FAM-002/003/004 沙盒。
- git：d07f4fd（checkpoint）+ d2f94b7（漏斗），工作树干净；push 待 Owner。
