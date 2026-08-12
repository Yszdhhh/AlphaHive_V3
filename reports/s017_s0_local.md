# s017 S0 本地沙盒 — Token Unlock 残差空

- date: 2026-08-12 07:37 UTC
- script: `scripts/s017_s0_local.py`
- events in: `G:\Quant test\derived_data\token_unlocks\sample_events.parquet`
- prices: coinglass raw_1h klines
- **描述性 / exploratory；不宣布 GO / historical_pass**

## 规格（锁定）

- 入场: T0−14d 后第一根 1h open；平: T0 close asof
- 方向: 空残差 = −(r_sym − β·r_btc)，β=入场前 30d 日收益 OLS，clip[0,1.5]
- 过滤: pct_circ≥0.5% · ADV7d≥$2M · 冷却 7d
- 成本: 悲观 round-trip 54 bps
- seed: 20260812

## 结论

| 项 | 值 |
|---|---|
| 合格事件 n | 313 |
| 覆盖币 | 13 |
| mean short residual | 2.03% |
| median | 4.95% |
| bootstrap 95% CI mean | [-0.19, 4.20]% |
| mean net (27bps×2) | 1.49% |
| 胜率 short>0 | 63.6% |
| vs random 14d excess | 0.67% CI[-1.59,2.82] |
| **S0 判定** | **S0_WEAK_OR_MIXED** |

### 分层

- main_pct05_adv: n=313 sym=13 mean_short=2.03% med=4.95% mean_net=1.49% pos=63.6% CI_mean[-0.19,4.20]%
- team_investor: n=295 sym=10 mean_short=1.96% med=4.98% mean_net=1.42% pos=63.7% CI_mean[-0.45,4.01]%
- pre_2024: n=102 sym=9 mean_short=-0.83% med=4.24% mean_net=-1.37% pos=65.7% CI_mean[-5.62,3.65]%
- post_2024: n=211 sym=12 mean_short=3.41% med=5.19% mean_net=2.87% pos=62.6% CI_mean[1.07,5.67]%

### 解锁占比三分位（单调性）

```
pct_bin  count     mean   median
    low    119 0.005497 0.052246
    mid    103 0.034446 0.042678
   high     91 0.023715 0.043706
```

### 备注

- 两段同向=NO (pre=-0.83% post=3.41%)
- 成本后 mean_net=1.49%
- vs random excess=0.67% CI[-1.59,2.82]% n_base=1492

### 补充（同日本地，仍描述性）

| 分析 | 结果 |
|---|---|
| 次 horizon T0→T0+14 空残差 | n=312 mean **+0.95%** med +4.20% pos 60%（弱于前窗） |
| 去掉 \|残差\| top10% | n=281 mean **+3.83%** med +4.96%（非单靠极端赢家） |
| 敏感性 pct≥0.25% | n=395 mean +2.26% CI[+0.50,+3.94]（CI 不含 0） |
| 主规格 pct≥0.5% | n=313 mean +2.03% CI[-0.16,+4.16]（含 0） |
| 敏感性 pct≥1.0% | n=195 mean +2.87% CI[+0.68,+5.07]（CI 不含 0） |
| pct≥1% 两段 | pre n=51 **+2.33%** / post n=144 **+3.06%** **同向** |

解读：主规格 0.5% 全样本方向正、中位数稳，但 **CI 跨 0 + 2024 前弱** → 不能升 S1。  
预声明敏感性 **1.0%** 更干净（CI>0 且两段同向）——若 Owner 要推进，应 **显式改卡锁定 1.0% 再 S1 一次 holdout**，禁止事后改口。

## 事件明细

`G:\Quant test\derived_data\token_unlocks\s0_events.csv`

## 下一跳（仍本地）

1. （可选）Owner 锁定 pct 主规格 0.5% 维持观察 / 或改卡 1.0% 后做 **一次** holdout（后 20%）
2. team/investor 映射清洗
3. 单币贡献 / 去掉 top 事件币稳健性

## 真·VPS 才需要

- Tokenomist 跨源校验日历（Mobula 覆盖不均；机构字段 cliff/linear）
- 非本机已有的全市场日历扫表
