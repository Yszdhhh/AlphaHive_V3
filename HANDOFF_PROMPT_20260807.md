# 交接提示词 — AlphaHive V3 山寨合约异动研究（2026-08-07 第六轮收官版）

> **核心信息（一句话概括）**：
> ▏ 研究已收官：wash_cvd（砸坑+卖压枯竭做多）是唯一验证 edge，5 层筛选（最强=空头强平激增 +4.44%）、组合四条件 +8.45%、宏观/资金面/情绪全部测完。项目在跑前向影子定时任务（约 4 个月后验证），无待办研究。红线：只读、shadow_only、配置版本锁需签批、pytest 468 基线、emoji 路径别搞混。

> 用途：**整段粘贴给新 agent（Claude/Codex/其他）作为其第一条指令**。新 agent 从本任务继续，不要重复已完成的研究，不要自己拍板方向；遇到不确定先读 §3 对应报告与记忆文件。

## 0. 动手前必读（按此顺序，全部读完再动代码/数据）

1. `G:\Quant test\AlphaHive_V3\AGENTS.md`
2. `G:\Quant test\AlphaHive_V3\PROJECT_REQUIRED_READING.md`（它定义强制阅读顺序 + 安全边界 + 任务分派规则，逐份读完）
3. 项目记忆（当前状态 + 全部结论索引，**最优先的单一真相源**）：
   `C:\Users\10639\.claude\projects\C--Users-10639\memory\project_alpha_hive_v3_contract_anomalies.md`
4. 历史交接记录（多轮累积，含每轮结论）：`G:\Quant test\AlphaHive_V3\HANDOFF_20260806_macro_factor_chain.md`

> ⚠️ 关于 `PROJECT_REQUIRED_READING.md` 中"Only Codex writes AlphaHive_V3/"：**Owner（用户）已直接授权本研究线程持续写 AlphaHive_V3/**（scripts 112–140、reports、config v3 均由本线在 Owner 直接指挥下写出）。新 agent 以 Owner 的直接指令为准，可继续在项目内写研究脚本/报告，但必须遵守宪法红线（§5）。

## 1. 当前状态（2026-08-07 一句话）

**研究侧已全部收官**：wash_cvd 信号体系（基础信号 + 5 层筛选 + 组合矩阵）、宏观、资金面、情绪、免费数据源全部测完（脚本 112–140，报告 30+ 份，468 tests 全过）。**项目进入前向影子验证期**——108/109 定时任务每日自动扫描积累真实候选，约 4 个月后样本够了回来验证历史结论。当前无待办研究，唯一可做的是 Owner 待确认项（见 §4）。

## 2. 应用 / 代码 / 数据在哪

- **项目根**：`G:\Quant test\AlphaHive_V3`（脚本/库/配置/报告/测试全在这）
- **核心库** `harness/lib/`：`event_study.py`（bootstrap_ci/draw_random_events/forward_stats/DEFAULT_HORIZONS）、`contract_anomaly_features.py`、`regime_engine.py`、`market_cap_provider.py`、`asset_identity_registry.py`
- **研究脚本** `scripts/`（112–140，全可 `python scripts/NNN_xxx.py` 默认参数跑通）：
  - 事件地基：113（load_price_ctx/load_funding_series/EPISODES/episode_of，**所有研究复用的加载器**）、115（detect_events "wash_cvd"）
  - A 线：112/114（funding 证伪）、113（washout-settle）、115（组合选型 wash_cvd）、116（相对强弱）、121（燃料分层）、126（放量组合）、131/134/135（强平流）、133（联合矩阵）、136（0xEggg 三元组）
  - 宏观：117/118（FRED 数据层）、119（交叉研究）、120（调制）、122（隔夜）、123（VIX 门控）、129（独立性诊断）、137（E-mini）
  - 市场/情绪：124/127（广度）、130/132（恐惧贪婪）、138（谷歌趋势/GDELT）
  - 新数据：125（CME 快照）、128（稳定币）、139（ETF 净流入）、140（交易所净流入）
  - 前向：108（监控，已接 wash_cvd+cvd_bear 双 trigger + vix 门控标注）、109（forward replay 闭环）、107（MC 每日快照）
- **配置** `config/`：`contract_anomaly_rules.yaml`（**v3**，wash_cvd 含 vix_gate）、`scan_rules.yaml`（v2）、`market_regimes.yaml`、`universe.json`、`macro_sources.yaml`、`local_secrets.yaml`（gitignored，FRED key，不外发）
- **报告** `reports/`：核心 4 份先读 `A_line_synthesis.md`、`macro_crypto_study.md`（119）、`macro_factor_modulation.md`（120）、`research_frontier.md`（130）；新 agent 必读 `independence_diagnosis.md`（129）、`joint_matrix.md`（133）、`liquidation_cross.md`（131）、`eggg_triple.md`（136）
- **测试**：项目根 `python -m pytest -q` = **468 passed + 19 subtests**（基线）

**数据位置（两个目录名不同，别搞混，emoji 路径漂移是反复坑）**：
- coinglass 历史（**带 emoji 🔒**）：`C:\Users\10639\Desktop\🔒 加密资产\coinglass_db`（raw_1h/klines、raw_1h/oi_ohlc、**raw_1h/liquidation**、macro/、funding_ohlc 等；klines 到 2026-07-07，⚠️ 2026-06-23 23:00→06-30 04:00 约 6.3 天全 universe 空档）
- binance 前向（**无 emoji**）：`C:\Users\10639\Desktop\加密\binance_free_db`（无 liquidation/真 CVD，CVD 用 taker 近似）
- 宏观+新数据（**带 emoji**）：`...\coinglass_db\macro\`：SP500/VIX/DOLLAR/TREASURY/CPI/GDP/WTI/GOLD/稳定币（stablecoin_supply_defillama.csv）/CME（cme_bitcoin.parquet）/恐惧贪婪（fear_greed_index.csv）/ETF 流（etf_flows_farside.csv）

## 3. 已完成结论（勿重做，需要细节读对应报告）

1. **唯一可交易 edge = wash_cvd**（washout 出清 且 cvd_divergence>2.0，72h 冷却，Long）：pooled n=1348，24h **+1.31%** CI[+0.66,+1.63]，168h +2.70%，3/4 episode GO_LONG（2022 例外=熊市普跌普反）。funding 确认是毒药（2022 反转为 GO_SHORT）；funding 择时/选币全证伪（112/114）。
2. **单层筛选（从强到弱）**：空头强平激增 liq_short_z>1 **+4.44%** CI[+1.98,+7.25]（n=123，2/2 episode；131/134）＞ 放量>1.5x **+1.90%**（4/4，直接增量 +0.78pp 显著；126）＞ 高 OI 分位 **+2.23%**（136）＞ 市场广度分层 +1.85%（124）＞ 谷歌趋势高分位周 +2.35%（138）＞ 情绪贪婪层 +1.48%（132）＞ VIX 低位门控 +0.27pp（123）。
3. **组合矩阵（133/134）**：**四条件全开（放量+VIX低+breadth≥5%+空头强平激增）+8.45%** CI[+3.55,+13.70]（n=57，单笔质量最高但样本 6.6%）；**≥2 条件档（72.7% 样本）总期望最大 = 稳健默认**（+1.60%/事件）；000 无条件子集 GO_SHORT（−2.09%）= 无燃料无确认的 wash_cvd 负期望。三条件近似正交（phi≈0），liq 与放量正相关。
4. **宏观（129 独立性诊断）**：研究设计/尺度问题为主，非"加密独立"——**同窗高相关**（同日 alt×SP500 r=+0.44，99.4% 交易日为正）+ **事件驱动**（FOMC/CPI 事件日 +1.13pp 显著）+ **周月慢变量**（周 +0.36/月 +0.56 显著）但**次日线性预测≈0**（119）；流动性通道（WALCL/RRP/稳定币/ETF 流/交易所净流入）全证伪；**连续"BTC 先动→alt 后动"轮动不存在**（lag1 显著负）——蓄力 alpha 只能走事件通道。
5. **资金面统一证伪（128/139/140）**：稳定币供给、ETF 净流入、交易所净流入三大资金面**都不预测次日、都不调制 wash_cvd**（唯一描述性亮点：交易所净流入高日 wash_cvd +2.24% 待复核）；wash_cvd edge 是币种级杠杆/清算结构内生。
6. **强平级联 2025 失效机理（135）**：非 z 失敏/非时滞，主因=市场语境（2025 下跌中继=中继燃料 vs 2024 崩后=底部确认）；可条件化修复（2025 +breadth≥5% 翻正 +1.52%，但短周期抢反弹）。
7. **0xEggg 框架验证（136 + gemini 调研）**：成交异动 ✅、高 OI ✅（代理）、负费率组合条件化后部分复活 ⚠️、低市值壳不可历史验证（无历史 MC，前向 107 积累中）、狗庄做空侧 ❌（无信号）；HEI 案例可查证（0.24→0.37，3x≈+162%），KOL 有幸存者偏差。
8. **数据现实**：OI 只 2024-06+（不可回填）；funding 回填到 2022（110）；coinglass klines 到 2026-07-07；binance_free_db = 前向区（到今）；历史 MC 缺失（CoinGecko 无历史）。

## 4. 当前唯一待办

- **前向影子验证期**（自动运行，无需干预）：108 每日 07:35 扫描（wash_cvd+cvd_bear，含 vix_gate 标注）、109 每日 08:35 forward replay、107 每小时 MC 快照、118 每日 07:00 宏观、125 CME 每日 08:05。**约 4 个月后**（2026-12 前后）回来用 109 积累的样本验证历史结论。
- **等 Owner**：① gpt 网关认证已确认（2026-08-07 晚，调用方式见 §6 表格——hermes 8642 与 aitokensale 均实测 200），第四通道可直接打通，无阻塞；② 无其它待签批项（C 门控已落地 v3、CME 已定时化、T3-1/T3-2 已用免费方案解决）。
- **可做（研究侧，无需签批）**：前向样本够了之后验证；或按 Owner 新指令扩展。

## 5. 治理红线（宪法，不可越）

- **全程用中文回复**。
- live 衍生数据触发保持 `DISABLED`；contract_anomaly_triggers 只在 historical_replay + 前向影子。
- `scan_rules.yaml`（v2）/ `contract_anomaly_rules.yaml`（v3）版本锁：任何值改动需 Owner 签批 + 版本号 +1。
- 新建模块一律只读、无订单路径；shadow_only=true（候选默认 Watch，不自动进 Paper）。
- 回测穷尽再谈纸面；外部数据必须有时间戳+来源 URL；FRED key 只在 `config/local_secrets.yaml`，永不写入代码/报告/外发。
- 改代码后跑 `python -m pytest -q`（468 全过是回归基线）。
- 墓地（GRAVEYARD.md）：funding 选币/择时、机械方向择时、跟随聪明钱已证伪，不得复活为交易机制。

## 6. 多模型通道路由（Owner 要求：正确网关调正确模型，不占错订阅额度）

| 通道 | 调用方式 | 用途 |
|---|---|---|
| ds/国产（opencode go 订阅） | task 子 agent / 当前会话 | 本地算数/脚本（⚠️ **不得**用 opencode 调 gpt/grok，占 go 额度） |
| gemini（谷歌，anti-gravity） | `C:\Users\10639\AppData\Local\agy\bin\agy.exe --prompt "..." --model gemini-3.6-flash-high --print-timeout 15m`（⚠️ 必须 `--prompt` 全称，`-p` 不执行；timeout 用 Go duration 如 `15m`） | 外部调研/联网查证 |
| grok（独立订阅） | `C:\Users\10639\AppData\Local\agy\bin\grok.exe -p "..."` | 独立第二意见/代码审计 |
| gpt（专属网关+订阅） | hermes 8642：`Authorization: Bearer <API_SERVER_KEY>`（key=`C:\Users\10639\AppData\Local\hermes\.env` 内 `API_SERVER_KEY` 值，非 hermes-api-2026）；aitokensale codex provider（api.aitokensale.com，gpt-5.6-terra）：`Authorization: Bearer <OPENAI_GW_API_KEY>`（环境变量）+ **必须带浏览器 User-Agent**（Cloudflare UA 校验，无 UA 一律 403） | ✅ 认证已确认（2026-08-07 晚，实测 /v1/models 200） |

## 7. 新 agent 的第一步动作

1. 读完 §0 全部必读文档（含记忆文件——它是最新最全的单一真相源）。
2. 核对 §2 路径；读 §3 列出的核心报告（A_line_synthesis / macro_crypto_study / macro_factor_modulation / research_frontier / independence_diagnosis / joint_matrix / liquidation_cross / eggg_triple）。
3. 汇报：当前已完成项、唯一阻塞项（若有）、Owner 决策项、可并行派发项。
4. 跑 `python -m pytest -q` 确认基线 468 全过。
5. 有新产出后：更新记忆文件 + 本文件追加交接点段。

*交接点时间戳：2026-08-07。研究侧收官，进入前向影子验证期。*

*交接点追加（2026-08-07 晚）：① 修复 `118_fred_macro.py` gold 单行 squeeze 降维 bug（GC=F 仅 1 根 bar → float64 → `'numpy.float64' has no attribute 'to_frame'`）——Macro_Refresh 定时任务 08-07 07:00 Result=1 的根因；GOLD 已补齐 08-07，hermes venv（任务同款解释器）幂等验证通过；② gpt 网关认证确认（§6 表格，两通道均实测 200）；③ 回归复确认 468 passed + 19 subtests；④ **修复 109 前向影子闭环断点**：108 每天覆盖 candidates csv 而 109 只算当日候选 → 旧候选在积累 csv 里收益永远 NaN（4 个月后无样本可验证）。已加：旧积累收益缺失行自动回填 + `--all` 全量验证模式（到期后 `python scripts/109_forward_replay.py --all` 一键验证），实测 08-06 旧候选 4h/24h 收益已回填。⑤ **旧项目侦察（4 scout 并行）+ edge 生命周期管理落地**：新增 `EDGE_LEDGER.md`（15 个 edge 生命周期台账 + 检验预算 + decay 规则）；109 加 **decay 监测**（事件计数窗口 30 事件/块 + CUSUM k=0.5 h=4.5 + 累积判决）；**141 四象限研究完成**（`reports/oi_quadrant_cross.md`）：OI×价格四象限是 wash_cvd 机制描述（82% 事件在清杠杆象限）**非增量筛选器**（清洗 vs 堆集 +0.01% CI 跨零），但 141 表3 **第三次独立确认空头强平激增**（清洗×激增 +5.13% CI[+2.18,+8.56] vs 无激增 +0.39%，差 +4.74% CI[+1.72,+8.08]）。⑥ gpt/gemini 外部调研：gpt 评审（第四通道首次实战）建议治理优先（EDGE_LEDGER/冻结版本/非重叠窗口/经济阈值/季度检验预算）；gemini 调研行业实践（事件计数窗口 N≥60-100、CUSUM、Harvey-Liu-Zhu t≥3.0 门槛、三阶梯退出）。*
*交接点追加（2026-08-07 深夜）：① Grok 独立审计 141/EDGE_LEDGER：141 统计可复现但事件池/象限合并/iid bootstrap/pooled 2025 弱化需保留；已将 E02 改为“131 主结果+134/141 同窗子集稳健”，E12 改为“主对照 +0.01pp、CI 跨零、功效不足”，台账补 `state/evidence_grade/independence` 与经济退出阈值。② 新增 `scripts/142_lcs_susceptibility.py` / `reports/lcs_susceptibility.md`：LCS=OI/rolling24h quote_volume、symbol 内 rolling30d q75/q90、train 2024/holdout 2025+。实测 861/867 可用，q75=60、q90=13；holdout 增量 q75 +1.38pp CI[-1.58,+5.33]、q90 +2.04pp CI[-1.42,+5.39]，均样本不足/未确认，不进配置。③ 扫描/影子仍是两个独立计划任务；两任务现经 `scripts/run_shadow_task.py` 调用 Hermes venv，结束后由 `scripts/alphahive_feishu_notify.py` 去重推送管理员私聊；凭据仅读 Hermes `.env`，不写项目。108 有新候选/错误才通知，109 仅有 GO/衰退预警/错误才通知。④ 已完成一次真实 Feishu DM 烟测并写入 `reports/feishu_notify_state.json`；发送成功。⑤ **双账户虚拟交易上线**（复用旧项目 alpha_hive 基建，非从零搭）：`scripts/143_paper_trade.py` 每日 08:40 跑（任务 `AlphaHiveV3_Paper_Trade`），账户 A=固定持有 24h 时间退出（与统计口径一致，已实测与 109 ret_24h 吻合）、账户 B=止损 -10%/trailing 50%/168h 上限 + MDD 断路器（参数抄 chassis_engine/cluster1_live_sim）；成本 27bps 单边；$1000/事件、$10000 初始；B 未满 168h 标 PENDING；输出 `reports/paper_positions.csv` / `paper_equity_A/B.csv` / `paper_trade_report.md`，结算事件走飞书通知（kind=paper）。
⑥ **飞书通知改结构化卡片**（schema 2.0）：📡扫描(蓝)/📊影子判决(靛)/💰虚拟交易(绿)/⚠️失败(红)，去重不变；实测送达；⚠️ 飞书 2.0 卡片 `note` 元素会 400，用 markdown 元素替代。⑦ **全市场交叉验证启动（144）**：Owner 拍板"品类不再限于加密山寨"——gemini 侦察结论（gTrade/Ostium/Synthetix/Delta 均有 funding+清算机制、Pyth 免费分钟级数据；Polymarket 是概率市场排除）；`scripts/144_chain_assets_washout.py` 对 Pyth 六资产（黄金/白银/英镑 24/7 + SPY/QQQ/NVDA 美盘）做 washout 事件研究（无 CVD 维度诚实标注）；Pyth 免费档限流窗口 ~30-60s，fetch 需 30s 退避重试 + 1.5s 间隔 + 90 天分段；2022-01 段 403（从 2022-06 起）。**首轮结果**：NVDA GO_LONG +1.90% CI[+0.13,+3.76] n=45（168h +4.83%，胜率 64%）；SPY/QQQ 样本不足方向正（168h +4.5/+6.0%）；黄金/白银/英镑 NO_GO——washout edge 是高波动资产特性。⚠️ Pyth TradingView shim 的 t 是**秒**单位（冷却按秒算，毫秒会放大 1000 倍只留 1 事件，已修）。*
