# s017 扩日历后诊断（冻结 pct=1%）

- date: 2026-08-12 08:17 UTC
- script: `scripts/s017_expand_diagnose.py`
- calendar: `G:\Quant test\derived_data\token_unlocks\sample_events.parquet`
- **冻结形态**: pct_circ ≥ **1%**（S1 胜出，**未重选**）
- 过滤: ADV≥$2M · 冷却 7d · 空残差同 S0
- **描述性 / exploratory；不宣布 GO；不改 S1 选形态**

## 结论

| 项 | 值 |
|---|---|
| 合格事件 n | 211 |
| 覆盖币 | 14 |
| mean / median short | 2.44% / 3.69% |
| bootstrap CI | [0.23%, 4.49%] |
| top 币权重 | SEIUSDT **46.4%** |
| SEI 占比 | 46.4% |
| **Verdict** | **MIXED_NEED_MORE_CALENDAR** |

### 分层

- full_pct1: n=211 sym=14 mean=2.44% med=3.69% CI[0.23,4.49] top=SEIUSDT(46.4%) pos=64.9%
- leave_SEIUSDT: n=113 sym=13 mean=2.59% med=3.46% CI[-0.21,5.19] top=UNIUSDT(27.4%) pos=65.5%
- leave_UNIUSDT: n=180 sym=13 mean=2.42% med=3.88% CI[0.23,4.90] top=SEIUSDT(54.4%) pos=63.9%
- leave_ARBUSDT: n=183 sym=13 mean=2.00% med=3.41% CI[-0.21,4.20] top=SEIUSDT(53.6%) pos=63.9%
- leave_AVAXUSDT: n=200 sym=13 mean=2.78% med=3.65% CI[0.68,4.58] top=SEIUSDT(49.0%) pos=65.5%
- leave_ANKRUSDT: n=203 sym=13 mean=2.62% med=4.18% CI[0.50,4.78] top=SEIUSDT(48.3%) pos=65.5%
- leave_top3: n=54 sym=11 mean=1.16% med=2.32% CI[-2.99,5.31] top=AVAXUSDT(20.4%) pos=59.3%
- clustered_7d: n=115 sym=14 mean=2.55% med=3.05% CI[-0.11,4.90] top=UNIUSDT(27.0%) pos=65.2%
- drop_dense_sched: n=111 sym=11 mean=2.37% med=3.46% CI[-0.56,4.92] top=UNIUSDT(27.9%) pos=64.9%
- sparse_cliff_4py: n=81 sym=14 mean=-0.61% med=4.91% CI[-5.78,3.48] top=ARBUSDT(14.8%) pos=58.0%

### 分币（top 15）

```
           count      mean    median    weight
symbol                                        
SEIUSDT       98  0.022745  0.041930  0.464455
UNIUSDT       31  0.025692  0.034588  0.146919
ARBUSDT       28  0.053667  0.053108  0.132701
AVAXUSDT      11 -0.036819  0.089040  0.052133
API3USDT       8 -0.033587 -0.008742  0.037915
ANKRUSDT       8 -0.021791 -0.011271  0.037915
INJUSDT        7 -0.001450 -0.066288  0.033175
HBARUSDT       7  0.076412  0.028816  0.033175
1INCHUSDT      6  0.032126  0.034487  0.028436
LDOUSDT        2 -0.013356 -0.013356  0.009479
ONDOUSDT       2  0.177230  0.177230  0.009479
OPUSDT         1  0.132357  0.132357  0.004739
SUIUSDT        1  0.005360  0.005360  0.004739
TIAUSDT        1  0.291321  0.291321  0.004739
```

### 簇化摘要

- 事件→簇: 211 → 115
- SEI 事件/簇: 98 / 2

## 解读

- `STRUCTURAL_MULTI`: 多币、leave-top3 CI>0 → 可考虑预注册稀疏 cliff 再 holdout  
- `IMPROVED_BUT_STILL_MIXED`: 有改善但仍集中或 leave 边界  
- `MIXED_NEED_MORE_CALENDAR`: 方向在但分散不够  
- `SINGLE_NAME_DOMINATED`: 单币主导  

## 产出

- `G:\Quant test\derived_data\token_unlocks\expanded_pct1_events.csv`
- 本报告

## 禁区

- 未重跑 S1 选 pct  
- 未宣称 historical_pass  
