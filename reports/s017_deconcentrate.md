# s017 降集中诊断 — Unlock 多币结构 vs SEI 线性 quirk

- date: 2026-08-12 07:56 UTC
- script: `scripts/s017_deconcentrate.py`
- inputs: `s1_select_events.csv` / `s1_eval_events.csv` / `sample_events.parquet`
- S1 胜出形态（冻结，本诊断不改）: pct_circ ≥ **1.00%**
- **数据性质: development / exploratory / descriptive**
- **禁止**: 不改 S1 pct；不进 S2；不宣称 GO / historical_pass

## Verdict: **MIXED_NEED_MORE_CALENDAR**

> leave-SEI full 仍正 (n=97, mean=3.47%, CI_lo=0.51%)；剔密集 schedule 仍正 (n=95, CI_lo=0.33%)；稀疏 cliff 仍正 (n=73, CI_lo=1.59%)；SEI 事件簇压缩 98→2（线性密集伪独立）；eval SEI 权重 79% 集中未消解；leave-top3 n=38 mean=2.81% 但 CI_lo=-3.56% 不稳 → 方向偏多币，但需扩日历降集中后再判结构稳性

### 判定键（三选一，描述性）

| Verdict | 含义 |
|---|---|
| `STRUCTURAL_MULTI` | leave-top 后仍稳 |
| `SINGLE_NAME_DOMINATED` | 主要 SEI |
| `MIXED_NEED_MORE_CALENDAR` | 方向在但 n 不够 |

---

## 0. 基线（S1 已算 short_resid，原样汇总）

| slice | n | n_sym | mean_short | median | bootstrap 95% CI | mean_net | pos% | top symbol weight |
|---|---:|---:|---:|---:|---|---:|---:|---|
| select_s1_pct1 | 138 | 12 | 2.84% | 4.64% | [-0.41%, 5.62%] | 2.30% | 65.22% | SEIUSDT 38.41% |
| eval_s1_pct1 | 57 | 3 | 2.95% | 4.15% | [0.70%, 5.06%] | 2.41% | 68.42% | SEIUSDT 78.95% |
| full_s1_pct1 | 195 | 12 | 2.87% | 4.27% | [0.72%, 4.79%] | 2.33% | 66.15% | SEIUSDT 50.26% |

- SEI weight: **full 50.3%** · **eval 78.9%** · schedule_rows(SEI)=2558
- dense schedule symbols (raw rows>100): ALGOUSDT, BLURUSDT, CRVUSDT, GRTUSDT, MANTAUSDT, NEARUSDT, SEIUSDT, SUIUSDT, TIAUSDT, WLDUSDT （共 10）

## 1. 各币 n / mean short / 权重

### 1.1 Full（select+eval，n=195 池中 S1 合格 138+57）

| symbol | n | mean_short | median | weight | mean_net | pos% | schedule_rows | dense? |
|---|---:|---:|---:|---:|---:|---:|---:|---|
| SEIUSDT | 98 | 2.27% | 4.19% | 50.26% | 1.73% | 64.29% | 2558 | Y |
| UNIUSDT | 31 | 2.57% | 3.46% | 15.90% | 2.03% | 70.97% | 48 |  |
| ARBUSDT | 28 | 5.37% | 5.31% | 14.36% | 4.83% | 71.43% | 38 |  |
| AVAXUSDT | 11 | -3.68% | 8.90% | 5.64% | -4.22% | 54.55% | 41 |  |
| HBARUSDT | 7 | 7.64% | 2.88% | 3.59% | 7.10% | 71.43% | 18 |  |
| INJUSDT | 7 | -0.14% | -6.63% | 3.59% | -0.68% | 42.86% | 27 |  |
| 1INCHUSDT | 6 | 3.21% | 3.45% | 3.08% | 2.67% | 66.67% | 9 |  |
| ONDOUSDT | 2 | 17.72% | 17.72% | 1.03% | 17.18% | 100.00% | 17 |  |
| LDOUSDT | 2 | -1.34% | -1.34% | 1.03% | -1.88% | 50.00% | 29 |  |
| TIAUSDT | 1 | 29.13% | 29.13% | 0.51% | 28.59% | 100.00% | 1097 | Y |
| OPUSDT | 1 | 13.24% | 13.24% | 0.51% | 12.70% | 100.00% | 50 |  |
| SUIUSDT | 1 | 0.54% | 0.54% | 0.51% | -0.00% | 100.00% | 2558 | Y |

### 1.2 Select

| symbol | n | mean_short | median | weight | pos% |
|---|---:|---:|---:|---:|---:|
| SEIUSDT | 53 | 1.54% | 6.21% | 38.41% | 60.38% |
| UNIUSDT | 31 | 2.57% | 3.46% | 22.46% | 70.97% |
| ARBUSDT | 17 | 8.23% | 9.66% | 12.32% | 76.47% |
| AVAXUSDT | 11 | -3.68% | 8.90% | 7.97% | 54.55% |
| HBARUSDT | 7 | 7.64% | 2.88% | 5.07% | 71.43% |
| INJUSDT | 7 | -0.14% | -6.63% | 5.07% | 42.86% |
| 1INCHUSDT | 6 | 3.21% | 3.45% | 4.35% | 66.67% |
| LDOUSDT | 2 | -1.34% | -1.34% | 1.45% | 50.00% |
| TIAUSDT | 1 | 29.13% | 29.13% | 0.72% | 100.00% |
| ONDOUSDT | 1 | 18.96% | 18.96% | 0.72% | 100.00% |
| OPUSDT | 1 | 13.24% | 13.24% | 0.72% | 100.00% |
| SUIUSDT | 1 | 0.54% | 0.54% | 0.72% | 100.00% |

### 1.3 Eval（Lead 已标 CONCENTRATED）

| symbol | n | mean_short | median | weight | pos% |
|---|---:|---:|---:|---:|---:|
| SEIUSDT | 45 | 3.14% | 4.15% | 78.95% | 68.89% |
| ARBUSDT | 11 | 0.95% | 1.58% | 19.30% | 63.64% |
| ONDOUSDT | 1 | 16.49% | 16.49% | 1.75% | 100.00% |

---

## 2. Leave-one-symbol-out

至少 SEI / ARB / top3（按 full 事件数）。

### 2.1 Full

| slice | n | n_sym | mean_short | median | bootstrap 95% CI | mean_net | pos% | top remaining |
|---|---:|---:|---:|---:|---|---:|---:|---|
| full_s1_pct1 | 195 | 12 | 2.87% | 4.27% | [0.72%, 4.79%] | 2.33% | 66.15% | SEIUSDT 50.26% |
| leave-SEIUSDT | 97 | 11 | 3.47% | 4.37% | [0.51%, 6.37%] | 2.93% | 68.04% | UNIUSDT 31.96% |
| leave-ARBUSDT | 167 | 11 | 2.45% | 4.18% | [-0.04%, 4.77%] | 1.91% | 65.27% | SEIUSDT 58.68% |
| leave-UNIUSDT | 164 | 11 | 2.93% | 4.40% | [0.18%, 5.10%] | 2.39% | 65.24% | SEIUSDT 59.76% |
| leave-AVAXUSDT | 184 | 11 | 3.26% | 4.24% | [1.10%, 5.27%] | 2.72% | 66.85% | SEIUSDT 53.26% |
| leave-HBARUSDT | 188 | 11 | 2.69% | 4.32% | [0.34%, 4.77%] | 2.15% | 65.96% | SEIUSDT 52.13% |
| leave-top1(SEI) | 97 | 11 | 3.47% | 4.37% | [0.51%, 6.37%] | 2.93% | 68.04% | UNIUSDT 31.96% |
| leave-top2(SEI+UNI) | 66 | 10 | 3.90% | 4.95% | [0.35%, 7.44%] | 3.36% | 66.67% | ARBUSDT 42.42% |
| leave-top3(SEI+UNI+ARB) | 38 | 9 | 2.81% | 3.63% | [-3.56%, 8.06%] | 2.27% | 63.16% | AVAXUSDT 28.95% |

### 2.2 Eval

| slice | n | n_sym | mean_short | median | bootstrap 95% CI | mean_net | pos% | top remaining |
|---|---:|---:|---:|---:|---|---:|---:|---|
| eval_s1_pct1 | 57 | 3 | 2.95% | 4.15% | [0.70%, 5.06%] | 2.41% | 68.42% | SEIUSDT 78.95% |
| leave-SEIUSDT | 12 | 2 | 2.24% | 3.51% | [-3.24%, 7.41%] | 1.70% | 66.67% | ARBUSDT 91.67% |
| leave-ARBUSDT | 46 | 2 | 3.43% | 4.17% | [0.92%, 5.79%] | 2.89% | 69.57% | SEIUSDT 97.83% |
| leave-top1(SEI) | 12 | 2 | 2.24% | 3.51% | [-3.24%, 7.41%] | 1.70% | 66.67% | ARBUSDT 91.67% |
| leave-top2(SEI+ARB) | 1 | 1 | 16.49% | 16.49% | [16.49%, 16.49%] | 15.95% | 100.00% | ONDOUSDT 100.00% |
| leave-top3(SEI+ARB+ONDO) | 0 | 0 | n/a | n/a | [n/a, n/a] | n/a | n/a |  n/a |

### 2.3 Select

| slice | n | n_sym | mean_short | median | bootstrap 95% CI | mean_net | pos% | top remaining |
|---|---:|---:|---:|---:|---|---:|---:|---|
| select_s1_pct1 | 138 | 12 | 2.84% | 4.64% | [-0.41%, 5.62%] | 2.30% | 65.22% | SEIUSDT 38.41% |
| leave-SEIUSDT | 85 | 11 | 3.65% | 4.37% | [0.20%, 6.50%] | 3.11% | 68.24% | UNIUSDT 36.47% |
| leave-ARBUSDT | 121 | 11 | 2.08% | 4.21% | [-1.28%, 5.43%] | 1.54% | 63.64% | SEIUSDT 43.80% |
| leave-UNIUSDT | 107 | 11 | 2.91% | 4.98% | [-0.77%, 6.45%] | 2.37% | 63.55% | SEIUSDT 49.53% |
| leave-AVAXUSDT | 127 | 11 | 3.40% | 4.37% | [0.51%, 6.11%] | 2.86% | 66.14% | SEIUSDT 41.73% |
| leave-HBARUSDT | 131 | 11 | 2.58% | 4.91% | [-0.36%, 5.39%] | 2.04% | 64.89% | SEIUSDT 40.46% |
| leave-top1(SEI) | 85 | 11 | 3.65% | 4.37% | [0.20%, 6.50%] | 3.11% | 68.24% | UNIUSDT 36.47% |
| leave-top2(SEI+UNI) | 54 | 10 | 4.26% | 4.95% | [-0.78%, 8.38%] | 3.72% | 66.67% | ARBUSDT 31.48% |
| leave-top3(SEI+UNI+ARB) | 37 | 9 | 2.44% | 2.88% | [-3.59%, 7.98%] | 1.90% | 62.16% | AVAXUSDT 29.73% |

---

## 3. 事件簇（同 symbol 间隔 ≤7d 并簇，降伪独立）

规则：按 symbol 排序 unlock_ms；相邻间隔 ≤7d 并入同一簇；簇收益 = 成员 `short_resid` 等权均值。冷却已在 S1 建池时应用，故簇主要压缩「刚好卡在冷却边界上的密集线性解锁」。

| slice | n_events | n_clusters | n_sym | mean_short | median | bootstrap 95% CI | mean_net | pos% | top |
|---|---:|---:|---:|---:|---:|---|---:|---:|---|
| cluster_select | 138 | 86 | 12 | 3.62% | 4.32% | [0.44%, 6.53%] | 3.08% | 68.60% | UNIUSDT 36.05% |
| cluster_eval | 57 | 14 | 3 | 2.02% | 2.42% | [-3.98%, 6.72%] | 1.48% | 64.29% | ARBUSDT 78.57% |
| cluster_full | 195 | 99 | 12 | 3.41% | 4.27% | [0.32%, 6.22%] | 2.87% | 67.68% | UNIUSDT 31.31% |

- SEI 事件→簇压缩: **98 → 2** clusters
- 多事件簇数: 1 / 99 (mean n_events in multi=97.00)

### 3.1 簇级各币（full）

| symbol | n_clusters | mean_short | median | weight | mean n_events/cluster |
|---|---:|---:|---:|---:|---:|
| 1INCHUSDT | 6 | 3.21% | 3.45% | 6.06% | 1.00 |
| ARBUSDT | 28 | 5.37% | 5.31% | 28.28% | 1.00 |
| AVAXUSDT | 11 | -3.68% | 8.90% | 11.11% | 1.00 |
| HBARUSDT | 7 | 7.64% | 2.88% | 7.07% | 1.00 |
| INJUSDT | 7 | -0.14% | -6.63% | 7.07% | 1.00 |
| LDOUSDT | 2 | -1.34% | -1.34% | 2.02% | 1.00 |
| ONDOUSDT | 2 | 17.72% | 17.72% | 2.02% | 1.00 |
| OPUSDT | 1 | 13.24% | 13.24% | 1.01% | 1.00 |
| SEIUSDT | 2 | 0.21% | 0.21% | 2.02% | 49.00 |
| SUIUSDT | 1 | 0.54% | 0.54% | 1.01% | 1.00 |
| TIAUSDT | 1 | 29.13% | 29.13% | 1.01% | 1.00 |
| UNIUSDT | 31 | 2.57% | 3.46% | 31.31% | 1.00 |

---

## 4. 可选过滤（仅诊断，三列并列，不选胜）

| filter | 定义 |
|---|---|
| **a** | 剔除 raw schedule 行数 >100 的币（疑似日更线性） |
| **b** | 仅 `team_investor==True` |
| **c** | 已在 pct≥1% 池上，每币每年最多 4 个事件（强制稀疏 cliff） |

### 4.1 Full 并列

| filter | n | n_sym | mean_short | median | bootstrap 95% CI | mean_net | pos% | top weight |
|---|---:|---:|---:|---:|---|---:|---:|---|
| full_s1_pct1 | 195 | 12 | 2.87% | 4.27% | [0.72%, 4.79%] | 2.33% | 66.15% | SEIUSDT 50.26% |
| filt_a_drop_dense_sched | 95 | 9 | 3.23% | 4.37% | [0.33%, 6.10%] | 2.69% | 67.37% | UNIUSDT 32.63% |
| filt_b_team_investor | 177 | 9 | 2.83% | 4.42% | [0.23%, 5.08%] | 2.29% | 66.67% | SEIUSDT 55.37% |
| filt_c_sparse_cliff | 73 | 12 | 5.06% | 5.19% | [1.59%, 8.37%] | 4.52% | 68.49% | ARBUSDT 16.44% |

### 4.2 Eval 并列

| filter | n | n_sym | mean_short | median | bootstrap 95% CI | mean_net | pos% | top weight |
|---|---:|---:|---:|---:|---|---:|---:|---|
| eval_s1_pct1 | 57 | 3 | 2.95% | 4.15% | [0.70%, 5.06%] | 2.41% | 68.42% | SEIUSDT 78.95% |
| filt_a_eval | 12 | 2 | 2.24% | 3.51% | [-3.24%, 7.41%] | 1.70% | 66.67% | ARBUSDT 91.67% |
| filt_b_eval | 57 | 3 | 2.95% | 4.15% | [0.70%, 5.06%] | 2.41% | 68.42% | SEIUSDT 78.95% |
| filt_c_eval | 17 | 3 | 1.17% | 1.88% | [-3.49%, 5.61%] | 0.63% | 64.71% | ARBUSDT 47.06% |

### 4.3 Select 并列

| filter | n | n_sym | mean_short | median | bootstrap 95% CI | mean_net | pos% | top weight |
|---|---:|---:|---:|---:|---|---:|---:|---|
| select_s1_pct1 | 138 | 12 | 2.84% | 4.64% | [-0.41%, 5.62%] | 2.30% | 65.22% | SEIUSDT 38.41% |
| filt_a_select | 83 | 9 | 3.38% | 4.37% | [-0.58%, 6.48%] | 2.84% | 67.47% | UNIUSDT 37.35% |
| filt_b_select | 120 | 9 | 2.77% | 5.11% | [-0.67%, 6.01%] | 2.23% | 65.83% | SEIUSDT 44.17% |
| filt_c_select | 64 | 12 | 5.32% | 5.70% | [1.28%, 8.92%] | 4.78% | 68.75% | UNIUSDT 18.75% |

- filter a 从 full 剔除币: SEIUSDT, SUIUSDT, TIAUSDT → 剩余 n=95
- filter b full: team_investor 177/195 (90.8%)
- filter c full: 195 → 73 (压缩 122 个同年超额事件)

---

## 5. 综合解读（描述性）

| 检查 | 结果 |
|---|---|
| eval SEI 占比 | 78.9% (≥50% 单名主导风险) |
| full SEI 占比 | 50.3% (≥40% 偏高) |
| leave-SEI full | n=97 mean=3.47% CI=[0.51%, 6.37%] med=4.37% |
| leave-top3 full | n=38 mean=2.81% CI=[-3.56%, 8.06%] |
| 簇化 full | events 195→clusters 99; mean=3.41% CI_lo=0.32% |
| 剔密集 schedule (a) | n=95 mean=3.23% CI_lo=0.33% |
| team_investor (b) | n=177 mean=2.83% CI_lo=0.23% |
| 稀疏 cliff (c) | n=73 mean=5.06% CI_lo=1.59% |
| **Verdict** | **MIXED_NEED_MORE_CALENDAR** |

### 关键数字（一页表）

| 指标 | 值 |
|---|---|
| S1 pct（冻结） | 1.00% |
| full n / n_sym | 195 / 12 |
| full mean_short | 2.87% |
| eval n / SEI_n / SEI_w | 57 / 45 / 78.95% |
| leave-SEI mean / n / CI_lo | 3.47% / 97 / 0.51% |
| leave-top3 mean / n / CI_lo | 2.81% / 38 / -3.56% |
| cluster mean / n / CI_lo | 3.41% / 99 / 0.32% |
| filt_a mean / n / CI_lo | 3.23% / 95 / 0.33% |
| filt_b mean / n / CI_lo | 2.83% / 177 / 0.23% |
| filt_c mean / n / CI_lo | 5.06% / 73 / 1.59% |
| **Verdict** | **MIXED_NEED_MORE_CALENDAR** |

---

## 6. 禁令与未决

- 本诊断 **未** 改 S1 选中 pct，**未** 用过滤结果回写形态。
- **不得** 据此宣布 GO / historical_pass / 进 S2。
- 若未来要「剔线性密集解锁」作新形态，须 **预注册** 后重跑 holdout（新卡/新形态），不可事后贴。
- 日历源仍为 Mobula sample；扩币/交叉 Tokenomist 未做。
- 未碰 s018 / s001 代码。

## 产出

- 报告: `G:\Quant test\AlphaHive_V3\reports\s017_deconcentrate.md`
- 脚本: `scripts/s017_deconcentrate.py`
