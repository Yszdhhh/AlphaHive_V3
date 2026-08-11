# 双账户虚拟交易报告

- 生成：2026-08-11 03:41 UTC
- 事件源：forward_replay_returns.csv；入场=事件后下一 bar open；成本=27bps 单边
- A=固定持有 24h 时间退出；B=止损 -20%/trailing -50%/上限 168h
- MDD 断路器：-15% 减半 / -25% 停新仓；仓位 $1000/事件；初始 $10000

## 账户 A

- 已结算：9 笔；净盈亏 $-387.48；期末净值 $9612.52
- 胜率 22.2%；最大回撤 -4.0%
- 退出分布：{'TIME': 9}

## 账户 D

- 已结算：262 笔；净盈亏 $+2491.97；期末净值 $12491.97
- 胜率 51.1%；最大回撤 -23.6%
- 退出分布：{'TIME': 262}

## 当前持仓

- B：9 笔持仓中（ONDOUSDT, ADAUSDT, ONDOUSDT, ONDOUSDT, ONDOUSDT, SKYAIUSDT ...）
- C：9 笔持仓中（ONDOUSDT, ADAUSDT, ONDOUSDT, ONDOUSDT, ONDOUSDT, SKYAIUSDT ...）
- D：25 笔持仓中（AAOIUSDT, APPUSDT, CAPUSDT, CRDOUSDT, MUUUSDT, MVLLUSDT ...）

