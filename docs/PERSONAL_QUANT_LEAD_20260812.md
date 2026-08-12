# AlphaHive 个人量化 — Project Lead 简报（2026-08-12）

> 角色：本对话主 agent = **Quant Lead**（机制/预算/晋级/否决权）。  
> 代码与重脚本 = **执行 agent**（只实现 Lead 冻结的 task 卡）。  
> Owner = 唯一签批人。  
> 依据：`PROJECT_CONSTITUTION` / `QUANT_METHODOLOGY` / `HANDOFF_20260811` / `GRAVEYARD` / EDGE_LEDGER / s017·s018 S0。

---

## 1. 我们是谁（适配性，不是红海说明书）

| 维度 | 本系统定位 |
|---|---|
| 资金/容量 | 个人小名义（事件 ~$1k 级）；**Capacity Edge** 在薄盘，不在 BTC/ETH 机构主场 |
| 工程 | 单机 Windows + parquet；研究/影子，**不碰真钱**（botv2 执行 NO-GO） |
| 频率 | **中低频事件**（小时～天～周）；禁止亚秒/做市 HFT 主线 |
| Universe | 山寨中间段 CORE；Major/MEME 只诊断 |
| 成功 KPI | 可审计假设数、前向事件块；**不是**公开赛道赛 Sharpe |

**刻意避开（红海 / 已踩坑）**

- 高频做市、订单簿 HFT、全市场日频横截面换手机器（旧项目换手杀）
- funding **方向**反转（s005 retired；FAM-C2）
- 裸 funding 横截面 **8h 猛调仓 CS_MN**（s018 S0：fund 正、price+成本灭；与机构 carry 同赛道但无库存优势）
- 单特征极值喷泉、聪明钱跟随、机械 BTC 择时（墓地）
- 热门叙事赛道：纯 meme 情绪、保证月化、黑箱卖参

**个人友好（应占预算）**

| 类型 | 为何适合个人 | 当前状态 |
|---|---|---|
| E-A 清杠杆后卖压枯竭 | 低频、机制硬、已有前向链 | **s001 wash_cvd 主线**（影子至 ~09-18） |
| E-D 时间锚新币 | 机构覆盖差、小名义 | **s009/D 账户**（注意回填≠前向） |
| E-D 解锁可预期流 | 日历公开、事件稀疏、容量小 | **s017** S0 混；S1 在途 |
| E-A 非方向收租（低频） | 只在极端费率机会开 | **s014** 预注册；≠s018 |
| 环境门控 | 减亏不增交易次数 | E26/E29/VIX 等 annotate |

---

## 2. 知识库 / 「专家」从哪调

本仓库**已内化**的专家层（Lead 默认加载，不另起炉灶）：

| 源 | 路径 | 用途 |
|---|---|---|
| 方法论 | `QUANT_METHODOLOGY.md` | S0/S1/S2 漏斗、成本、预算 |
| 宪法 | `PROJECT_CONSTITUTION.md` | Capacity、不实盘 |
| 墓地 | `GRAVEYARD.md` | 禁换皮清单 |
| 因子采矿实践 | `reports/external_intel/codex56sol_factor_mining_practice_20260809.md` | 概念族、形态词典 |
| X 情报 | `reports/external_intel/x_quant_digest_2026-08.md` | 非方向小钱、funding 语义 |
| 交接 | `HANDOFF_PROMPT_20260811.md` | 账户数据性质铁律 |
| 红队 | `prompts/red_team_prompt.md` | 换手/容量拷问 |
| Owner 资料库 | `G:\交易储备知识库`（YTC/Brooks/缠论/民间） | **历史结论：方向/形态理论勿直接进主栈**；最多作「主观标签」旁路，禁与 wash_cvd 换皮 |

**没有**单独的「外部 Quant 真人专家 API」。Lead = 上述文件 + 本简报的综合裁决。

---

## 3. 本轮裁决（基于刚跑完的 S0）

### s018 CS_MN — **停主线，不进 S1，不丢 VPS**

- 证据：70 币面板，fund +1.9bps/期，price −8bps，net27 −32bps；降频仍负。
- 适配性：**红海形态**（截面费率收割）+ 高换手，个人无库存/借币优势。
- 动作：卡保持预注册痕迹；EDGE **S0 红线**；若再开必须**新卡**（例如「仅 spread>阈值 的稀疏事件」，非每 8h 全调仓）。

### s017 Unlock — **唯一值得立刻消耗的 S1 槽（探索）**

- 适配性：事件稀疏、E-D 可预期流、非 HFT、容量天然小 → **符合个人**。
- 主规格 0.5%：mean+ 但 CI 跨 0、pre/post 不同向 → 不能 GO。
- 预声明敏感性含 0.25/0.5/1.0%。按漏斗：**前 80% 时间只选形态，后 20% 只评一次**。
- 动作：执行 agent 跑 `s017_s1_holdout`（见 task 卡）。**禁止**看完 holdout 再改阈值。

### s001 / s009 — **不抢戏**

- 前向块在走；Lead 不并行开新方向喷泉。本周代码预算优先 s017 S1。

### s014 — **保持休眠**

- 与 s018 不同（现货–永续对冲）。仅当出现「高 funding 且可对冲」的稀疏机会再唤醒审计，不做日更横截面。

---

## 4. 工作流：Lead vs 执行 agent

```
Owner 意图
   ↓
Lead：读墓地/预算/S0 → 写 task 卡（成功标准/禁区/输出路径）
   ↓
执行 agent：只写代码+跑本地脚本+写 reports/
   ↓
Lead：验收数字性质、是否泄漏 holdout、是否越权升级
   ↓
Owner：是否改卡 / 是否前向
```

**执行 agent 禁区**：改 `143` 成本锚、复活 s005、把 gross 当 net、宣布 historical_pass/GO、改 s014 定义、大范围重构。

---

## 5. 下一步队列（推荐序）

| 序 | 任务 | 谁 | 本地/VPS |
|---|---|---|---|
| **1** | s017 S1 holdout | 执行 ✅ | 本地 → 脚本 `S1_PASS_CANDIDATE`；Lead **集中冻结** |
| **1b** | s017 降集中诊断 | 执行 ✅ | `MIXED_NEED_MORE_CALENDAR`（`reports/s017_deconcentrate.md`） |
| **1c** | 扩日历 + 冻结1%再诊断 | 执行 ✅ | SEI 权重 **79%→46%**；full CI+；leave-SEI CI 仍跨0；Verdict 仍 **MIXED**（`s017_expand_diagnose.md`） |
| 2 | Mobula 免费路径已触顶（109 候选仅 ~20 有 schedule） | Lead | 再扩需 **Tokenomist/付费** 或停线 |
| 3 | 若 Owner 接受「SEI+ARB+UNI 主导的稀疏事件组合」可做前向影子小名义 | Owner | 非 historical_pass |
| 4 | s018 写入 GRAVEYARD 附注（CS_MN 8h 主规格） | Lead | — |
| 5 | Tokenomist | Owner 要机构字段时 | VPS/付费 |
| — | 前向 s001/s009 | 日任务 | 等时间 |

### 已落地执行结果摘要

- **s018**：个人不适配红海 → 停。
- **s017 S1**：选中 1%；eval +2.95% CI 正；**SEI 79%** → Lead 禁升级。
- **降集中**：leave-SEI 全样本仍正；leave-top3 CI 穿 0；簇化 SEI 98→2；**filt 稀疏 cliff mean +5.06% CI_lo+1.59%**（仅诊断，未改卡）。

---

## 6. 一句话战略

> **个人系统只打：低频、可解释、容量不适配机构的边。**  
> 主线仍是 wash_cvd + 新币时间锚；本季结构增量试 Unlock；截面 funding 红海收工。

---

## 7. Owner 决策落盘：A 为主（2026-08-12）

| 项 | 内容 |
|---|---|
| 决定 | **A 为主**：停 Unlock 扩历，注意力回 s001/s009 前向 |
| 不做 | 默认不做 B（Tokenomist）、不做重 C 影子接线 |
| s017 | 预注册+S0/S1/扩历报告**留档**；状态=**观察**；禁 historical_pass |
| s018 | 维持停主线 |
| 重开 s017 | 仅 Owner 明示新数据源或接受集中影子 |

**Lead 执行口径：** 后续默认 task 优先日任务健康 / 前向块 / 数据完整性；Unlock 仅问答与归档，不主动派扩历 agent。
