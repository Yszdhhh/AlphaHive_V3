# s018 CS_MN S0+ 本地（含价格腿 + 调仓频率敏感性）

- date: 2026-08-12 07:31 UTC
- script: `scripts/s018_s0_local.py`
- funding: `C:\Users\10639\Desktop\加密\binance_free_db\history\funding` (≤70 alts, uncapped only)
- prices: coinglass 1h
- **CS_MN / ≠s014 / ≠s005**；exploratory，不宣布 GO
- **主规格判定仅 every_n=1**；更低频为描述性敏感性（未改卡）

## 规格

- 结算 8h：空 top5 / 多 bottom5；美元中性
- funding / 价格腿拆分；成本 16.2 / 27 bps × 换手

## 主规格结论 (every_n=1)

| 项 | 值 |
|---|---|
| n | 3567 |
| mean fund / price / gross (bps) | 1.880 / -8.108 / -6.228 |
| mean net 16.2 / 27 (bps) | -21.765 / -32.123 |
| mean turnover | 0.959 |
| 两段同向 net27 | True |
| **S0 判定** | **S0_FAIL_HINT** |

### 分段（主规格）

- every_1x8h: n=3567 fund=1.88bps price=-8.11bps gross=-6.23bps net16.2=-21.76bps net27=-32.12bps to=0.96 win%=49.6
- pre_2025: n=1819 fund=0.99bps price=1.76bps gross=2.75bps net16.2=-11.75bps net27=-21.42bps to=0.90 win%=49.4
- post_2025: n=1748 fund=2.81bps price=-18.38bps gross=-15.57bps net16.2=-32.18bps net27=-43.26bps to=1.03 win%=49.7

### 调仓频率敏感性（描述）

- every_n=1 (~8h): n=3567 fund=1.88bps price=-8.11bps gross=-6.23bps net16.2=-21.76 net27=-32.12 to=0.959
- every_n=3 (~24h): n=3567 fund=1.70bps price=-4.13bps gross=-2.43bps net16.2=-8.33 net27=-12.26 to=0.364
- every_n=9 (~72h): n=3567 fund=1.32bps price=-2.04bps gross=-0.72bps net16.2=-3.00 net27=-4.51 to=0.140

### 红线检查（主规格）

- mean net_pess (27bps) <= 0  [主规格 every_n=1]
- price leg magnitude > funding and negative

## 明细

`G:\Quant test\AlphaHive_V3\reports\s018_s0_local_periods.csv`

## 解读

- funding 截面价差本身常为正，但 **价格腿 + 高频换手** 可吞噬 carry。
- 若敏感性显示低频仍净负 → 机制在可交易成本下弱；若低频转正 → 需 **改卡重预注册** 才能进 S1。

## 真·VPS

- 全所微观结构冲击、借币、多所 funding 对齐（本机已覆盖 70 币 8h 面板级）
