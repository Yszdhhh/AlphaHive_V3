# S1 挑战者：cvd_divergence 冻结（214，一次时间 holdout）

- family：cvd_divergence | 生成：2026-08-09 12:10 UTC
- 切分：前 80% train / 后 20% holdout（按事件时间，非打乱）
- 标签：24h 成本后净收益；holdout 只评估选中形态一次

## train 形态选择

| 形态 | IC | uplift | n |
|---|---|---:|---:|
| capped_hinge(1,2) | +nan | +nan% | 1078 |
| log_ratio | +0.128 | +2.25% | 899 |

## holdout 一次评估（选中形态）

| 形态 | IC | uplift | 6h 聚类 CI | n | 判定 |
|---|---|---:|---:|---:|---|
| log_ratio | -0.248 | -1.59% | [-1.99, +5.78] | 91 | **NO_GO/UNDERPOWERED** |

## 冻结提案

- family：cvd_divergence | 形态：log_ratio
- forward_start：不适用
- 激活动作（Owner 签批后）：config/factor_funnel.yaml score_vol.status → FROZEN + 填 forward_start
- 激活后：108/109 自动开始标注与分桶前向积累（纯标注，不改触发/verdict/纸面）

## 纪律

- S1 通过只授予冻结规格资格，不授予历史结论；前向 30/60-100 事件块才是唯一确认。
- 若 NO_GO/UNDERPOWERED：FAM-001 记台账后关闭，禁止换皮重测（除非新数据/新机制）。
