# Meta-Labeling 深拆与 AlphaHive V3 对照方案

- 生成：2026-08-08 UTC
- 性质：研究方案（外部权威文献 × 本地体系对照）
- 上游依据：`reports/external_intel/authoritative_quant_research_pipeline_deep_dive_2026-08.md` §2.3（AFML 一节）+ 联网核验（López de Prado AFML 原书、Joubert 2022 JFDS 论文、Hudson & Thames 实施解读）
- 涉及对象：s001 wash_cvd（一级）、E18 4h 确认、s009/s010、账户 A/B/C/D、gauntlet 验证体系

---

## 0. TL;DR（明确判断）

1. **我们的 4h 确认/筛选层与 meta-labeling 是同构的**：一级定方向（wash_cvd）、二级定"做不做"。区别只在二级的实现——我们是**人工挑选的单特征硬阈值**（r4>0、<90d、流动性分层、周期门控，AND 逻辑），meta-labeling 是**多特征联合的概率模型**（P(一级成功 | 特征) + 阈值 T）。
2. **正式升级**需要：事件级标签（每个 wash_cvd 事件的 168h 成本后净收益 > 0）、现有全部筛选特征（asof 时点）、**purged k-fold CV**（我们的 72h 冷却 < 168h 标签窗 → 相邻事件标签重叠真实存在，naive k-fold 会泄漏）、判定门槛（OOF AUC + 对 V_confirm +3.56% 基线的增量 ≥ +1.0pp 且 CI 下界 > 0）。
3. **值得做吗：有条件值得——先做半天诊断性最小实验，不直接立项**。规则基线已很强（+3.56%、中位数转正、砍掉 41% 尾部）；ML 的现实增量不在"均值翻倍"，而在多特征交互与概率仓位（文献增益主要在 Sharpe/MDD）。n≈1348、胜率 ~50% 的事件样本注定 AUC 天花板低（预计 0.55–0.60）。最小实验风险为零（纯研究、不动账户），产出直接回答"联合特征是否超过手挑规则"。
4. **第一步（半天）**：拼事件×特征宽表（复用 148/157/161/160 全部已有列）→ asof 审计 → 复算基线 +3.56% → L1 logistic + 浅 GBM，purged k-fold（purge/embargo 168h）出 OOF AUC → T 扫描 → 对照判定。

---

## 1. AFML meta-labeling 核心要点（5 条，全部经原文/论文核验）

**① 定义（AFML 原书 Ch.3 §3.6，p.50，原文大意）**：
> 假设已有决定做多/做空的模型，你只需要学"下注大小"，包括零仓位。ML 算法被训练来决定**要不要下注**（纯二分类）；当预测标签为 1 时，用该二次预测的概率推导仓位大小，方向（符号）由一级模型决定。

- 关键：meta-model **不学方向、只学"做不做/做多大"**；一级负责 recall，二级负责 precision。
- 引文转载来源：Hudson & Thames (2019) 《Meta Labeling: A Toy Example》直接摘录原书 p.50 段落（已联网核对原文转载，非二手转述）。

**② 目的 = 提 F1、砍 false positives，而不是提准确率**：
- 一级模型先做到高 recall（宁可多报），meta 层把一级报出的 positive 里那些"假阳性"筛掉 → 组合 F1 提升。
- 对交易的含义：**小注高准确 vs 大注低准确会亏死你**——"识别机会"和"给机会正确配仓"是两件事，后者值得单独建模型。
- 附加价值（原书列举）：白盒/规则模型之上叠 ML（quantamental）；过拟合危害受限（ML 不决定方向）；可针对多头/空头分别建 meta 模型；文献中 meta-labeling 模型比标准 labeling 模型更稳健。

**③ Triple-barrier 标签（Ch.3）**：上障碍（止盈）、下障碍（止损）、竖障碍（时间退出），取**先触碰者**为标签 +1/-1/0。路径依赖，贴近真实交易结果（固定时点收益标签不反映"先爆仓还是先止盈"）。

**④ Purged / Embargoed CV（Ch.7）**：金融标签用前视窗口生成 → 相邻观测标签互相重叠 → 随机 k-fold 泄漏、高估表现。解法：
- **purge**：训练集中标签窗口与测试集区间重叠的观测，从该 fold 训练集剔除；
- **embargo**：测试集之后一段缓冲期内的训练观测也剔除（吸收序列自相关/波动聚集的残余依赖）。
- 推广形态 CPCV（组合 purged CV）：多路径测试分布，配合 PBO/DSR 评估过拟合。

**⑤ 概率阈值 T 与仓位映射（Joubert 2022 框架论文）**：
- Joubert, J.F. (2022) *Meta-Labeling: Theory and Framework*, Journal of Financial Data Science 4(3): 31–44：把概念整理成完整框架 + 受控实验。
- 实验结论：meta 层直接改善 **Sharpe 与最大回撤**；**阈值 T（最低执行置信度）的优化是最大化 Sharpe 的关键步骤**——T 越高 recall 越低、剩余交易质量越高；通过阈值后用 P 作置信度映射仓位（高置信 → 大仓位）。
- 特征工程指引：成功的 meta-model 通常同时用 **regime 特征 + 一级模型自身的特征**。
- 后续文献：Meyer et al. (2022) *Meta-Labeling Architecture*；Thumm et al. (2022) *Ensemble Meta-Labeling*（框架生态在扩展）。

---

## 2. 结构对照：我们的筛选层 vs Meta-Labeling

| 维度 | 我们现状（已验证） | Meta-labeling 正式形态 | 差异本质 |
|---|---|---|---|
| 一级 | wash_cvd 规则事件（方向=Long） | primary model / signal（定 side） | **一致**：一级只定方向 ✓ |
| 二级决策 | 4h 确认 r4>0（E18）、新币期<90d（s009）、低流动性层（s010）、周期门控（164）：**人工挑选的单特征硬阈值，AND 串联** | meta-model：$P(\text{成功}\mid\mathbf{x})$ + 阈值 $T$ | 规则=单特征×硬阈值，无法学交互；ML=多特征联合概率，自动学组合 |
| 标签 | r168 > 0（垂直障碍；账户 A/C/D 统计口径） | triple-barrier（+1/-1/0）或垂直障碍 | 我们 A/C/D 是纯时间退出 → r168>0 就是天然 meta-label；**账户 B（-10% 止损/trailing）才对应 triple-barrier** |
| 样本切分 | 独立时间窗口（W1/W2，157 等） | purged k-fold / CPCV + embargo | 独立窗口=粗粒度 embargo，防泄漏但**浪费数据**；purged CV 每 fold 用满非重叠数据，功效更高 |
| 输出 | 二值通过/拒绝 | 概率 → 阈值过滤 **+ 仓位缩放** | 我们丢掉了概率信息（r4 只用了符号，没用幅度） |
| 验证 | gauntlet：n≥30 / bootstrap CI / 独立窗口 / 尾切 / 成本后净期望 > 1.5×成本 / 预注册 | 同一套纪律 + 阈值扫描 trials 记账 | 方法论一致，ML 需额外管好"阈值挖掘"与"CV 泄漏" |
| 失败处置 | 二级失败 → 关过滤器，一级机制保留 | 同（meta 层失败 ≠ 一级死亡） | **一致**——这是我们已认同的 AFML 深度操作意义 |

**一句话**：我们已经在做 meta-labeling 的**规则版**（精神完全一致），缺的是 (a) 多特征联合建模、(b) 概率输出与阈值化、(c) purge-aware 的验证、（d) 概率→仓位。其中 (b)(d) 是 ML 的独有增益，(a) 是核心问题。

---

## 3. 升级方案：把二级层升级为"正式 meta-labeling"

### 3.1 样本构造

| 项 | 方案 |
|---|---|
| 事件池 | wash_cvd 全事件（115 口径、72h 冷却、2022-01→2026-06），**n=1348**（s001_confirm4.md 口径） |
| 标签定义 | $y = \mathbb{1}[\,r_{168} - 0.0054 > 0\,]$（168h 收益 − 双边成本 54bps，QUANT_METHODOLOGY §4.1 成本口径） |
| 主口径（推荐） | **r4 作为特征而非前置过滤器**：样本=全部 1348，模型自己学"4h 确认是否值得" → 与 meta-labeling 精神一致，不手工预设单特征 |
| 对照口径 | V_confirm 792 事件（已确认）上再叠一层：目标=确认之后的进一步精选，增量直接对标 +3.56% 基线 |
| 正类率 | 全事件 168h 胜率 47%，V_confirm 51% → 标签接近平衡，无需强过采样；**禁用随机过采样改分布**（AFML 纪律：训练集须代表总体） |
| 去重/重叠 | 沿用 72h 冷却；**注意**：冷却 72h < 标签窗 168h → 相邻事件标签窗重叠 96h，purged CV 必须按此处理（见 3.3） |
| 时点对齐 | 全部特征取事件时点（或确认时点）**之前**可得值，asof 口径；禁止任何前视（现有纪律延续） |

### 3.2 特征集（全部已有列，零新数据源）

| 组 | 特征 | 来源 |
|---|---|---|
| 信号强度 | washout 深度（price_z / ret_24h）、cvd_divergence z | s001 已有 |
| 确认信息 | r4（4h 收益，主口径下作特征） | E18 |
| 时间锚 | days_since_listing（连续）+ <90d 哑变量 | s009 |
| 容量锚 | 事件时点 24h 成交额（对数 + 分层哑变量） | s010 |
| 周期 | Mayer 倍数、cycle_z、BTC regime | 164/s013 |
| 大户行为 | np_z（净持仓背离；161 已证 r168 负向关联） | 161 候选 |
| 成交结构 | taker_buysell | 已有 |
| 上市形态 | pump 类哑变量（上市以来最大涨幅 >300%；160 显示非 pump 更强） | 160 |
| 市场环境 | VIX_SYNTH、breadth、贪婪指数 | 108/109 流 |
| 波动率 | 事件前 ATR/波动率（vol-target 相关） | 已有 klines |

- **样本量约束是硬约束**：n≈1348 × ~12–15 特征 → 强正则化（L1 logistic / 浅 GBM depth≤3 / RF 限特征数），禁止深网与无约束 GBM。
- 特征交互正是 ML 相对规则网格的**唯一理论增量来源**（规则层已把单特征用尽：s009/s010/161/160 都是单特征分层）。

### 3.3 训练/验证切分：purged CV vs 我们的独立窗口

| 方法 | 做法 | 优劣 |
|---|---|---|
| 我们现状：独立窗口 | 时间切成 W1/W2（或 157 式两段），各段独立评估 | ✓ 无泄漏、可解释；✗ 每段只用一半数据（功效低）、窗口边缘事件标签可能跨界 |
| **purged k-fold（推荐主法）** | k=5 时间有序 fold；对每个测试块，训练集中**标签窗与测试块重叠**的事件剔除（purge 168h）；测试块**之后**再 embargo ≥168h 缓冲 | ✓ 每 fold 用满非重叠数据；✓ 明确处理 72h<168h 的重叠泄漏；✗ 实现复杂度 + 需预注册 |
| walk-forward 滚动（对照） | 训练 2022-01→2025-06，验证 2025-07→2026-06，逐段滚动重训 | 与我们前向影子哲学最接近，可作最终确认手段 |

- 泄漏检查清单（沿用 gauntlet 对抗审查）：purge 窗=标签窗 168h；embargo ≥ 168h；特征无未来信息；跨 symbol 截面事件按**时间块**（而非随机行）切分（washout 常多币并发，截面相关）；`np_z` 等滚动特征确认用截至事件时点的滚动窗口。
- 阈值 $T$ 的选择**只在 OOF（out-of-fold）上**扫描，且计入 trials 记账（Bailey/LdP DSR 纪律：网格/阈值扫描必须记账）。

### 3.4 判定门槛（预注册为证，沿用 gauntlet 口径）

| 门槛 | 值 | 依据 |
|---|---|---|
| 模型质量 | purged OOF AUC > **0.55**（弱信号可再放宽到 0.55–0.60 区间内看增量） | 事件研究噪声大；AUC≤0.55 直接判死 |
| 增量（核心） | meta 过滤后 168h 超额 **≥ V_confirm 基线 +3.56% 再 +1.0pp**，且 bootstrap CI 下界 > 0 | 沿用 parallel_gpt_dataplan 160 的边际门槛口径 |
| 样本 | 过滤后 n ≥ 30（gauntlet 硬门槛） | QUANT_METHODOLOGY |
| 稳健性 | 尾切不转负；独立窗口 W1/W2 方向一致；0.5×/1×/2× 成本敏感性净期望仍正 | gauntlet |
| 证伪条件 | OOF AUC ≤ 0.55，或增量 CI 跨零，或 W1/W2 不一致 → **关闭并记录"规则层已捕获可用信息"** | 预注册证伪纪律 |
| 预算 | 消耗 1 个主问题配额（QUANT_PRE_REGISTRY 记账）；阈值扫描次数记入 trials | 方法论 §2/§3 |

---

## 4. 值得做吗：成本—收益判断（明确结论）

**结论：有条件值得——先做半天诊断实验，不作为主 edge 工程立项。**

**支持规则基线优先的理由（反方）**：
- E18 已很强：V_confirm 168h 超额 +3.56%（n=792）、中位数 +0.51% 转正、胜率 51%；4h 确认已把 556/1348（41%）坏尾部砍掉，V_reject 均值 -0.26%。
- s009（+5.82%）、s010（+2.60%）、s009×s010×非pump（中位数 +4.31%）说明**单特征规则层的边际还没挖完**——账户 D 参数仍在优化中，规则路线的确定增量更容易量化。
- 样本约束：n≈1348、胜率 ~50%、168h 超额只有 +1.48% → 信噪比低，ML 的 OOF AUC 天花板估计 0.55–0.60；**AUC 0.55–0.60 的模型在均值超额上的增益预计只有 +0.5~+1.5pp，且大概率体现在 Sharpe/MDD（概率仓位）而非均值**。
- ML 特有风险：purged CV 只是降低泄漏，不消除过拟合；"看起来正规的 CV"可能掩盖高方差（Bailey/LdP 警告）。验证改造（预注册 ML 卡、trials 记账、阈值挖掘控制）有 2–5 天成本。

**支持最小实验的理由（正方）**：
- **结构上已经同构**：我们在做规则版 meta-labeling，升级是"同一问题的另一种求解器"，不是新方向——符合"保护主 edge、不另挖新矿"的既定策略。
- 现有散点证据指向**4h 确认之外确实还有条件信息**（np_z 负向 -4.36%、低流动×非pump 更强、周期门控）——ML 可以把这些一次性联合，而不是逐个网格消耗检验预算。
- 半天成本、纯研究、不动账户、预注册证伪——即使失败也产出"规则层已到天花板"的结构化证据，与 160 证伪同价值。

**定量预期（诚实版）**：若 OOF AUC ≈ 0.58、阈值 T≈0.60 时过滤掉 30% 低质量确认事件（均值≈V_reject 水平），组合均值约从 +4.78% 提升至 +5.5~6.0%（均值口径），即**增量 +0.7~1.2pp 区间**；这是乐观假设，CI 大概率宽。**因此判定门槛定 +1.0pp 且 CI 下界 > 0 是严格且现实的。**

---

## 5. 第一步行动：半天最小实验（可执行路径）

**目标**：回答两个问题——(1) 多特征联合的 OOF AUC 是否显著 > 0.55？(2) meta 过滤后的 168h 超额是否 ≥ 基线 +3.56% + 1.0pp？

1. **拼宽表**（~2h）：复用 148/157 事件表（1348 事件）左连接全部特征列（§3.2 清单）；标签 = r168 − 0.0054 > 0。所有列必须已是现有报告/脚本产出的 asof 值。
2. **asof 审计**（0.5h）：每列人工过一遍"事件时点是否已知"；`np_z`/`cycle_z` 确认滚动口径（cyclez_forward_stats.md 已警告：统计口径 vs 交易口径需滚动重算）。
3. **复算基线**（0.5h）：V_confirm +3.56% 超额、CI、中位数——作为对照锚（若复算对不上，先停，不进入建模）。
4. **训练 + purged CV**（1h）：L1 logistic 与浅 GBM（depth≤3，强正则）各一；k=5 时间有序，purge=embargo=168h；输出 OOF AUC + 校准曲线。
5. **T 扫描**（0.5h）：OOF 上扫 T∈{0.5,0.55,0.60,0.65,0.70,0.75}，选净期望最大者；bootstrap CI；记录 trials 数。
6. **对照判定**：按 §3.4 门槛出 GO/NO_GO；GO → 预注册正式 ML alpha card（账户 E：meta 层，接在账户 C/D 之后）；NO_GO → 记录"规则层已捕获可用信息"，关闭。
7. **产出**：mini 报告（本目录 `meta_labeling_firstpass.md`）+ QUANT_PRE_REGISTRY 记账 + EDGE_LEDGER 草稿。

**技术栈**：python + sklearn（本机量化环境已有），全本地数据，零新数据源，零账户改动。

---

## 6. 参考来源（全部为真实来源）

1. López de Prado, M. (2018). *Advances in Financial Machine Learning*. Wiley. — Ch.3 标签与 meta-labeling（§3.6，p.50 引文）；Ch.7 purged/embargoed k-fold CV、CPCV。
2. Joubert, J.F. (2022). *Meta-Labeling: Theory and Framework*. The Journal of Financial Data Science 4(3): 31–44 — pm-research.com（阈值 T 优化、Sharpe/MDD 受控实验、regime+一级特征的特征工程指引）。
3. Hudson & Thames (2019). *Meta Labeling: A Toy Example*. https://hudsonthames.org/meta-labeling-a-toy-example/ — 直接转载原书 p.50 段落；F1/假阳性机理；MNIST 玩具验证。
4. Hudson & Thames (2019). *Does Meta Labeling Add to Signal Efficacy?* — 趋势跟踪实盘式应用（meta-labeling 提升 Sharpe 的实证案例）。
5. Meyer et al. (2022) *Meta-Labeling Architecture*；Thumm et al. (2022) *Ensemble Meta-Labeling* — 框架生态扩展（经 pm-research 引用页核验存在）。
6. Bailey, D. & López de Prado, M. (2014). *The Deflated Sharpe Ratio*. JPM — trials 记账纪律（本地权威文档 §2.2 引用）。
7. 本地：`reports/external_intel/authoritative_quant_research_pipeline_deep_dive_2026-08.md` §2.3（AFML 一节，含"meta-labeling 特别贴合你们"的判定）。

*数字来源（本仓库，均可复现）：s001_confirm4.md（1348/792/556、+3.56%、胜率）；EDGE_LEDGER（E18/E19/E20）；newlisting_confirm.md（s009 +5.82%）；s009_s010_stack.md（+7.74% / 中位数 +4.31%）；161（np_z -4.36%）；QUANT_METHODOLOGY.md（成本 27bps 单边、净期望 > 1.5×成本、gauntlet 门槛）。*
