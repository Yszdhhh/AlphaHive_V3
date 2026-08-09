这是方法论与管线设计问题。先快速查看工作区是否有 AlphaHive 相关代码/文档，以便建议贴合你们的现有约束。读取你们已有的研究结论，使方案与 AlphaHive 现状对齐。# AlphaHive V3：约束下的自动因子提取路径

**核心判断先说清楚：**  
你们已证伪的三条路（单特征极值、meta-labeling、规则硬叠）说明问题不在“算子不够多”，而在**问题设定错了**。  
`wash_cvd` 是**事件驱动 edge**（低频、条件触发），不是股票式截面连续因子。在此约束下，自动挖掘的正确目标不是“再找一条独立 edge 替代 wash_cvd”，而是：

1. **在 wash_cvd 条件分布内**找边际有效的修饰因子（modifier / intensity / regime gate）  
2. **正交残差空间**里找不与 wash_cvd 共线的第二结构（若存在）  
3. **用前向影子 + 多重检验预算**管生命周期，而不是回测 IC 冲榜  

下面按 A/B/C 给可执行方案。

---

## A. 自动因子提取的正确路径

### A0. 问题重构（比工具更重要）

| 错误设定 | 正确设定 |
|---|---|
| 全市场连续截面因子 → IC/IR 排序 | **事件集** \(\mathcal{E}=\{wash\_cvd 触发点\}\)，在事件上定义特征 \(x_i\) 与前瞻收益 \(r_{i,\tau}\) |
| 单特征极值（funding/high 等）独立 edge | 单特征极值 **16/16 NO_GO 已终局**；只允许作为 **条件交互** 或 **正交残差** |
| 预测“这次会不会深亏”（meta-label） | 深亏尾部难预测（AUC 0.592）；改为预测 **强度分位 / 持有 horizon 匹配 / 仓位缩放**，或只做 **过滤型 gate**（二值降频） |
| 4 条件 AND 冲 +8.45% | n=57、样本 6.6% 是过拟合高危区；默认用 **≥2 条件档 +1.60%** 作稳健基线，新因子必须报告 **边际 Δ vs 该基线** |

**可执行定义：**

```text
单元样本 = 1 个 wash_cvd 事件（symbol, t0）
标签 y    = 前向收益 r_24h / r_72h / r_168h（已有口径）
特征 X    = 仅 t≤t0 的信息（含冷却 72h 内不可复用）
目标      = E[y | wash_cvd, X] 的可交易增量，而非全域 E[y|X]
```

自动搜索只允许在 **事件条件空间** 或 **与 wash_cvd 正交的残差空间** 进行。

---

### A1. 算子搜索 / 遗传规划：适用性与陷阱

#### 适用性（有限开放，不是主引擎）

| 场景 | 是否建议 | 说明 |
|---|---|---|
| 裸 gplearn 在全 bar 上搜 IC | **禁止** | 与 16/16 单特征极值失败同构：组合爆炸 + 多重检验必过拟合 |
| 在事件表上搜 **简单交互式**（`f1 * f2`, `rank(f1)-rank(f2)`, `zscore` 差） | **有条件允许** | 算子白名单极短；fitness 用 **purged OOS 边际贡献**，不用 IS IC |
| 搜第二独立 edge（替代 wash_cvd） | **暂缓** | 历史 4 episode + 前向影子未完成前，第二 edge 优先级低于 **护核 + 衰减监控** |
| 搜 **持有期/止损参数**（持有 h、冷却、分位阈值） | **可以** | 这是超参搜索，不是“新因子叙事”；预算单独记账 |

#### 若做 GP / 算子搜索：硬约束清单

```text
1. 输入：仅事件级面板（n≈1348 量级），不是 1m bar 原始流
2. 算子白名单（最多 6–8 个）：
   + - * / | rank | zscore | abs | sign | delay(k∈{0})  # 事件上 delay 几乎无意义
   禁止：rolling_mean/std（事件表上无时序语义）、复杂嵌套、if-then 树深>2
3. 最大表达式复杂度：节点数 ≤ 5；禁止常量网格（避免阈值拟合）
4. Fitness（唯一合法）：
   fitness = OOS_mean(y | top_q(f)) - OOS_mean(y | wash_cvd_base)
             - λ * turnover_proxy
             且要求 bootstrap CI 下界 > 0（或 ΔSharpe 的 deflated p < α_budget）
5. 禁止用全样本选表达式后再报告同一窗口的 p 值
6. 每代/每轮候选数计入多重检验预算（见 C）
```

#### 陷阱（结合你们已有发现）

1. **单特征极值再包装**  
   GP 会重新发明 `funding/high`、`qv/high`——你们已 16/16 NO_GO。  
   **对策：** 输出表达式必须能映射到经济叙事；与已证伪特征族的相关 > 0.7 直接 **HARD REJECT**。

2. **Fitness 与可交易目标错配**（meta-label 教训）  
   AUC/准确率优化“是否深亏”失败，是因为标签难、且决策不对称。  
   **对策：** fitness = **事件收益的边际期望 + 成本**，不是分类 AUC。

3. **小样本上的组合爆炸**  
   n=1348 事件、4 episode，GP 代数一大必拟合噪声。  
   **对策：** 总尝试次数预算（如研究季 ≤ 50 次正式假设）；GP 只作 **假设生成器**，入选后走与人工因子相同的验证流水线。

4. **gplearn 默认 Pearson 相关**  
   对重尾 crypto 收益极不稳定。  
   **对策：** 用 Spearman / 分位多空收益 / bootstrap mean；自研 fitness 回调，别用默认。

**结论：** GP 可以作 **受限假设生成**，不能作 **主发现引擎**。主路径应是 **假设驱动交互 + 正交边际检验**。

---

### A2. 因子正交化与边际贡献检验（主路径）

目标：新因子 \(f\) 是否在 **控制 wash_cvd 及已采用 gate** 后仍有增量。

#### 步骤（事件级，可直接编码）

**Step 1 — 标准化（事件截面或滚动历史分位）**

```text
对每个日历日 t 的候选事件横截面：
  f̃ = rank_or_zscore(f | 当日/当周事件)
（低频日均 1–2 事件时，改用：相对自身历史分位 + 全池历史分位双轨）
```

**Step 2 — Symmetric orthogonalization（多候选同时）**

对候选因子矩阵 \(F\)（列已标准化）：

\[
F^{\perp} = F (F^\top F)^{-1/2}
\]

- 对称正交保持相对结构，适合“一批候选同时去相关后再比 IC”。  
- **陷阱：** 事件稀疏时 \(F^\top F\) 病态 → 加 ridge，或改用 **逐个对核心因子回归残差**：

\[
f^{\perp} = f - \hat\beta^\top X_{\text{core}},\quad
X_{\text{core}}=\{\text{wash\_cvd 强度}, \text{已采用 gate}, \text{BTC 24h}, \text{breadth}\}
\]

**Step 3 — 边际贡献检验（必须同时过 3 关）**

| 检验 | 方法 | GO 门槛（建议） |
|---|---|---|
| M1 条件分层 | 仅在 wash_cvd 内，按 \(f^{\perp}\) 三分位，看 top−bottom 或 top vs rest | bootstrap CI 下界 > 0；且 **≥3/4 episode 同号** |
| M2 回归边际 | \(r = \alpha + \beta f^{\perp} + \gamma'X_{\text{core}} + \varepsilon\)，HC/ cluster by date | \(|t|\ge 2.5\)（小样本可降到 2.0 但必须 DSR/多重校正） |
| M3 嵌套策略 | 策略 A=wash_cvd 基线；B=A + gate(\(f\))；看 Δ 收益与 n 变化 | Δ 收益 > 成本缓冲；B 的 n 不低于 A 的 40%（防 +8.45% 式样本蒸发） |

**与规则天花板的关系：**  
四条件 AND +8.45%（n=57）应视为 **探索上界/过拟合警示**，不是生产目标。  
新因子默认接入方式：

- **加分缩放**（连续强度 → 仓位 0.5–1.5x），或  
- **软 gate**（降频但保留 ≥50–70% 事件），  
- 禁止默认走 **硬 AND 叠到 n 崩塌**。

---

### A3. 时间序列交叉验证：泄漏控制

事件驱动 + crypto 横截面相关 → 标准 K-fold **必泄漏**。

#### 推荐：Combinatorial Purged K-Fold + Embargo（López de Prado）

```text
时间轴 ──train──| purge |──test──| embargo |──train──...
```

| 参数 | 建议值（对齐你们 24h/168h 标签） |
|---|---|
| 标签最长前瞻 | \(h=168h\)（7d） |
| purge | ≥ \(h\)（事件 t0 前/后各 7d 内样本不得同时跨 train/test） |
| embargo | ≥ 2–3d（或 0.5×平均事件间隔）；防波动聚集传染 |
| 折法 | 按 **时间切块**，不要按事件随机打乱 |
| 横截面 | 同一 t0 的多币事件要么全在 train 要么全在 test（**date-level split**） |

**额外 crypto 特有控制：**

1. **Episode 阻塞：** 4 个历史 regime 至少留 1 个完全 OOS；报告 **leave-one-episode-out**。  
2. **点-in-time：** funding/OI/liq 用发布可得时间；禁止未来修正后的 OI。  
3. **冷却 72h：** 同一 symbol 重叠事件在 CV 中视为依赖簇（cluster bootstrap）。  
4. **禁止：** 先全样本算分位阈值再 CV；阈值必须 **fold 内拟合，fold 外冻结**。

**伪代码骨架：**

```python
# 事件表 events: t0, symbol, y_24h, y_168h, features...
# 1) 按 t0 排序，切时间折
# 2) 对 test 折，purge 掉 |t - t_test| < 168h 的 train 事件
# 3) embargo: test 结束后 3d 内事件不进下一 train
# 4) 仅在 train 上估阈值/正交系数；应用到 test
# 5) 汇总 OOS 事件收益 → bootstrap CI + deflated Sharpe
```

---

### A4. 因子衰减监控（对齐你们 EDGE_LEDGER 思路）

事件低频（日均 1–2）→ **禁止纯日历窗**，用 **事件计数窗**。

| 层级 | 触发 | 动作 |
|---|---|---|
| L0 正常 | 滚动 N=60 事件，超额 CI 下界 > 0 | 维持；每 +10 事件重算 |
| L1 预警 | CI 含 0 但上界 > 0；或 mean 较历史基线下滑 >40% | 降权 50%；记入 ledger `watch` |
| L2 隔离 | 连续 2 个窗（各 n≥30）超额 CI **上界 < 0**；或 Live DD > 1.5× IS DD | 实盘仓位 0，转 shadow |
| L3 退役 | shadow 再积 n≥60 仍失效；或 DSR 失效 | `retired`，冻结假设编号 |

**必做指标（事件级）：**

- 滚动事件 mean/median 收益 + bootstrap CI  
- win rate 与 payoff 分解（防“胜率崩、盈亏比伪装”）  
- **净成本后** TE（换手 × 费率/滑点）  
- OOS 衰减率：\(1 - R_{\text{shadow}}/R_{\text{IS}}\)，>50% 预警  
- 与 BTC/breadth 的条件表现（区分 edge 死 vs regime 差）

影子期（你们 108/109 闭环）是 **唯一合法晋升通道**；回测 GO ≠ live GO。

---

## B. 实操管线推荐（库选型 + 逐步过拟合控制）

### B1. 库选型（务实组合，不追框架）

| 层级 | 推荐 | 不推荐/慎用 | 原因 |
|---|---|---|---|
| 事件面板 / 清洗 | **pandas + polars**，自研 event builder | 重型回测框架先上 | 你们已是事件驱动，先固定 `events.parquet` 契约 |
| 统计推断 | **statsmodels**（OLS/WLS + HC1/cluster）、**scipy** bootstrap | 只看 t 不看 cluster | crypto 同日横截面相关 |
| 因子研究报表 | **alphalens-reloaded** 仅作 **截面诊断参考** | 当主判决引擎 | alphalens 假设股票式日频持仓；事件信号会 **错配**（换手、加权、区间） |
| 正交/降维 | **numpy/scipy** 自研 sym-orth；sklearn 仅用 `StandardScaler` | 盲目 PCA 当 alpha | PCA 方向无经济含义，易数据窥探 |
| GP（可选） | **gplearn** 仅假设生成 + 白名单算子 | 默认 fitness 扫全市场 | 见 A1 |
| 多重检验 | 自研：Bonferroni / BH-FDR + **Deflated Sharpe**；参考 mlfinlab 概念可自实现 | 依赖黑盒 AutoML | 需把“已测假设数”显式记账 |
| 回测/成本 | 自研 event backtester（进场 t0+slip，出场 h，冷却，费率） | vectorbt 乱扫参数 | 参数网格会吃光检验预算 |
| 监控 | 自研 EDGE_LEDGER（candidate→validated→shadow→live→decaying→retired） | 无状态 notebook | 生命周期是工程问题 |

**总原则：80% 自研事件管线 + 20% statsmodels/scipy；alphalens 辅助、不决策。**

### B2. 端到端管线（可直接排期）

```text
[0] 冻结核心
    wash_cvd 定义/冷却/标签口径 只读；影子继续跑
    基线策略：≥2 条件档（稳健）+ 可选四条件仅作研究上界

[1] 数据契约 Event Store
    events(t0, symbol, y_*, core_features, regime_tags, cost_est)
    点-in-time 字段 + 数据版本 hash

[2] 假设注册 Hypothesis Registry
    每个候选：id, 叙事, 特征公式, 依赖数据, 预算消耗=1
    已证伪族黑名单：funding极值、单特征 high、稳定币/ETF/GDELT 等

[3] 特征生成（仅事件上）
    人工交互（优先）：OI×价格四象限 × wash_cvd、LCS、CVD陷阱布尔…
    可选 GP：白名单，≤20 个表达式/季，只进 registry 不直接上线

[4] 正交化
    对 core 与已采用 gate 回归残差 / sym-orth

[5] Purged CV + leave-one-episode-out
    fold 内拟合阈值；OOS 汇总

[6] 边际三关（M1/M2/M3）+ 成本后净收益

[7] 多重检验门
    累计尝试次数 N_trials → 校正 α 或 DSR
    未过门：记 NO_GO，永不“换标签重试”同一假设

[8] Shadow 晋升
    前向 n≥30 再看 CI；n≥60 才讨论 live 权重

[9] Decay 监测
    每 +10 事件；L1/L2/L3 状态机
```

### B3. 每步过拟合控制（检查表）

| 步骤 | 过拟合控制 |
|---|---|
| 特征定义 | 先叙事后代码；禁止看 y 再改公式 |
| 阈值 | 只允许分位数（如 top 30%），禁止网格搜最优 cutoff 后只报最优 |
| 组合规则 | 报告完整路径：n、Δ vs 基线、episode 一致性；禁止只报 +8.45% 那一格 |
| CV | purge+embargo+date split；一次 OOS，禁止反复调到 OOS 变好（OOS 变调参集则作废） |
| 尝试次数 | 研究季预算写死（例：正式注册假设 ≤20–50）；GP 中间代不计入可放宽，但 **最终提交式** 计入 |
| 成本 | 默认 taker + 10–20bp 滑点（山寨）；净收益 ≤0 → NO_GO |
| 晋升 | 无 shadow 不得 live；shadow 与 IS 衰减 >50% → 降级 |
| 文档 | EDGE_LEDGER 强制：GO/NO_GO/数据版本/N_trials |

---

## C. 失败模式优先级（结合你们已有发现）

按 **“现在最可能杀掉真实研究进度 / 制造假 edge”** 排序：

### P0 — 立刻制度化（会直接污染 wash_cvd 护核）

| 模式 | 为何对你们是 P0 | 规避动作 |
|---|---|---|
| **多重检验 / 选择偏差** | 已测约 20 条线 + 16 极值 + meta + 规则组合；表面显著遍地 | Hypothesis Registry + 预算；报告 DSR / 校正 p；四条件 +8.45% 降权为探索 |
| **小样本硬 AND** | n=57、6.6% 样本冲高收益 | 生产默认 ≥2 条件；新 gate 限制最低样本保留率 |
| **标签/决策错配** | meta-label AUC 0.592，深亏不可预测 | 不做深亏分类器；做边际过滤/仓位缩放 |
| **数据透视泄漏** | 全样本分位、未来 OI、先看 y 再设阈值 | fold 内阈值；point-in-time；研究日志审计 |

### P1 — 管线设计期必须堵住

| 模式 | 为何相关 | 规避动作 |
|---|---|---|
| **CV 泄漏（重叠标签）** | y 含 24–168h，事件扎堆 | purged k-fold + embargo + 同日簇 |
| **把连续截面工具硬套事件** | alphalens IC 叙事误导 | 事件 bootstrap 为主，alphalens 仅辅 |
| **换手/成本忽略** | 山寨合约滑点与撤单真实存在 | 成本后 net；TE 进 fitness |
| **Regime 误判为 edge 死亡/存活** | 2022 深熊 1/4 episode 例外已出现 | leave-one-episode-out；分 regime 报告，不合并粉饰 |
| **已证伪特征族复活** | GP/正交后仍变体 funding 极值等 | 黑名单 + 相关>0.7 HARD REJECT |

### P2 — 中期监控（影子→live）

| 模式 | 说明 | 规避动作 |
|---|---|---|
| **幸存者偏差** | 下架币、改名、合约切换 | 事件表用当时可交易 universe；含失败上市 |
| **前视上市/市值** | 用未来市值过滤 | 用 t0 时的 list 状态 |
| **拥挤与衰减** | edge 公开后失效 | 事件窗 decay；CI 上界<0 连续 2 窗 |
| **相关假象（BTC beta）** | 事件收益其实是 beta | 回归控制 BTC/市场 breadth |
| **重复使用同一稀缺样本** | 4 episode 被所有假设反复榨取 | 第二 edge 严格 OOS episode；优先影子新数据 |

### P3 — 已知低价值方向（直接冻结，不配算力）

- 单特征极值算子全家桶（已 16/16）  
- funding 择时/选币、稳定币/ETF/交易所净流入、GDELT 情绪等已证伪线  
- 深亏 meta-label ML  
- 无叙事的深层 GP 表达式  

---

## 可执行 90 天方案（收敛版）

| 阶段 | 时间 | 做什么 | 成功标准 |
|---|---|---|---|
| **护核** | 0–30d | 冻结 wash_cvd；影子闭环；EDGE_LEDGER + 事件计数 decay；Hypothesis Registry | 基线与监控上线；不再开新无注册假设 |
| **边际** | 30–60d | 只做 **wash_cvd 内** 正交边际：优先 OI×价格四象限、LCS、CVD 陷阱等有叙事构造；M1–M3 + purged CV | ≤5 个正式假设；每个有 GO/NO_GO 档案 |
| **可选自动** | 45–75d | 若人工交互枯竭：白名单 GP **仅事件表**，每季 ≤20 式，同一流水线 | 无 IS-only 入选 |
| **晋升** | 60–90d | 过门因子进 shadow；与四条件探索档对比稳健性 | 无 shadow 实证不调 live 主仓 |

**明确不做：** 全域因子动物园、meta-label 2.0、规则五条件再叠、无预算的算子网格。

---

## 风险清单（一页版）

| ID | 风险 | 等级 | 缓解 |
|---|---|---|---|
| R1 | 多重检验耗尽后仍“再试一个” | P0 | 季度预算 + Registry 强制 |
| R2 | 四条件 +8.45% 被当成生产目标 | P0 | 生产用 ≥2 条件；+8.45% 仅研究上界 |
| R3 | GP/极值搜索复活伪因子 | P0 | 黑名单 + 正交共线拒绝 |
| R4 | 标签前瞻泄漏 / 阈值全样本拟合 | P0 | purge+embargo；fold 内阈值 |
| R5 | meta-label 类目标再引入 | P0 | 禁止分类深亏；只优化净期望 |
| R6 | 事件稀疏导致 decay 误杀 | P1 | 事件窗 n≥30/60；连续 2 窗 |
| R7 | 成本后 alpha 为 0 | P1 | 默认滑点压力测试 |
| R8 | alphalens/IC 误导事件策略 | P1 | 事件 bootstrap 为判决 |
| R9 | 2022 类深熊 regime | P1 | episode OOS；分状态仓位 |
| R10 | 幸存者/下架币 | P2 | 当时 universe 重建 |
| R11 | 第二 edge 分心，影子样本不够 | P2 | 90 天内第二 edge 低优先级 |
| R12 | 同日多币相关低估方差 | P1 | date-cluster bootstrap |

---

## 一句话总纲

> **停止“全市场自动挖新 edge”；把自动提取降级为：在已验证的 wash_cvd 事件条件分布上，做强约束的交互/正交边际搜索，用 purged+embargo CV 与多重检验预算判决，用事件计数窗影子监控衰减。**  
> 算子搜索/GP 是 **假设生成器** 不是 **发现引擎**；规则硬叠与 meta-label 已触顶/失败，下一单位算力应给 **正交边际 + 生命周期工程**，而不是更大的特征动物园。

若你下一步要落地成 AlphaHive 仓库里的模块（`event_store` / `purged_cv` / `sym_orth` / `edge_ledger` 接口草图），可以指定现有目录结构，我可以按上述管线直接拆成可提交的工程骨架与验收测试。
