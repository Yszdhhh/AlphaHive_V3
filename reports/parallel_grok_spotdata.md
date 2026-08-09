# 币安现货 klines 可得性与小币覆盖侦察（A3 期现中性 carry）

- **Agent**: GrokSpotData（market-researcher）
- **生成时间**: 2026-08-08 07:15 UTC
- **用途**: A3 期现中性 carry 回测（现货多 + 永续空收 funding；需现货价算基差）
- **约束**: 只读侦察；不给交易下单建议
- **双源核对**: 官方 docs（GitHub `binance-spot-api-docs` + gemini/xai 检索）× 本机 live REST 实测

---

## 1. API 免费可得性与限频（已确认事实）

### 1.1 端点与鉴权

| 项 | 结论 | 证据 |
|---|---|---|
| 是否免费 | **是**。公开 market data，**无需 API key** | live `GET` 返回 200；docs security type = `NONE` |
| 主 base | `https://api.binance.com` | [rest-api.md](https://github.com/binance/binance-spot-api-docs/blob/master/rest-api.md) |
| 备 base | `api1`–`api4`、`api-gcp.binance.com` | 同上 |
| 纯行情推荐 | `https://data-api.binance.vision` | docs + live 200（与主站同路径 `/api/v3/klines`） |
| klines | `GET /api/v3/klines` | weight **2**（官方固定，与 limit 无关） |
| 最新价 | `GET /api/v3/ticker/price` | live 测 weight **≈2**（单 symbol） |
| 交易对元数据 | `GET /api/v3/exchangeInfo` | live 测 weight **≈20–24** |

官方 klines 段（摘录确认 weight=2, limit max 1000）:
- https://raw.githubusercontent.com/binance/binance-spot-api-docs/master/rest-api.md （章节 *Kline/Candlestick data*）
- 开发者文档镜像: https://developers.binance.com/docs/binance-spot-api-docs/rest-api/market-data-endpoints

### 1.2 IP 级限频（live `exchangeInfo.rateLimits` @ 2026-08-08）

```json
[
  {"rateLimitType": "REQUEST_WEIGHT", "interval": "MINUTE", "intervalNum": 1, "limit": 6000},
  {"rateLimitType": "ORDERS",         "interval": "SECOND", "intervalNum": 10, "limit": 100},
  {"rateLimitType": "ORDERS",         "interval": "DAY",    "intervalNum": 1,  "limit": 200000},
  {"rateLimitType": "RAW_REQUESTS",   "interval": "MINUTE", "intervalNum": 5,  "limit": 300000}
]
```

| 限制 | 值 | 含义（回测拉数） |
|---|---|---|
| REQUEST_WEIGHT | **6000 / 分钟 / IP** | klines 每次 2 → 理论 **~3000 次/分钟** |
| RAW_REQUESTS | 300000 / 5 分钟 / IP | 另计原始请求数 |
| 超限 | HTTP 429 + `Retry-After`；持续撞限 → 418 IP ban（2 分钟–3 天） | docs *IP Limits* |
| 监控头 | `X-MBX-USED-WEIGHT-1M` | 每次响应可观测 |

**双源一致**: xai/gemini 检索与 live `exchangeInfo` 均指向 REQUEST_WEIGHT=6000/min、klines weight=2。  
（2023-08 起从旧 1200/min 上调，见 Binance 公告；当前以 live 为准。）

### 1.3 历史深度（startTime 可拉多远）

| 规则 | 已确认 |
|---|---|
| `startTime`/`endTime` | 毫秒；可任意早，但**不会早于该交易对实际上市 K 线** |
| 无 start/end | 返回最近 `limit` 根（默认 500，最大 1000） |
| 分页 | 下一段 `startTime = last_open_time + 1`；每页 ≤1000 |
| 更大批量 | 可走 `https://data.binance.vision/` 月/日文件（绕过 REST 权重）— https://github.com/binance/binance-public-data |

**Live 最早 1d bar（`startTime=2017-01-01`, limit=1）**:

| symbol | 最早现货 1d | 备注 |
|---|---|---|
| BTCUSDT | **2017-08-17** | 币安现货 BTC 起点 |
| ETHUSDT | **2017-08-17** | 同 |
| ARBUSDT | 2023-03-23 | 现货上市日 |
| PEPEUSDT | 2023-05-05 | 对应永续 `1000PEPEUSDT` |
| ENAUSDT | 2024-04-02 | |
| TRUMPUSDT | 2025-01-19 | |
| KITEUSDT | 2025-11-03 | |

→ **历史深度 = 该现货对上市日起全量可拉**；不是固定 N 年窗口截断。

---

## 2. 实测：BTC/ETH 现货 1d klines（2022-01 起）

**方法**: Python `urllib`，无 API key，base=`https://api.binance.com`，`interval=1d`，`startTime=2022-01-01T00:00:00Z`，`limit=1000` 分页。

| symbol | HTTP | calls | bars | first open (UTC) | last open (UTC) | first close | last close (probe) | 所用 weight 头 |
|---|---|---:|---:|---|---|---:|---:|---|
| BTCUSDT | 200 | 2 | **1681** | 2022-01-01 | 2026-08-08 | 47722.65 | ~65004.95 | `X-MBX-USED-WEIGHT-1M` 正常递增 |
| ETHUSDT | 200 | 2 | **1681** | 2022-01-01 | 2026-08-08 | 3765.54 | ~1916.01 | 同 |

样例请求（可复现）:

```
GET https://api.binance.com/api/v3/klines?symbol=BTCUSDT&interval=1d&startTime=1640995200000&limit=1000
```

首根返回 openTime=`1640995200000` = 2022-01-01 00:00:00 UTC — **与请求对齐，可行**。

`data-api.binance.vision` 同步测通（200）。

---

## 3. 现货可得性表（AlphaHive 永续 universe 子集）

**核对方式**（2026-08-08 live）:
1. `GET https://api.binance.com/api/v3/exchangeInfo` → 全部 USDT 现货 symbol（约 732 个 TRADING USDT）
2. `GET https://api.binance.com/api/v3/ticker/price` → 全市场最新价存在性
3. `GET https://fapi.binance.com/fapi/v1/exchangeInfo` + `premiumIndex` → 永续仍 TRADING、contractType、标记价/funding

### 3.1 总表

| 永续合约 | 永续状态 / 类型 | 现货交易对存在？ | 现货 ticker | 映射说明 | 真·双腿中性？ |
|---|---|---|---|---|---|
| ARBUSDT | TRADING / PERPETUAL | **是** | `ARBUSDT` | 同名现货 | **是** |
| 1000PEPEUSDT | TRADING / PERPETUAL | **是（缩放）** | `PEPEUSDT` | 无 `1000PEPEUSDT` 现货；`mark ≈ spot×1000`（probe ratio≈1.0028） | **是**（名义×1000 对齐） |
| KITEUSDT | TRADING / PERPETUAL | **是** | `KITEUSDT` | 同名 | **是** |
| TRUMPUSDT | TRADING / PERPETUAL | **是** | `TRUMPUSDT` | 同名 | **是** |
| ENAUSDT | TRADING / PERPETUAL | **是** | `ENAUSDT` | 同名 | **是** |
| MUUSDT | TRADING / **TRADIFI_PERPETUAL** | **是（代币化股票）** | `MUBUSDT` | base=`MUB`；mark≈spot（basis ~+2.5 bps） | **条件是**（tradifi 代币腿，非链上 MU） |
| CRCLUSDT | TRADING / **TRADIFI_PERPETUAL** | **是（代币化股票）** | `CRCLBUSDT` | base=`CRCLB`；basis ~+1.4 bps | **条件是** |
| SNDKUSDT | TRADING / **TRADIFI_PERPETUAL** | **是（代币化股票）** | `SNDKBUSDT` | base=`SNDKB`；basis ~+12–16 bps | **条件是** |
| XAGUSDT | TRADING / **TRADIFI_PERPETUAL** | **否** | — | 无 `XAGUSDT`/`XAGBUSDT` 现货 | **否**（仅永续） |
| SKYAIUSDT | TRADING / PERPETUAL | **否** | — | 无同名现货 | **否** |
| ESPORTSUSDT | TRADING / PERPETUAL | **否** | — | 无；`ESPUSDT` 不是同一资产 | **否** |
| UBUSDT | TRADING / PERPETUAL | **否** | — | 无 | **否** |
| RIVERUSDT | TRADING / PERPETUAL | **否** | — | 无 | **否** |
| LABUSDT | TRADING / PERPETUAL | **否** | — | `TSLABUSDT`/`ALABBUSDT` 为 TSLA 类股票代币，价 ~329 vs LAB 永续 ~0.126，**不是同一标的** | **否** |
| HUSDT | TRADING / PERPETUAL | **否** | — | 无（勿匹配 HOT 等） | **否** |
| MUSDT | TRADING / PERPETUAL | **否** | — | 无（`M` 代币）；勿与 `MUUSDT`/`MUBUSDT` 混淆 | **否** |
| RAVEUSDT | TRADING / PERPETUAL | **否** | — | 无 | **否** |
| VVVUSDT | TRADING / PERPETUAL | **否** | — | 无 | **否** |

### 3.2 分类汇总

| 类别 | 合约 | 回测含义 |
|---|---|---|
| A. 原生同名/可缩放现货 | ARB, 1000PEPE→PEPE×1000, KITE, TRUMP, ENA | 可算真基差；双腿中性 carry |
| B. Tradifi 现货代币孪生 | MU→MUB, CRCL→CRCLB, SNDK→SNDKB | 价差通常 <20 bps；可做「准中性」，但需单独审计赎回/合规/库存溢价 |
| C. 永续-only（无现货） | SKYAI, ESPORTS, UB, XAG, RIVER, LAB, H, M, RAVE, VVV | **只能做方向暴露简化版**（单边永续 ± funding），不能锁 delta |

**live 计数**: 18 个任务合约中，**5 原生现货 + 3 tradifi 孪生 = 8 可双腿**；**10 无现货**。

---

## 4. Funding 极端 × 现货可得性（30d / 7d live）

数据: `GET https://fapi.binance.com/fapi/v1/fundingRate`（无需 key），窗口约 30d 与 7d。  
年化近似: `mean_rate × 3 × 365`（按 8h 结算；**部分合约结算频率可能不同，ESPORTS n 偏大，年化仅作排序用**）。

### 4.1 任务宇宙 30d 均值 funding 排序

**Top（多头付空头 → 空永续收 funding）**:

| rank | perp | 30d mean | 30d ann~ | 现货双腿？ |
|---:|---|---:|---:|---|
| 1 | LABUSDT | +0.000204 | +22.3% | 否 |
| 2 | HUSDT | +0.000183 | +20.1% | 否 |
| 3 | RAVEUSDT | +0.000135 | +14.7% | 否 |
| 4 | MUSDT | +0.000127 | +13.9% | 否 |
| 5 | ESPORTSUSDT | +0.000110 | +12.0% | 否 |
| 6 | SNDKUSDT | +0.000099 | +10.8% | 条件是 (SNDKB) |
| 7 | RIVERUSDT | +0.000093 | +10.2% | 否 |
| 8 | SKYAIUSDT | +0.000067 | +7.3% | 否 |

**Bottom（偏负/最低 → 多永续或难收正 funding）**:

| rank | perp | 30d mean | 30d ann~ | 现货双腿？ |
|---:|---|---:|---:|---|
| 1 | TRUMPUSDT | **-0.000018** | **-2.0%** | 是 |
| 2 | ARBUSDT | +0.000003 | +0.3% | 是 |
| 3 | ENAUSDT | +0.000025 | +2.8% | 是 |
| 4 | XAGUSDT | +0.000028 | +3.1% | 否 |
| 5 | 1000PEPEUSDT | +0.000034 | +3.7% | 是 (PEPE×1000) |

**观察（事实）**: 30d funding **最高的一串几乎都是无现货小币**（LAB/H/RAVE/M/ESPORTS/RIVER/SKYAI）。  
有现货可锁的合约 funding 中等偏低；tradifi 里 SNDK 相对更高。

### 4.2 瞬时 premiumIndex（probe 时刻，非均值）

最高 lastFundingRate 样本: ESPORTS +3.98e-4, RAVE +2.07e-4, RIVER +1.83e-4, 1000PEPE +1.0e-4。  
最低: ARB −8.4e-5；多个 tradifi last=0。  
→ 横截面极端会变；回测应用历史 funding 序列而非单点。

---

## 5. 推荐双腿清单（Top/Bottom 各最多 5，仅现货可得）

定义（A3 口径）:
- **正 funding 双腿**: 现货多 + 永续空，收 funding，基差用现货价
- **负 funding 双腿**: 现货空 + 永续多（需现货借券/保证金；现货账户不一定支持，回测可先纸面）

### 5.1 Top 5（正 funding 侧、现货可得，按 30d mean）

| # | 永续 | 现货腿 | 30d ann~ | 7d ann~ | 备注 |
|---:|---|---|---:|---:|---|
| 1 | **SNDKUSDT** | `SNDKBUSDT` | +10.8% | +5.9% | tradifi；basis 常 +10–16 bps，进成本 |
| 2 | **1000PEPEUSDT** | `PEPEUSDT` ×1000 | +3.7% | +7.8% | 原生缩放；流动性好 |
| 3 | **KITEUSDT** | `KITEUSDT` | +5.8% | +5.3% | 原生同名；上市偏新(2025-11 spot) |
| 4 | **MUUSDT** | `MUBUSDT` | +4.7% | +2.5% | tradifi；basis 紧 |
| 5 | **ENAUSDT** | `ENAUSDT` | +2.8% | +4.1% | 原生同名；深度较好 |

（若样本外扩基准腿: **BTCUSDT/ETHUSDT** 现货完备，7d ann~ +5.3%/+3.5%，已有 `basis_carry.md` 审计。）

**未能进入 Top5 的高 funding**: LAB/H/RAVE/M/ESPORTS/RIVER/SKYAI — **全部无现货**，不可真中性。

### 5.2 Bottom 5（最低/负 funding、现货可得）

| # | 永续 | 现货腿 | 30d ann~ | 含义 |
|---:|---|---|---:|---|
| 1 | **TRUMPUSDT** | `TRUMPUSDT` | **−2.0%** | 唯一 30d 均值为负；中性需 **空现货+多永续**（借券约束） |
| 2 | **ARBUSDT** | `ARBUSDT` | +0.3% | 近零；正 carry 薄，更适合当基差/对冲对照组 |
| 3 | **CRCLUSDT** | `CRCLBUSDT` | ~+低个位数（7d +2.0%） | tradifi；funding 弱 |
| 4 | **ENAUSDT** | `ENAUSDT` | +2.8% | 有现货集合里偏低端 |
| 5 | **MUUSDT** | `MUBUSDT` | +4.7% | 有现货集合里中偏低（7d 更低） |

Bottom 侧「可收负 funding」的真候选在本宇宙里 **几乎只有 TRUMP**；其余 bottom 多为「正但小」，不是稳定的反向 carry。

### 5.3 只能做方向暴露简化版（无现货，按 30d |funding| 突出）

| 永续 | 30d ann~ | 简化版角色 |
|---|---:|---|
| LABUSDT | +22.3% | 高 funding 多头拥挤代理；不可锁 |
| HUSDT | +20.1% | 同 |
| RAVEUSDT | +14.7% | 同 |
| MUSDT | +13.9% | 同（≠ MU 股票） |
| ESPORTSUSDT | +12.0% | 同；结算频率需单独确认 |
| RIVERUSDT | +10.2% | 同 |
| SKYAIUSDT | +7.3% | 同 |
| UBUSDT / VVVUSDT / XAGUSDT | 中低 | 无现货；XAG 为 tradifi 无 spot 孪生 |

---

## 6. 结论（给 A3）

### 已确认事实
1. **币安现货 REST 公开免费**：`/api/v3/klines`、`/ticker/price`、`/exchangeInfo` 无需 key。  
2. **IP 权重**: live **6000 weight/分钟**；klines/ticker 各 **2**；理论 ~3000 klines 调用/分钟/IP。  
3. **历史**: 可自上市日全量分页；BTC/ETH 自 **2017-08-17**；2022-01 起 1d 拉 **1681** 根已实测成功。  
4. **任务 18 合约现货覆盖差**: 仅 **5 原生 + 3 tradifi 孪生** 可做双腿；**10 个 funding 更极端的小币无现货**。  
5. **1000PEPE**: 现货用 `PEPEUSDT`，数量/价格按 **×1000** 对齐（live ratio≈1.003）。  
6. **LAB ≠ TSLAB/ALABB**：不可误映射。

### 对「真·中性 vs 简化版」的含义
- **真·中性期现套利池很小**: ARB / PEPE(×1000) / KITE / TRUMP / ENA + tradifi(MU/CRCL/SNDK)。  
- **Funding 横截面最肥的尾部（LAB/H/RAVE/M/ESPORTS…）做不了双腿**，若只空永续则 **暴露方向**，与 A3「非方向现金流」目标不一致。  
- 实操分层建议（研究设计，非下单建议）:
  - **Pool A（真中性）**: 上表 Top/Bottom 现货可得集 + BTC/ETH 基准。  
  - **Pool B（tradifi 准中性）**: MU/CRCL/SNDK，单独计 basis 与代币结构风险。  
  - **Pool C（永续-only）**: 仅作 funding 描述统计或明确标注「方向暴露简化版」，不与 Pool A 混称中性 carry。

### 未验证 / 边界
- 现货 **借券费率与是否可空**（负 funding 反向腿）未测。  
- Tradifi 代币 **赎回、托管、地区限制** 未审。  
- 部分永续 funding 间隔是否恒为 8h（ESPORTS 样本密度异常）需用 `fundingInfo` 再核。  
- 本报告 funding 为 **2026-08-08 前 7d/30d 快照排序**，不是全历史分位；回测应连历史 funding 序列。

### 可验证 URL 清单
- Spot REST 总文档: https://github.com/binance/binance-spot-api-docs/blob/master/rest-api.md  
- Klines: `https://api.binance.com/api/v3/klines`  
- Ticker: `https://api.binance.com/api/v3/ticker/price`  
- ExchangeInfo: `https://api.binance.com/api/v3/exchangeInfo`  
- Market-data only: `https://data-api.binance.vision`  
- 批量历史: https://data.binance.vision/ / https://github.com/binance/binance-public-data  
- USD-M 永续 exchangeInfo: `https://fapi.binance.com/fapi/v1/exchangeInfo`  
- Funding 历史: `https://fapi.binance.com/fapi/v1/fundingRate`  
- Premium/funding 瞬时: `https://fapi.binance.com/fapi/v1/premiumIndex`  

---

*Probe 环境: Win/Python urllib；时间戳 2026-08-08T07:14Z 附近。结论区分已确认 live/docs 事实与排序快照。*
