# API 用量报告（203）

- 生成：2026-08-09 03:07 UTC
- Dune（实时）: 4.42 / 2500 credits （2026-07-24 ~ 2026-08-24）
- Coinalyze（本地计数）: 累计 0 calls（0 次同步）

| API | key 位置 | 免费 limit | 用量 | 用途 |
|---|---|---|---|---|
| fred | local_secrets.yaml -> fred.api_key | 120 req/min（无月度硬上限，远未触及） | 不可见 | 宏观序列（SP500/VIX/利率/黄金等 118） |
| coinalyze | local_secrets.yaml -> coinalyze.api_key | 40 calls/min（每 symbol 计 1 call） | 本地: 累计 0 calls（0 次同步） | 清算历史前向（196，E21） |
| dune | local_secrets.yaml -> dune.api_key | community 2500 credits/月（billing 2026-07-24~08-24） | 实时: 4.42 / 2500 credits （2026-07-24 ~ 2026-08-24） | 链上历史回填（201-202，P7）+ 横截面链上特征（204+） |
| binance_public | none（公开 REST/WS） | IP weight 2400/min（klines limit=1000 → weight 5） | 不可见 | klines/OI/funding/taker 前向 + 历史回填（hermes 每小时 + 研究脚本） |
| yfinance | none | 软限流（429 需退避） | 不可见 | USDCNH（197）/ GOLD（118）/ ES=F（137）/ ETF 代理 |
| p2p_binance_okx | none（公开端点） | 未文档化；低频日快照 | 不可见 | 场外溢价（197，P7） |
| pyth | none | 限流 30-60s 退避（144 实测） | 不可见 | 链上价格（144 六资产 washout） |
| uniswap_rpc | none（公共 RPC ethereum.publicnode.com） | 软限流；每小时 1 次快照（173） | 不可见 | CEX-DEX 价差（173）/ 稳定币 DEX 价 |
| akshare | none | 免费；接口停更风险（125 CME 已评估） | 不可见 | CME 机构持仓（125） |
| openbb | 复用 fred | 随底层（FRED） | 不可见 | FRED 双源对照（174） |
