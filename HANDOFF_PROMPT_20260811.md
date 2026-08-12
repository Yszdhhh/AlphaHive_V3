# AlphaHive V3 交接提示词（2026-08-11）

> 供其他 agent 接手本项目的完整上下文。项目目录：`G:\Quant test\AlphaHive_V3`（私有库 Yszdhhh/AlphaHive_V3，push 已获 Owner 批准）。
> 最新 commit：`af08665`（515 pytest + 19 subtests 全绿）。本文件与 `memory://root`（OMP 记忆）互为印证，冲突时以本文件+仓库现状为准。

## 1. 快速启动

```bash
cd "G:\Quant test\AlphaHive_V3"
python -m pytest -q                    # 515 tests 全绿是接手基线
python scripts/199_data_health.py      # 数据健康快照（今日全链路状态）
python scripts/143_paper_trade.py      # 虚拟交易结算+报告（每日 08:40 任务）
```

## 2. 系统是什么

单机 Windows + pandas/parquet 的个人量化研究系统。**纯研究/影子验证，不碰真钱**（执行层 botv2 已整体 NO-GO，另写小执行内核的计划搁置中）。

### 每日链（14 个计划任务 AlphaHiveV3_*，全部北京时间）
| 时间 | 任务 | 产出 |
|---|---|---|
| 07:00 | Macro_Refresh | 宏观（SP500/VIX/CME） |
| 07:35 | Contract_Monitor | 108 候选 → `reports/contract_monitor_candidates.csv` |
| 08:05 | CME_Snapshot | CME 溢价 |
| 08:30 | Coinalyze_Sync | 清算数据（E21 前向源） |
| 08:35 | Forward_Replay | 109 前向收益积累+判决 |
| 08:35 | Newlisting_Monitor | 159 新币候选（s009） |
| 08:40 | Paper_Trade | 143 虚拟交易结算 |
| 08:45 | Exec_Diagnosis | 执行诊断 |
| 08:50 | CycleZ_Forward | cycle_z 信号 |
| 09:00 | OTC_Premium | 场外溢价 |
| 09:10 | Dashboard | 看板+回撤图 |
| 09:15 | DataHealth_Drawdown | 199 数据健康+200 回撤 |
| 每小时 | CEXDEX_Scan | TDI 三角失衡（173 列） |

### 事件流（三级漏斗）
- **108**（wash_cvd/cvd_bear）：每日实时扫描 → `forward_replay_returns.csv` 前向积累（A/B/C 账户事件源，8-06 起，无历史回填）
- **159**（s009 新币×确认）：每日扫描新币池（上线<90天）→ `newlisting_candidates.csv`（⚠️ **首次运行回填了池内新币全历史 washout 事件**，见账户 D 说明）
- **s001**：8-09 起的前向影子，7 候选，30 事件块判决约 2026-09-18

## 3. 虚拟交易账户体系（143）——数据性质必须分清

| 账户 | 事件源 | 执行 | 数据性质 |
|---|---|---|---|
| A | wash_cvd | 24h 固定持有（统计锚，无止损） | 实时扫描（8-06 起，无回填）；8-09 前 7 笔=dev 区 |
| B | wash_cvd | 止损-20%/trailing/168h/MDD | 同 A（B−A=风控增量） |
| C | wash_cvd | 4h 反弹确认入场，163h | 同 A（V_confirm 口径） |
| D | 新币×确认（s009） | 163h 固定 | ⚠️ **265 笔结算 100% 历史回填（6-01~8-04，development）**；前向影子 8-09 起 7 笔候选持仓中，最早 8-16 结算 |

**铁律（2026-08-11 Owner 质疑后核实确立）**：D 的 +$2,4xx 收益是历史回测口径，**不能当前向证据**。报告/卡片已标注"数据性质"+持仓批次列（前向/回填/dev）。任何展示脚本不得再把历史回填结果伪装成影子交易。

## 4. 推送体系

- 目标：**quant 群** `oc_b09f882231082604d0796e5af1c7c266`（`scripts/alphahive_feishu_notify.py`，群优先+DM 回退，`FEISHU_CHAT_ID` 可覆盖）
- 四类卡片：scan（📡 信号）/ forward（📊 判决）/ paper（💰 虚拟交易，含 D 收益摘要+最差浮盈5笔+单币Top5）/ error（⚠️ 简洁错误：原因+位置）
- **展示时间一律北京时间**（`TZ_CN = timezone(timedelta(hours=8))`），计算层保持 UTC
- digest 去重：`reports/feishu_notify_state.json`

## 5. 铁律与约束（Owner 明示）

1. **三级漏斗纪律**：2026-08-09 前 = development；最终确认只认前向；关闭族禁换皮
2. **大改动流程**：codex-sol（订阅）出规划 → grok/Gemini 审查 → 条件满足才动手
3. **下一步确认格式**：每次提"下一步"必须附推荐顺序 + 正反面影响；几乎无反面影响的纯增量/研究侧任务直接跑
4. **A 账户 27bps = 统计口径锚不可变**（真实成本 16.2bps，只加列不替换）；143 与 rules 零改动（除非 Owner 签批）
5. 密钥不入库（gitignored）、不回显；`config/local_secrets.yaml` 是密钥文件
6. 个人系统、避免过度工程（opentelemetry/DuckDB/Web 看板已搁置；Coinglass 付费 API 不接；Dune 限定历史回填用途）
7. **已关闭族**（禁换皮）：single_feature_extreme、funding_family、meta_labeling、stablecoin_etf_netflow、cvd_slope、attention_sentiment、oi_quadrant、FAM-001~004、知识库方向全族（bias<-15%=washout 重叠、ahr999 抄底开关、td9/donchian/vol_div、squeeze）
8. **wash_cvd 确认维度实证排序**：放量>1.5x（+1.90%）> 无确认 > 缩量分型确认（-0.39pp）——实证赢过知识库理论
9. 外部 agent 派发：禁止给"读不了就基于通用知识"退路（gemini 曾输出教科书内容）；深度拆解必须给足读取工具并抽查

## 6. 数据源与健康

| 源 | 位置 | 状态（2026-08-11） |
|---|---|---|
| binance_free_db | `C:\Users\10639\Desktop\加密\binance_free_db`（无 emoji！） | ✅ 每小时拉取，klines/oi/funding/taker |
| coinglass_db | `C:\Users\10639\Desktop\🔒 加密资产\coinglass_db`（带 emoji） | ⚠️ klines 停 07-07、衍生停 06-23（预期） |
| coinalyze | `data/coinalyze_liquidation` | ✅ 每日 08:30 |
| otc_premium | `data/otc_premium.csv` | ✅ 每日 09:00 |
| Dune | `scripts/dune_mcp.py` | 社区 2500 credits/月，约 10 已用 |
| binance.vision | 手动/月度 | 全标的 aggTrades + BTC 日线（µs 坑：>1e14 除 1000） |

路径统一走 `harness/lib/data_registry.py` + `config/data_paths.yaml`；清洗统一走 `harness/lib/data_cleaning.py`（199 已接入抽样检查）。

## 7. 进行中（前向积累，只等时间）

- s001 前向影子：7 候选，30 事件块判决约 2026-09-18
- D 账户前向（s009）：8-09 起 7 笔候选，最早 8-16 结算
- E21 风暴日志：6 次积累中
- P7 OTC 溢价序列：快照积累中
- 173 TDI/CEX-DEX 价差：+2.25bps，1-2 月后有样本
- 方向 A 新币生命周期：<60d 确认 +8.65% GO_LONG，前向继续
- s013 cycle_z×Mayer：0 事件待触发

## 8. 待办/阻塞

- **E29 环境标注接入 108**（annotate-only，同 vix_gate 先例）——Owner 已签批过一次？确认最新状态；若已签批则实施
- AHR v2（动态幂律+RealizedPrice）：链上 realized price 免费源 2026 已死，数据不可得
- 执行层 Phase 2 测试网网关：T3 搁置
- 鲸鱼数据 canonical 地址修复：parked
- E27 门控口径与 184 冲突：待复核
- 信息源挖掘流水线（每周 2h grok/gemini 候选概念池）：可选

## 9. 常用操作

- **模型路由**：codex 订阅 `codex exec --skip-git-repo-check --dangerously-bypass-approvals-and-sandbox -c 'model="gpt-5.6-sol"'`；agy.exe = gemini（`--model gemini-3.6-flash-high`）；grok.exe 独立审查；task/scout = DeepSeek V4 Flash
- **测试**：`python -m pytest -q`（515 基线）
- **推送验证**：`python scripts/alphahive_feishu_notify.py paper --dry-run`（dry-run 不发送）
- **跑任务**：`python scripts/run_shadow_task.py --kind scan|forward|paper <script>`（计划任务用同款 wrapper）
- 计划任务查询：`powershell Get-ScheduledTask | Where TaskName -like 'AlphaHiveV3*'`（LastTaskResult 0=成功）

## 10. 交接注意

- 用户（Owner）在 `G:\交易储备知识库` 有大量资料（缠论/价格行为/民间交易员/结构化 YAML），此前两轮提炼全部拦截（价值在留档）
- 用户风格：质疑数据真实性（曾揪出 D 账户历史回填冒充影子交易）——**接手后先核实再汇报，标注数据性质**
- EDGE_LEDGER.md 是策略记账本；QUANT_PROPOSALS/ 是待办池；记忆单源在 `C:\Users\10639\.claude\projects\C--Users-10639\memory\project_alpha_hive_v3_contract_anomalies.md`
