# AlphaHive V3 前向影子收益复核

- 生成: 2026-08-09 08:09 UTC
- 候选源: contract_monitor_candidates.csv（n=2），trigger=['cvd_bear_divergence']）
- 基线: 候选时点 1 个，每时点随机 300 个 universe symbol 横截面
- 样本不足时 verdict=PENDING（CI 宽，待积累）


## 4h — PENDING

| 组 | n | 均值% | 中位数% | 胜率% |
|---|---|---|---|---|
| candidate | 2 | 2.66 | 2.66 | 50 |
| baseline | 246 | 0.09 | -0.29 | 29 |

超额（事件−基线）均值 = +2.57%  bootstrap 95% CI [-0.55, +5.70]

> ⚠️ 样本不足（事件 n=2，基线 n=246）→ PENDING，继续积累前向影子。

## 24h — NOT_ENOUGH_DATA（候选尚无 24h 前向数据）


## 72h — NOT_ENOUGH_DATA（候选尚无 72h 前向数据）


## 168h — NOT_ENOUGH_DATA（候选尚无 168h 前向数据）


## Verdict 汇总

4h:PENDING | 24h:PENDING | 72h:PENDING | 168h:PENDING


## 连续分数前向验证（描述性，不参与 verdict）

- 有效分数样本不足（n=0，唯一值 0）→ **INSUFFICIENT_VARIATION / NOT_ENOUGH_DATA**


## Decay 监测（事件计数窗口）

- 判决单位: 每 30 事件一块（非重叠，按时间序）；n 总=0
- CUSUM(向下, k=0.5, h=4.5)：z_i = 事件超额/σ，S⁻ 超阈值触发预警

| 块 | 时间范围 (UTC) | n | 24h均值% | 超额% | CI | 判定 |
|---|---|---|---|---|---|---|
| 1 | 08-08 21:00~08-08 21:00 | 0 | - | - | - ~ - | 无基线 |

**累积**: n=0 < 30 → 样本不足，观察中（不判衰退）
**CUSUM S⁻** = 0.00（阈值 4.5）