# s017 S1 Holdout — Token Unlock 残差空 — **S1_PASS_CANDIDATE**

- date: 2026-08-12 07:50 UTC
- script: `scripts/s017_s1_holdout.py`
- events in: `G:\Quant test\derived_data\token_unlocks\sample_events.parquet`
- prices: coinglass raw_1h klines (`C:\Users\10639\Desktop\🔒 加密资产\coinglass_db\raw_1h\klines`)
- seed: 20260812
- **数据性质: development / exploratory**
- **禁止**: 不宣布 historical_pass / live / 前向通过；不改卡规格；eval 未参与选形态

## 规格（锁定，与 S0 / alpha_card 一致）

| 项 | 值 |
|---|---|
| 入场 | T0−14d 后第一根完整 1h open |
| 平仓 | T0 close asof |
| 方向 | 空残差 = −(r_sym − β·r_btc)；β=入场前 30d 日收益 OLS，clip[0, 1.5] |
| 过滤 | pct_circ≥阈值 · ADV7d≥$2M · 冷却 7d |
| 成本 | 悲观 round-trip 54 bps（27bps×2） |
| 预声明 pct | {0.25%, 0.5%, 1.0%} |
| Holdout | 按 unlock_ms 排序；前 80% select / 后 20% eval |

## 时间切分（防泄漏）

| 项 | 值 |
|---|---|
| 切分锚点池 | 最松 pct≥0.25% 合格事件（n=395） |
| cut_ms | 1755302400000 |
| cut_utc | 2025-08-16 00:00:00+00:00 |
| select (unlock_ms < cut) | n=316（锚点池） |
| eval (unlock_ms ≥ cut) | n=79（锚点池） |
| 说明 | 三形态共用同一 cut_ms；**仅 select 用于选 pct**；eval 只对胜出形态评一次 |

## Select 段：三形态对比（唯一选形态依据）

| pct | n | sym | mean_short | median | bootstrap 95% CI mean | mean_net | pos% | 段内半切同向 (A/B mean) |
|---|---:|---:|---:|---:|---:|---:|---:|---|
| 0.25% | 316 | 14 | 1.98% | 4.99% | [-0.57%, 4.08%] | 1.44% | 63.61% | YES (0.24%/3.71%) |
| 0.50% | 246 | 13 | 1.57% | 4.97% | [-1.17%, 4.10%] | 1.03% | 63.01% | NO (-0.83%/3.96%) |
| 1.00% | 138 | 12 | 2.84% | 4.64% | [-0.15%, 5.54%] | 2.30% | 65.22% | YES (3.14%/2.53%) |

### 选形态规则（冻结）

1. select 段 `mean_short` 的 bootstrap CI **下界最大**
2. 并列 → median 更大
3. 再并列 → n 更大
4. 再并列 → pct 更严（1.0% > 0.5% > 0.25%）

排序（优→劣）: 1.00%, 0.25%, 0.50%

### **选中 pct = 1.00%**

- select n=138 · mean=2.84% · med=4.64% · CI=[-0.15%, 5.54%]

## Eval 段：胜出形态唯一一次评价

| 项 | 值 |
|---|---|
| 形态 | pct_circ ≥ **1.00%** |
| n | **57** |
| 覆盖币 | 3 |
| mean short residual | **2.95%** |
| median | **4.15%** |
| bootstrap 95% CI mean | **[0.62%, 5.13%]** |
| mean net (27bps×2) | **2.41%** |
| median net | 3.61% |
| 胜率 short>0 | 68.42% |
| vs random 14d (简化) | base_mean=0.38% CI[-1.67%, 2.47%] n_base=285；excess=2.57% |

> 注：上表为**胜出 pct 在 eval 上的唯一正式结果**。未对未胜出形态做决策性 eval 对比（避免多重比较后改口）。

## GO 候选门控（报告用；**不**等于 historical_pass）

| 门控 | 结果 |
|---|---|
| n_ge_20 | PASS |
| ci_lo_gt_0 | PASS |
| median_ge_0 | PASS |
| mean_net_gt_0 | PASS |

| **S1 Verdict（脚本）** | **S1_PASS_CANDIDATE** |
|---|---|
| **Lead 验收（2026-08-12）** | **升级冻结：CONCENTRATED** |

### Lead 审计（非执行 agent）

| 检查 | 结果 |
|---|---|
| eval 币分布 | **SEI 45 / ARB 11 / ONDO 1**（SEI≈79%） |
| leave-SEI | n=12 mean +2.24% med +3.51%（方向同、样本不足） |
| SEI 事件间隔 | 中位 7d（=冷却下限，偏线性/密集解锁而非独立 cliff） |
| 卡 n≥80 | eval 57 **未达**升级门槛 |
| 统计门控 | CI/median/net 脚本 PASS 成立 |

**Lead 结论**：脚本门控可记 `S1_PASS_CANDIDATE`，但 **不得** 申请 historical_pass。  
主因：eval 高度 SEI 集中 + 总 n 未达卡门槛 + 个人适配要求「组合分散解锁事件」。  
下一步优先：扩日历降低单币占比，或把 SEI 线性解锁剔除后重跑（须预注册新过滤，算新形态）。

判定说明:
- `S1_UNDERPOWERED`: eval n<20
- `S1_PASS_CANDIDATE`: n≥20 且 CI下界>0 且 median≥0 且 mean_net>0（**仅候选**，不升级、不写 historical_pass）
- `S1_FAIL`: 有足够样本但未过门控
- `Lead CONCENTRATED`: 门控过但单币/单结构主导 → 冻结升级

## 禁升级声明

- 本结果为 **development / exploratory** 本地 holdout。
- **不得**写入 live 配置、**不得**宣布 historical_pass / 前向通过。
- 未改 s014 / s018 / s001；未看 eval 后改阈值。
- 若为 `S1_PASS_CANDIDATE`，下一步仍由 Owner 决定是否申请正式 historical_pass 流程（含 n≥80 卡门槛、增量 vs s001 等）。

## 池规模（全时段，供参考）

| pct | 全时段 n | select n | eval n |
|---|---:|---:|---:|
| 0.25% | 395 | 316 | 79 |
| 0.50% | 313 | 246 | 67 |
| 1.00% | 195 | 138 | 57 |

## 产出文件

- 报告: `G:\Quant test\AlphaHive_V3\reports\s017_s1_holdout.md`
- 全 pct 事件: `G:\Quant test\derived_data\token_unlocks\s1_events_all_pct.csv`
- 胜出 select: `G:\Quant test\derived_data\token_unlocks\s1_select_events.csv`
- 胜出 eval: `G:\Quant test\derived_data\token_unlocks\s1_eval_events.csv`

## 未决项

1. team/investor alloc 字符串仍脏；主路径与 S0 一致未做硬过滤
2. 日历源仍为 Mobula sample；与链上/Tokenomist 交叉未做
3. 卡门槛 n≥80 为升级门槛；本 S1 用 n≥20 标 UNDERPOWERED
4. funding 持有期成本未计入（仅 27bps×2 开平）
