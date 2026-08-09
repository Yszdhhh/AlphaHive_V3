# 前向数据源实测：E21 清算风暴 + 161 np_z + funding/OI

- 生成时间: 2026-08-08（工作站本地）
- Agent: ForwardDataSources（market-researcher）
- 背景: coinglass 免费维 `liquidation` 停于 **2026-06-23 03:00 UTC**；`ls_top_trader`/`ls_global`/`net_position` 更早停于 **2026-05-26~28**；E21 / 161 np_z 前向 blocked
- 方法: 官方 OpenAPI/changelog 直读 + HTTP/WS 实机探针（Python requests/websockets）+ 双源检索（xAI + Gemini）
- 口径: **已确认事实** vs **文档/二手** 分开；禁止编造未探针的响应体
- 关联: 侦察稿 `reports/parallel_grok_liqsources.md`（本报告为**实测加固版**，含 L/S·np_z·funding/OI）

---

## 0. 执行摘要（给主 agent）

| 目标 | 最可行前向路径 | 阻塞点 | 工作量 |
|---|---|---|---|
| **E21 市场级清算风暴** | **Coinalyze** `liquidation-history`（注册 free key）回填 1h/daily + **多所 WS 自归档**（Binance `!forceOrder@arr` + Bybit `allLiquidation` + OKX REST/WS + Gate 1h REST） | 本机**无** Coinalyze key → 200 路径未跑通；须 Owner 注册 5 分钟 | **2–4 人日**上线双轨；阈值须重校准 |
| **161 np_z** | **无** `net_position_change_cum` 同构免费源。次优: Binance **topLongShortPositionRatio** 差分 / z 作**代理**；`ls_top`/`ls_global` 可**直接**用币安公开 REST + vision metrics 深回填 | 代理 ≠ 原 np_z，161 结论须在新序列上重跑，不可直接搬阈值 | **1–2 人日**归档器 + **0.5–1 日**161 重测 |
| **funding / OI 前向增强** | funding: `GET /fapi/v1/fundingRate` 深历史可用；OI: `openInterestHist` 仅 **30d** + **data.binance.vision metrics** 日文件深史；Coinalyze 亦可（需 key） | OI 1h 超 30d 须 vision 或自建快照 | **0.5–1 人日** |

**一句话**: E21 = Coinalyze（历史/日对账）+ WS（前向）；np_z 原定义**断供**→用 top trader position ratio 代理并重验；funding 已通，OI 用 REST30d+vision 补深史。

---

## 1. Coinalyze（清算 / LS / OI / funding 聚合）

### 1.1 已确认事实（探针 + 官方文档 2026-08-08）

| 项 | 结果 | 证据 |
|---|---|---|
| Base | `https://api.coinalyze.net/v1` | OpenAPI servers |
| 文档 | https://api.coinalyze.net/v1/doc/ | HTTP 200，Redoc HTML |
| OpenAPI | https://api.coinalyze.net/v1/doc/api-spec.json | HTTP 200，37855 bytes |
| **无 key** | 全部业务端点 **401** `{"message":"Invalid/Missing API key"}` | 实机: `/` `/future-markets` `/liquidation-history` `/open-interest-history` `/funding-rate-history` |
| **demo/test/free/public/0/null/sandbox** | 全部 **401** | 实机 query + header |
| 鉴权方式 | header 或 query 名 **`api_key`** | 文档原文 |
| 注册拿 key | Sign up → https://coinalyze.net/account/api-key/ | 文档原文；**无公开 demo key** |
| 费用 | API **免费**（站点去广告另付）；公开引用需注明 | 文档原文 |
| 限速 | **40 calls/min/key**；超限 **429** + `Retry-After` | 文档原文 |
| symbols 计费 | 逗号最多 **20**；**每个 symbol 计 1 次 call** | OpenAPI parameter description |

### 1.2 端点清单（OpenAPI paths，均需 key）

| Method | Path | 用途 |
|---|---|---|
| GET | `/exchanges` | 交易所代码 |
| GET | `/future-markets` | 合约符号映射（含 `oi_lq_vol_denominated_in`, `has_long_short_ratio_data`） |
| GET | `/spot-markets` | 现货 |
| GET | `/open-interest` | 当前 OI |
| GET | `/funding-rate` / `/predicted-funding-rate` | 当前资金费 |
| GET | `/open-interest-history` | OI 历史 |
| GET | `/funding-rate-history` / `/predicted-funding-rate-history` | funding 历史 |
| GET | **`/liquidation-history`** | **E21 主候选** |
| GET | `/long-short-ratio-history` | LS 历史（r/l/s） |
| GET | `/ohlcv-history` | OHLCV |

### 1.3 `GET /liquidation-history` 契约（文档/OpenAPI，**响应体未在无 key 下实测 200**）

**Query（全部必填除非注明）**

| 参数 | 类型 | 说明 |
|---|---|---|
| `symbols` | string | 如 `BTCUSDT_PERP.A`；最多 20；每 symbol=1 call |
| `interval` | enum | `1min,5min,15min,30min,1hour,2hour,4hour,6hour,12hour,daily` |
| `from` / `to` | int64 | UNIX **秒**，inclusive |
| `convert_to_usd` | `true`/`false` | 默认 false；E21 应对齐 USD 时用 **true** |

**响应 schema（OpenAPI `liquidation_history`）**

```json
[
  {
    "symbol": "BTCUSDT_PERP.A",
    "history": [
      { "t": 1717682400, "l": 12345.6, "s": 6789.0 }
    ]
  }
]
```

- `t`: interval 起点（秒）
- `l`: Longs liquidation volume
- `s`: Shorts liquidation volume  
- 量纲: 见该 market 的 `oi_lq_vol_denominated_in` ∈ {BASE_ASSET, QUOTE_ASSET, CONTRACTS}；**务必 `convert_to_usd=true` 或本地 mark 折算** 才能对齐 coinglass `long_liquidation_usd` / `short_liquidation_usd`

### 1.4 历史深度 / 保留策略（官方原文，已确认）

> We keep only between **1500 and 2000** datapoints for intraday timeframe/granularity (1 minute till 12 hours), the old data is deleted each day. For **daily** timeframe/granularity **we do not delete the old data**.

| interval | 约可回看 | 对 E21 |
|---|---|---|
| 1hour | 1500–2000h ≈ **62–83 天** | 可覆盖 2026-06-23→今（~46 天，2026-08-08）的 1h 缺口 |
| 5min | 1500–2000×5min ≈ 5–7 天 | 仅短窗 |
| daily | **不删** | 长史风暴标签 / 粗粒度 |

**含义**: Coinalyze 云端 **不能**当永久 1h 湖 → 本地必须日归档。

### 1.5 40 rpm 下每日增量是否够用（算术，已确认）

假设 universe≈123 币（本地 liquidation 文件数）或 paper universe 66：

| 场景 | calls | 耗时 @40 rpm |
|---|---|---|
| 123 symbols × 1 endpoint × 1 window（每批 20） | ⌈123/20⌉ = **7** | ~10.5 s |
| 123 × (liq 1h + liq daily + LS 1h + OI 1h + funding) | 7×5 = **35** | ~1 min |
| 理论日上限 | 40×60×24 = **57,600** | 日更绰绰有余 |

**结论**: 日增量 **完全可行**；回填 1h 全保留窗亦只需数十 call。

### 1.6 未完成（须 Owner）

- [ ] 注册 free key 写入 `config/local_secrets.yaml`（gitignored）如 `coinalyze.api_key`
- [ ] 用 key 实拉 BTC/ETH 1h `convert_to_usd=true`，与本地 2026-05 重叠窗做相关/比率标定
- [ ] `/future-markets` 解析 Binance 主所 symbol 后缀（文档例 `.A` / `.0`）

### 1.7 `/long-short-ratio-history`（文档）

响应: `{ t, r, l, s }` = ratio / longs% / shorts% — 可作多所 LS 补充，**仍非** coinglass `net_position`。

---

## 2. 币安 forceOrder WebSocket

### 2.1 连接实测（2026-08-08）

| URL | 结果 |
|---|---|
| `wss://fstream.binance.com/ws/!forceOrder@arr` | **TCP/WS 握手成功**（~0.5s）；静默监听 **90s → 0 条消息** |
| `wss://fstream.binance.com/stream?streams=!forceOrder@arr` | 连接成功；**60s → 0 条** |
| `wss://fstream.binance.com/ws/btcusdt@forceOrder` | 连接成功；**60s → 0 条** |

**解释（已确认事实 + 文档）**: 无强平时**不推送**；当日探针窗口市场平静（OKX 有清算但 Binance 侧该窗可能无/极少）。**连接性已验证**；**实时 payload 样本未在本窗捕获**。

### 2.2 消息格式（官方 llms-full + 行业一致文档；本窗无 live sample）

```json
{
  "e": "forceOrder",
  "E": 1724216900000,
  "o": {
    "s": "BTCUSDT",
    "S": "SELL",
    "o": "LIMIT",
    "f": "IOC",
    "q": "0.005",
    "p": "9500.00",
    "ap": "9499.50",
    "X": "FILLED",
    "l": "0.005",
    "z": "0.005",
    "T": 1724216900000
  }
}
```

| 字段 | 含义 | E21 用法 |
|---|---|---|
| `E` / `o.T` | event / trade time ms | bar 归属 |
| `o.s` | symbol | 分币 / 市场加总 |
| `o.S` | BUY/SELL | **SELL≈多仓被强平(long liq)**；**BUY≈空仓被强平(short liq)**（强平单吃对侧） |
| `o.q` / `o.p` / `o.ap` | qty / price / avg | USD ≈ `ap * z`（filled） |
| 覆盖 | **USD-M 全市场** `!forceOrder@arr` | 非全量逐笔 |

### 2.3 节流（官方 changelog，已确认）

- 每 symbol、**1000ms 内只推 largest 一笔**（描述从 “latest” 改为 “largest”）
- 风暴期 **系统性低估** → E21 分位阈值 **必须**在自建序列上重估，禁止沿用 coinglass 绝对阈值

### 2.4 是否含「全部合约清算」？

| 说法 | 判定 |
|---|---|
| 全市场 stream 覆盖 USD-M 多 symbol | **是**（`!forceOrder@arr`） |
| 每个强平事件的全量逐笔 | **否**（1s largest snapshot） |
| 含 COIN-M / 他所 | **否**（仅 fstream USD-M；COIN-M 另 dstream） |

---

## 3. 清算历史 REST 替代

### 3.1 Binance

| 端点 | 探针 | 结论 |
|---|---|---|
| `GET https://fapi.binance.com/fapi/v1/allForceOrders` | **404** HTML 错误页 | **已死**（changelog: 2021-04-27 停维） |
| `GET https://dapi.binance.com/dapi/v1/allForceOrders` | **404** | **已死** |
| `GET https://fapi.binance.com/fapi/v1/forceOrders` | **401** `{"code":-2014,"msg":"API-key format invalid."}` | **USER_DATA**，仅**本账户**近 90 天，不可作市场 E21 |
| data.binance.vision `futures/um/daily/` | 无 liquidation 类目录（既有侦察 + 本任务未发现 liq 文件） | **无**官方清算历史文件 |
| vision `metrics` | **有** OI + L/S ratios（见 §4.3），**无** liquidation 列 | 不解决 E21 清算量 |

### 3.2 Bybit

| 端点 | 探针 |
|---|---|
| `/v5/market/liquidation` | **404** |
| `/v5/market/recent-liquidation` | **404** |
| `/v5/market/liq-orders` | **404** |
| 其它猜测路径 | **404** |
| WS `wss://stream.bybit.com/v5/public/linear` + `allLiquidation.BTCUSDT` | **subscribe success**；45s 内 0 清算事件（平静市） |
| 文档 | https://bybit-exchange.github.io/docs/v5/websocket/public/all-liquidation |

**结论**: Bybit **无**公开历史清算 REST；仅 WS 前向。字段文档: `T,s,S,v,p`（Buy=long liq）。

### 3.3 OKX（短窗 REST 可用）

```
GET https://www.okx.com/api/v5/public/liquidation-orders
  ?instType=SWAP&uly=BTC-USDT&state=filled&limit=100
```

| 项 | 实测 2026-08-08 |
|---|---|
| HTTP | **200** `code=0` |
| details 条数 | **~447–547**（limit 影响） |
| 时间跨度 | **~23.5–24h** |
| 字段 | `bkPx, posSide, side, sz, ts, time, bkLoss` |
| `after` 翻页 | 返回空 data（深史不可翻） |

**评级**: 前向校验 / 近 24h 补洞 **A**；回填 E21 缺口 **C**。

### 3.4 Gate.io

```
GET https://api.gateio.ws/api/v4/futures/usdt/liq_orders?contract=BTC_USDT&from=&to=&limit=
```

| 项 | 实测 |
|---|---|
| 无 from | 时常 **[]**（平静或仅极近） |
| `from=now-3600` 曾在其它窗返回条目 | 字段: `contract,size,order_size,fill_price,order_price,time` |
| `from/to` 跨度 **>1h** | **400** `range from/to must in 1 hour` |
| 跨 1h 但过旧窗 | **400** 同上 |

**评级**: 滚动 1h 拉取 **A**；长回填 **C**。

---

## 4. LS / 净持仓前向替代（161 np_z）

### 4.1 本地字段与停更（已读 parquet）

| 维 | 路径列 | BTC 停更（末 bar） | 161 用法 |
|---|---|---|---|
| `ls_top_trader` | `top_position_long_short_ratio` (+ long/short %) | **2026-05-26 23:00** | div 分子 |
| `ls_global` | `global_account_long_short_ratio` (+ %) | **2026-05-27 03:00** | div 分母 |
| `net_position` | `net_position_change_cum` 等 | **2026-05-28 06:00** | **`np_z = rolling_z(net_position_change_cum, 720)`** |
| `liquidation` | long/short_usd | **2026-06-23 03:00** | E21 / liq_short_z |

### 4.2 币安公开 REST（**无需 API key**，已实测 200）

Base: `https://fapi.binance.com/futures/data`

| 端点 | 映射 coinglass | 响应字段（实测） | 历史深度（实测） |
|---|---|---|---|
| `/topLongShortPositionRatio` | **≈ ls_top_trader**（top 20% 保证金用户的**仓位**多空） | `longAccount, shortAccount, longShortRatio, timestamp`（字段名仍叫 longAccount，语义是 position share） | **最多约 30 天**；`startTime` 超 30d → `-1130`；`period=1h&limit=500` ≈ 20.8d；`1d` 最多 30–31 根 |
| `/topLongShortAccountRatio` | top **账户数**多空（coinglass 未单列，近 top account） | 同上结构 | 同 30d |
| `/globalLongShortAccountRatio` | **≈ ls_global**（全网账户） | 同上 | 同 30d |
| `/takerlongshortRatio` | ≈ taker_buysell 类 | `buyVol, sellVol, buySellRatio, timestamp` | 同 30d 量级 |
| `/openInterestHist` | ≈ oi 快照 | `sumOpenInterest, sumOpenInterestValue, ...` | **30d** 硬顶 |

**鉴权**: 文档有的写要 `X-MBX-APIKEY`；**本机无 key 全部 200**。生产可继续无 key，注意 IP weight。

**周期**: `5m,15m,30m,1h,2h,4h,6h,12h,1d`；limit 默认 30 max **500**。

**样本（BTCUSDT 1h，探针时点）**:

```text
top position: longShortRatio≈1.54, longAccount≈0.607
top account:  longShortRatio≈1.20, longAccount≈0.546
global acct:  longShortRatio≈1.12, longAccount≈0.529
```

与本地 ls_top 末值 ratio≈1.28–1.29 **量级同阶**（不同日、定义近但不保证数值连续）。

### 4.3 data.binance.vision **metrics**（深历史 L/S + OI）

```
https://data.binance.vision/data/futures/um/daily/metrics/BTCUSDT/BTCUSDT-metrics-YYYY-MM-DD.zip
```

实测 `BTCUSDT-metrics-2026-08-06.zip` HTTP 200：

```text
header:
create_time,symbol,sum_open_interest,sum_open_interest_value,
count_toptrader_long_short_ratio,sum_toptrader_long_short_ratio,
count_long_short_ratio,sum_taker_long_short_vol_ratio
```

- 粒度: **5m**（日文件 288 行）
- 历史: S3 列表自 **2020-09** 起有 zip
- **可回填** ls_top 类（`sum_toptrader_long_short_ratio`）与 global 类（`count_long_short_ratio`）及 OI，**远超** REST 30d
- **仍无** net_position_change 列

### 4.4 np_z 能否替代？

| 方案 | 定义 | 与 161 `np_z` | 建议 |
|---|---|---|---|
| **A. 原样 net_position** | coinglass `net_position_change_cum` z | 同构 | **前向不可用**（源停更且无交易所同构 API） |
| **B. top position ratio 代理** | `np_proxy = rolling_z( Δ_24h log(longShortRatio_top_pos) )` 或 `rolling_z(longAccount_top_pos diff 24h)` | **弱代理**：反映大户仓位倾向变化，不是 USD 净持仓累计 | **主推荐前向**；须重跑 161 分层 |
| **C. OI × (2L−1) 变化** | `signed_oi = OI * (long% - short%)` 再 diff/z | 中等接近「净多名义」 | 可作对照特征 |
| **D. Coinalyze LS history** | `r/l/s` 多所 | 非 net_position | 辅助 |
| **E. 放弃 np_z 前向** | 仅历史窗 meta | — | 若代理重测失败则降级 |

**明确结论**:

1. **`topLongShortPositionRatio` 可替代 coinglass `ls_top_trader` 的主体**（大户仓位多空比）。
2. **`globalLongShortAccountRatio` 可替代 `ls_global` 的主体**（全网账户多空比）。
3. **`net_position` / `np_z` 无同构免费 API** → **不能**声称「已恢复 161 原特征」；只能 **proxy + 独立复核**。
4. div=`top_long% − global_long%` 可用币安 top position longAccount − global longAccount **直接重建**（前向 + vision 回填）。

### 4.5 Bybit account-ratio（补充）

`GET https://api.bybit.com/v5/market/account-ratio?category=linear&symbol=BTCUSDT&period=1h`  
实测 200: `buyRatio/sellRatio/timestamp`；1d limit=200 可回溯更长。可作非 BN 对照，非 np_z。

---

## 5. funding / OI 前向增强（附带实测）

| 源 | 端点 | 实测 | 深度 | 用途 |
|---|---|---|---|---|
| BN funding | `GET /fapi/v1/fundingRate` | 200，limit 最大 1000 | 分页可至 **数年**（探针 800d 窗返回 1000 条自 2024-05） | 主 funding 前向/回填 |
| BN premium | `GET /fapi/v1/premiumIndex` | 200 | 瞬时 | mark/index/lastFunding |
| BN premium klines | `GET /fapi/v1/premiumIndexKlines` | 200 | kline 规则 | 基差 |
| BN OI now | `GET /fapi/v1/openInterest` | 200 | 瞬时 | 快照归档 |
| BN OI hist | `GET /futures/data/openInterestHist` | 200 | **≤30d** | 近窗 1h OI |
| BN vision metrics | 日 zip | 200 | **2020→** 5m OI+L/S | 深史 OI/L/S |
| Bybit OI | `/v5/market/open-interest` | 200 | 分页 | 多所 |
| Bybit funding | `/v5/market/funding/history` | 200 | 分页 | 多所 |
| Coinalyze | OI/funding history | 需 key | intraday 滚动 + daily 长 | 多所聚合 |

**本地 funding_ohlc 亦停于 2026-06-23** → 应用 BN `fundingRate` **立即**可续写（无需 Coinalyze）。

---

## 6. 推荐接入方案

### 6.1 E21 前向最可行路径

```text
                    ┌─────────────────────────────────────┐
                    │  历史缺口 2026-06-23 → T0            │
                    │  Coinalyze liquidation-history      │
                    │  interval=1hour, convert_to_usd=true│
                    │  + daily 长备份                      │
                    └─────────────────┬───────────────────┘
                                      │
                                      ▼
┌──────────────┐   日终对账    ┌──────────────────────────┐
│ Coinalyze    │◄────────────►│ 本地 parquet              │
│ 增量 1h/daily│              │ data/liq_forward_1h/      │
└──────────────┘              └────────────▲─────────────┘
                                           │ 重采样 1h
              ┌────────────────────────────┼────────────────────────┐
              │ WS 常驻自归档               │                        │
              ▼                            ▼                        ▼
     Binance !forceOrder@arr     Bybit allLiquidation.*     OKX liq REST/WS
     (largest/1s 低估)           Gate liq_orders 1h 滚拉     (+可选)
```

**落地步骤**

1. **D0（Owner 5min）**: 注册 Coinalyze key → `local_secrets.yaml`
2. **D0–D1**: 脚本拉 BTC/ETH 重叠窗 vs coinglass，估 scale；回填 2026-06-23→今 1h+daily（123 币 ~7 call/端点）
3. **D1–D2**: WS writer（BN+Bybit+OKX）→ 逐笔/快照落盘 → 1h long/short_usd
4. **D2–D3**: 日终 Coinalyze 对账；E21 风暴检测在**新序列**上重算分位（禁止旧阈值）
5. **可选付费**: CoinGlass API ≥$29/mo 同构字段（非免费约束时）

### 6.2 161 np_z 前向替代

```text
ls_top  ──► BN topLongShortPositionRatio (1h) 日归档
            + vision metrics sum_toptrader_long_short_ratio 回填 2026-05-26 缺口

ls_global ► BN globalLongShortAccountRatio (1h) 日归档
            + vision metrics count_long_short_ratio

net_pos  ─► ✗ 无同构
            代理候选 np_proxy_z = rolling_z( Δ24h(top_position_longAccount), 720 )
            或 signed_oi_z = rolling_z( Δ24h(OI×(2L−1)), 720 )
            → 必须重跑 scripts/161_positioning_divergence.py 逻辑
```

**div 前向**: 可恢复（top long% − global long%）。  
**np_z 前向**: 仅 proxy；161「np_z<-1 → GO_SHORT 过滤」**状态 = 待重验**，不能直接接线 108。

### 6.3 funding/OI

- funding: 已有 BN REST → 直接续写 `funding_ohlc` 或并行 `binance_free_db`
- OI 近窗: `openInterestHist` 1h 滚动 30d 归档（每日拉避免丢）
- OI 深史/补洞: vision metrics zip

---

## 7. 工作量估计

| 工作包 | 内容 | 人日 |
|---|---|---|
| W1 Coinalyze client | key 配置、symbol 映射、限速 40rpm、liq/LS/OI/funding pull、本地 parquet | 0.5–1 |
| W2 E21 回填+标定 | 重叠窗 scale、缺口 1h 回填、daily 备份、简单 QA 图 | 0.5–1 |
| W3 WS 归档器 | BN forceOrder + Bybit allLiq + OKX/Gate 辅助、断线重连、1h 聚合 | 1–1.5 |
| W4 LS/np proxy 归档 | BN futures/data 三端点小时拉 + vision metrics 回填脚本 | 0.5–1 |
| W5 161/E21 重测 | 新序列上风暴阈值 + np_proxy 分层（研究，非接线） | 0.5–1 |
| W6 funding/OI 续写 | fundingRate 分页 + OI hist 日更 | 0.5 |
| **合计（免费路径）** | | **约 3.5–6 人日** |

---

## 8. 源对照总表（本轮实测）

| 源 | 端点/通道 | 鉴权 | 额度 | 历史 | E21 | np_z/LS | 实测状态 |
|---|---|---|---|---|---|---|---|
| Coinalyze liq | `/liquidation-history` | **api_key 必需** | 40 rpm free | 1h~2–3mo；daily 长 | **主回填** | LS 另端点 | 401 无 key；契约已读 |
| BN forceOrder WS | `!forceOrder@arr` | 无 | 连接限 | 无历史 | **主前向** | — | **已连接**；0 msg 静市 |
| BN allForceOrders | REST | — | — | — | 不可用 | — | **404 死** |
| BN forceOrders | REST USER_DATA | key | 90d 本户 | 本户 | 不可用 | — | **401** |
| Bybit liq | WS only | 无 | — | 无 REST | 前向 | — | sub OK；REST 404 |
| OKX liq | REST+WS | 无 | — | ~24h | 校验 | — | **200 ~24h** |
| Gate liq | REST | 无 | — | ≤1h/次 | 滚拉 | — | 超窗 400 |
| BN top/global LS | `/futures/data/*` | **无 key 可** | IP weight | **30d** | — | **ls 主替代** | **200** |
| BN vision metrics | 日 zip | 无 | 下载 | **2020+ 5m** | — | LS+OI 深回填 | **200** 含 L/S 列 |
| BN funding | `/fapi/v1/fundingRate` | 无 | — | 多年分页 | — | funding 增强 | **200** |
| BN OI hist | `openInterestHist` | 无 | — | **30d** | — | OI | **200** |
| 真 net_position | — | — | — | — | — | **无替代同构** | — |

---

## 9. 核实标记

| 声明 | 状态 |
|---|---|
| Coinalyze 无 key → 401；无可用 demo key | **已确认事实** |
| Coinalyze OpenAPI 契约与 40rpm / 1500–2000 / daily 不删 | **已确认事实**（官方 doc） |
| Coinalyze 200 真实 history 数值 | **未验证**（缺 key） |
| BN `!forceOrder@arr` 可连接 | **已确认事实** |
| BN forceOrder 实时 JSON 本窗样本 | **未捕获**（0 msg）；格式来自官方文档 |
| BN allForceOrders 404 死亡 | **已确认事实** |
| OKX liq ~24h / Gate ≤1h | **已确认事实** |
| Bybit 无 liq REST；WS 可订阅 | **已确认事实** |
| BN top/global LS 无 key 200、30d 顶 | **已确认事实** |
| vision metrics 含 top/global LS + OI | **已确认事实** |
| net_position 无交易所同构 REST | **已确认事实**（BN/Bybit/OKX 探针范围内） |
| topLongShortPositionRatio ≈ 原 np_z | **否**；仅为代理假设，**待重测** |

---

## 10. 链接速查

| 用途 | URL |
|---|---|
| Coinalyze docs | https://api.coinalyze.net/v1/doc/ |
| Coinalyze OpenAPI | https://api.coinalyze.net/v1/doc/api-spec.json |
| Coinalyze key | https://coinalyze.net/account/api-key/ |
| BN llms-full（forceOrder changelog） | https://developers.binance.com/en/docs/llms-full.txt |
| BN top LS position | https://fapi.binance.com/futures/data/topLongShortPositionRatio |
| BN global LS | https://fapi.binance.com/futures/data/globalLongShortAccountRatio |
| BN funding | https://fapi.binance.com/fapi/v1/fundingRate |
| BN vision | https://data.binance.vision/ |
| Bybit allLiquidation docs | https://bybit-exchange.github.io/docs/v5/websocket/public/all-liquidation |
| OKX liq REST | https://www.okx.com/api/v5/public/liquidation-orders |
| Gate liq | https://api.gateio.ws/api/v4/futures/usdt/liq_orders |
| 前序侦察 | `reports/parallel_grok_liqsources.md` |

---

## 11. 风险（实现必读）

1. **WS 低估 vs 聚合源**: 风暴日偏差最大，恰是 E21 信号区 → 双轨 + 重校准。  
2. **Coinalyze intraday 滚动删除**: 不日归档则再次断供。  
3. **字段名陷阱**: BN position 端点仍返回 `longAccount` 键名。  
4. **np_z 代理不可静默替换**: 161 效应可能消失或反转。  
5. **多所覆盖差**: coinglass 多所加总 ≠ BN-only WS 加总。  
6. **单位**: 张 / base / USD 混用会污染 z-score。

---

*仅数据源实测与接入方案，不构成交易建议；不修改项目脚本/配置。*
