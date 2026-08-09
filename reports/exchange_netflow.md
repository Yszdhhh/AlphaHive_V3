# 交易所 BTC 净流入免费数据源实测（CoinMetrics Community API）

- 生成: 2026-08-07 05:33:56 UTC
- 方法: CoinMetrics Community API v4（免费无 key）—— `GET /v4/timeseries/asset-metrics?assets=btc&metrics=FlowInExNtv,FlowOutExNtv,FlowInExUSD,FlowOutExUSD&frequency=1d`；净流入 = FlowInExNtv − FlowOutExNtv（原生 BTC）/ FlowInExUSD − FlowOutExUSD（USD）
- 数据源: CoinMetrics Community API（community-api.coinmetrics.io/v4，免费无 key），拉取时间 2026-08-07 05:31:50 UTC（缓存）；fetch_log=exchange_netflow_fetch_log.json
- 净流入日序列落盘: btc_exchange_netflow_daily.csv（含 fetched_at 时间戳，一次性拉取不做定时化）
- 收益口径: coinglass klines（113 清洗）日频，btc=BTCUSDT，alt=universe 等权篮子（138 同款）
- 无前视：wash_cvd 事件分层用事件日-1 的净流入滚动分位（-1 日收盘后完全可知）
> 目的：实测免费交易所净流入数据路径的可用性/质量/覆盖，检验与 btc/alt 收益及 wash_cvd 信号的关联，评估 Dune 免费账号注册是否值得（T3-2 免费替代）。

## 表1 数据覆盖实证（CoinMetrics btc 1d，社区档）

| 指标 | 行数 | 起始 | 最新 |
|---|---|---|---|
| FlowInExNtv | 5584 | 2011-04-24 | 2026-08-06 |
| FlowOutExNtv | 5584 | 2011-04-24 | 2026-08-06 |
| FlowInExUSD | 5584 | 2011-04-24 | 2026-08-06 |
| FlowOutExUSD | 5584 | 2011-04-24 | 2026-08-06 |
| SplyExNtv | 5584 | 2011-04-24 | 2026-08-06 |
| SplyExUSD | 5584 | 2011-04-24 | 2026-08-06 |

- 索引覆盖 2011-04-24 → 2026-08-06，5584 行；范围内缺失日期 0 天（无）
- 全部行的 `-status` 字段为 **flash**（社区档不提供 final/修订标记；值可能随上游修订变化）——见 fetch_log 与下方局限。

## 表2 净流入 vs btc/alt 收益相关

窗口 2022-01-16 → 2026-07-07，1627 天（coinglass 侧为数据末尾约束）；netflow_ntv mean=-341 std=7315 P10=-6135 P90=5075 BTC

| 对比 | n | Pearson | Spearman |
|---|---|---|---|
| 净流入水平 vs 当日 btc 收益 | 1627 | -0.090 | -0.093 |
| 净流入水平 vs 当日 alt 收益 | 1627 | -0.057 | -0.059 |
| 净流入水平 → 次日 btc 收益 | 1626 | +0.045 | +0.040 |
| 净流入水平 → 次日 alt 收益 | 1626 | +0.050 | +0.051 |
| 净流入日变化 vs 当日 btc 收益 | 1626 | -0.100 | -0.086 |
| 净流入日变化 vs 当日 alt 收益 | 1626 | -0.080 | -0.064 |
| 净流入日变化 → 次日 btc 收益 | 1625 | +0.051 | +0.014 |
| 净流入日变化 → 次日 alt 收益 | 1625 | +0.069 | +0.019 |
| 净流入USD vs 当日 btc 收益 | 1627 | -0.109 | -0.099 |
| 净流入USD vs 当日 alt 收益 | 1627 | -0.068 | -0.071 |
| 净流入USD → 次日 btc 收益 | 1626 | +0.034 | +0.045 |
| 净流入USD → 次日 alt 收益 | 1626 | +0.049 | +0.055 |
| 净流入USD日变化 vs 当日 btc 收益 | 1626 | -0.111 | -0.098 |
| 净流入USD日变化 → 次日 btc 收益 | 1625 | +0.020 | +0.008 |

## 表3 wash_cvd 事件 × 事件日-1 净流入分层（24h 超额，基线=同窗口随机，bootstrap 95% CI）

| 层 | n | 净流入均值(BTC) | 24h均 | 24h超额 | CI | 判定 |
|---|---|---|---|---|---|---|
| 净流入-低 | 454 | -5475 | +0.86% | +0.66% | [-0.10, +1.39] | **NO_GO** |
| 净流入-中 | 454 | -228 | +0.68% | +0.49% | [-0.43, +1.42] | **NO_GO** |
| 净流入-高 | 440 | +4171 | +2.43% | +2.24% | [+1.33, +3.21] | **GO_LONG** |
| 净流入-全 | 1348 | -559 | +1.31% | +1.12% | [+0.59, +1.64] | **GO_LONG** |

- wash_cvd 事件总数 1348（对照：115 pooled n=1348，24h超额 +1.31%）；滚动分位覆盖 1348 个；分层用事件日-1 净流入（无前视）。

## Dune / CryptoQuant 免费档（备选路径，未实测）

- Dune: config/local_secrets.yaml 未发现 dune key → 需注册 Dune 免费账号并申请 API key。免费档含 API（约 2,500 credits/月，按查询算力计费，超量 $5/100 credits，100MB 存储，不滚动）；需 SQL 建模（交易所钱包标签 → 净流入），可自定义交易所集合（CoinMetrics 做不到的分所口径）。
- CryptoQuant: config/local_secrets.yaml 未发现 cryptoquant key；且 CryptoQuant API 的 exchange-flows/netflow 端点仅 Professional/Premium 付费档开放（免费档仅网站查看、无 API 凭证）→ 免费路径为付费墙，不可行（付费墙：netflow API 仅 Professional/Premium 档，免费档无 API 凭证）。
- 两条路径本机均无 key → 未实测，不编造数据。

## 判定与局限

### 数据可用性（实测）

- **CoinMetrics Community API（免费）**：**可用**。btc 1d 直接给 4 个 flow 指标（FlowInExNtv/FlowOutExNtv/FlowInExUSD/FlowOutExUSD）+ 2 个交易所持仓（SplyExNtv/SplyExUSD），无需 key，单请求拿全史。
- **频率限制（实证）**：1h/1b 返回 403（社区档仅 1d）；`FlowTnxCount` 返回 400（不受支持）；目录中无 `FlowInExchanges` 分所口径。
- **Dune / CryptoQuant**：本机无 key 未实测；Dune 需注册免费账号 + API key，CryptoQuant netflow API 为付费墙（免费档不可用）——详见下节。

### 与收益的关联（判定口径：CI 下界>0 → GO_LONG / 上界<0 → GO_SHORT / 含0 → NO_GO）

- 表3 wash_cvd × 事件日-1 净流入: 净流入-低 NO_GO；净流入-中 NO_GO；净流入-高 GO_LONG；净流入-全 GO_LONG
- 表2 净流入 vs 当日 btc 收益: Pearson -0.090 (n=1627)；vs 次日: +0.045 (n=1626)（描述性，相关不是信号）

### 判定

- **免费交易所净流入路径：可用（CoinMetrics Community API）**。无需 key、单请求全史（2011-04-24 → 2026-08-06，5584 行，0 缺失日），日频净流入 = FlowInExNtv − FlowOutExNtv（+USD 版与 SplyEx 持仓），已落盘 `btc_exchange_netflow_daily.csv` 供下游复用。频率仅 1d（1h/1b 实测 403），无分所口径（无 FlowInExchanges）。
- **数据质量评估：中等**。全行 `-status=flash`（社区档无 final 修订标记，值可能随上游修订）；全所汇总口径（CoinMetrics 交易所集合，非 Binance 单独口径）。适合做宏观背景/共振变量（日频、与价格同步），不适合事件级精确拆分。
- **wash_cvd 附加价值（描述性）**：事件日-1 净流入高三分位 24h 超额 +2.24%（CI [+1.33, +3.21]，n=440，GO_LONG），低/中分位 NO_GO——washout 前一天交易所净流入高（承接买盘）与更优 24h 结果同现；样本内观察，需独立样本复核，不构成信号。
- **Dune 免费账号注册：暂不值得（作为 T3-2 免费替代）**。CoinMetrics 免费已覆盖日频全史净流入，Dune 的边际价值仅在分所/地址级拆分，需 SQL 建模 + 2500 credits/月额度管理；除非后续研究明确需要分所口径（如 Binance 单独净流入对齐币安 wash_cvd），否则注册投入产出比低。CryptoQuant 免费档不可行（netflow API 为付费墙）。

### 局限

- 全部行 `-status=flash`（社区档无 final 标记）：值可能随 CoinMetrics 上游修订变化，历史回测结论需在最终修订版上复核。
- 净流入为全所汇总口径（CoinMetrics 覆盖的交易所集合），非 Binance 单独口径，无分所拆分；与 wash_cvd（币安永续数据）存在口径错配。
- 事件日-1 净流入分层：事件集中在 2022-2026，滚动 90 日分位 warmup 会排除窗口前段少量事件；分层 n 见上表，样本不足层诚实标注。
- 相关性检验为描述性，无多重检验校正；不构成交易信号，仅评估免费数据源价值。
- Dune 免费档需自行建模（钱包地址标签），工作量大且额度有限（2500 credits/月）；CryptoQuant netflow API 为付费墙——均见判定。