# E21 清算数据替代源侦察报告（parallel_grok_liqsources）

- 生成时间: 2026-08-08 UTC（工作站日期）
- 任务: 为 AlphaHive V3 E21（市场级清算风暴，历史验证 168h +2.86%）寻找**免费可用**清算数据替代源
- 背景事实（本地已确认）:
  - coinglass raw_1h/liquidation 字段: time, long_liquidation_usd, short_liquidation_usd, _symbol, datetime
  - BTCUSDT 样本: 2024-06-06 → **2026-06-23 03:00 UTC** 停更（17918 行 1h bar）
  - binance_free_db 无 liquidation 维度
- 方法: 官方文档直读 + 实机 HTTP 探针 + 双源检索（xAI/Gemini；xAI 多次超时则以 Gemini+官方页+探针为准）
- 口径: **已确认事实** vs **未验证/二手** 分开标注；评级 A=免费可用可落地 / B=需工程或付费门槛 / C=不可用或不匹配 E21

---

## 0. 源对比总表（每源一行）

| 源 | 数据内容 | 免费额度 | 历史深度 | 粒度 | 接入方式 | 评级 |
|---|---|---|---|---|---|---|
| Binance USD-M WS !forceOrder@arr / symbol@forceOrder | 全市场/单币强平订单流（公开） | 免费、无需 key | **无历史**（仅实时） | 逐笔快照，**每 1000ms 仅推最大一笔**（非全量） | WS: wss://fstream.binance.com/ws/!forceOrder@arr | **A**（前向采集） |
| Binance REST GET /fapi/v1/forceOrders | **仅本账户**强平/ADL | 免费但需 API key 签名 | 近 **90 天**（用户自身） | 订单级 | USER_DATA，不可作市场信号 | **C**（非市场级） |
| Binance REST GET /fapi/v1/allForceOrders | 曾为全市场历史强平 | — | — | — | **2021-04-27 起停维，不再接受请求** | **C** |
| Binance Data Vision data.binance.vision | futures um daily 公共文件 | 免费下载 | klines/trades 等多年 | 日文件 | 实测 **无** liquidationSnapshot 目录（见 §1） | **C**（清算维度不存在） |
| Bybit V5 WS allLiquidation.{symbol} | 线性/反向/USDC 强平流 | 免费公开 WS | 无 REST 历史 | 推送 500ms；side/size/破产价 | wss://stream.bybit.com/v5/public/linear 订阅 topic | **A**（前向） / 历史 **C** |
| OKX REST GET /api/v5/public/liquidation-orders | 公共强平订单（SWAP 等） | 免费、无需 key | 实测 BTC-USDT **~24h / ~1000 条** | 逐笔 details | https://www.okx.com/api/v5/public/liquidation-orders?instType=SWAP&uly=BTC-USDT&state=filled | **A**（短窗） / 深历史 **C** |
| OKX WS liquidation-orders | 实时强平 | 免费公开 | 无 | ≤1 更新/秒/合约 | wss://ws.okx.com:8443/ws/v5/public | **A**（前向） |
| Gate REST GET /api/v4/futures/usdt/liq_orders | USDT 永续强平订单 | 免费公开（探针 200） | from/to **必须在 1 小时内**；无参时仅最近一小撮 | 逐笔 | https://api.gateio.ws/api/v4/futures/usdt/liq_orders?contract=BTC_USDT | **A**（实时/1h 窗） / 回填 **C** |
| Gate .../liquidates | 需 Timestamp 头（探针 400） | 视鉴权 | 未在无 key 下验证 | — | 非公开免鉴权路径 | **B/C** |
| Bitget WS liquidation | 合约强平频道（二手/Tardis 记载） | 声称免费公开 | 无可靠免费深历史 | 聚合/限流（二手称 1s 最大单） | 官方新文档 URL 301→UTA intro，稳定性差 | **B** |
| Coinalyze Free API | 多所聚合 long/short 清算量历史 | **完全免费**（注册拿 key）；40 次/分 | **daily 不删历史**；intraday 仅保留约 **1500–2000** 点后滚动删除 | 1min…12hour + daily；字段 l/s | GET https://api.coinalyze.net/v1/liquidation-history | **A**（首选免费历史+日更） |
| CoinGlass API v4 | 与现网同构的聚合清算历史 | **无免费 API**；Hobbyist **$29/mo** 起；30 req/min | 1d 可 all-time（付费档）；Hobbyist interval **≥4h** | 聚合 USD long/short | https://open-api-v4.coinglass.com/api/futures/liquidation/aggregated-history + header CG-API-KEY | **B**（最贴合但付费） |
| Tardis.dev | 交易所原生 WS 归档（含 liquidations） | 样例/试用有限；完整历史付费 | 多年 tick | 逐笔（exchange-native） | https://docs.tardis.dev / https://tardis.dev | **B**（回填利器，非免费日更） |
| Dune Analytics | 链上 DEX 清算（GMX/部分 HL） | 免费 SQL 额度 | 视表 | 事件级 | 无 CEX Binance 撮合清算表 | **C**（不覆盖 E21 CEX 市场风暴） |

---

## 1. 币安 USD-M：清算订单流 / 历史 / 额度

### 1.1 已确认事实

| 项 | 结论 | 证据 |
|---|---|---|
| 公开 WS 强平流 | **有** | 官方 changelog（developers.binance.com llms-full）明确: symbol@forceOrder 与 !forceOrder@arr |
| 流式端点 | wss://fstream.binance.com/ws/!forceOrder@arr（全市场）；wss://fstream.binance.com/ws/BTCUSDT@forceOrder（单币示例） | 行业通用 + Gemini 检索汇总；与 connector 生态一致 |
| 节流 | 自 2021-04-27 起不再推「全量实时单」；**最多约 1 次/秒**；2026-08 changelog 进一步写明 1000ms 内只推 **largest** 一笔 | 官方 changelog 原文 |
| 全市场历史 REST | GET /fapi/v1/allForceOrders **已停维**（2021-04-27） | 同上 changelog；探针返回 404 HTML |
| 用户强平 REST | GET https://fapi.binance.com/fapi/v1/forceOrders 为 **USER_DATA**，需 API key；无 key 探针 → code -2014 HTTP 401；且仅近 **90 天本账户** | 实机探针 + changelog「Only support querying data in the past 90 days」 |
| data.binance.vision 清算文件 | S3 列表 data/futures/um/daily/ 子目录仅有: aggTrades, bookDepth, bookTicker, indexPriceKlines, klines, markPriceKlines, metrics, premiumIndexKlines, trades — **无 liquidation 类目录** | 实机 ListBucket 2026-08-08 |
| 免费额度 | 公开 WS/行情无需 key；标准 IP 权重限频（与其他 fapi 公共接口同类） | 币安公共 API 惯例 |

### 1.2 文档链接（真实 URL）

- 产品总览 / WS 索引: https://developers.binance.com/en/docs/products/derivatives-trading-usds-futures/Introduction
- Liquidation Order Streams（文档站路径，新站 SPA 渲染不稳定）: https://developers.binance.com/docs/derivatives/usds-margined-futures/websocket-market-streams/Liquidation-Order-Streams
- 变更日志（forceOrder / allForceOrders 行为）: https://developers.binance.com/en/docs/llms-full.txt （内含 2021-04-27、2026-04-06、2026-08 相关条目）
- 公共数据站: https://data.binance.vision/
- 公共数据说明: https://github.com/binance/binance-public-data

### 1.3 对 E21 的含义

- **前向监测**: Binance WS 可自建 1h long/short_liquidation_usd（用 order 方向×qty×price），但风暴期会**系统性低估**（1s/最大单节流）。
- **历史回填 / 填 2026-06-23 缺口**: 币安官方**没有**可用的免费全市场清算历史 API/文件。

---

## 2. Bybit / OKX / Bitget / Gate

### 2.1 Bybit（已确认）

- **WS（免费）**: Topic allLiquidation.{symbol}，覆盖 USDT/USDC/Inverse；推送频率 **500ms**；字段 T/s/S/v/p（时间、symbol、Buy=多仓被强平、数量、破产价）。
- **文档**: https://bybit-exchange.github.io/docs/v5/websocket/public/all-liquidation
- **REST 历史**: 探针 GET /v5/market/liquidation → **404**；无公开深历史清算 REST。
- **评级**: 前向 **A**；回填 **C**。

### 2.2 OKX（已确认）

- **WS**: channel liquidation-orders；公共入口文档锚点
  - https://www.okx.com/docs-v5/en/#order-book-trading-market-data-ws-liquidation-orders-channel
  - #public-data-websocket-liquidation-orders-channel
  - 连接: wss://ws.okx.com:8443/ws/v5/public
  - 二手/文档惯例: 每合约最多约 1 更新/秒
- **REST（免费、已探针）**:
  - GET https://www.okx.com/api/v5/public/liquidation-orders?instType=SWAP&uly=BTC-USDT&state=filled
  - 2026-08-08 探针: code=0，约 **1003** 条 details，时间跨度 **~23.5h**
  - 字段示例: bkPx, posSide, side, sz, ts
  - 文档页: https://www.okx.com/docs-v5/en/#public-data-rest-api-get-liquidation-orders
- **评级**: 短窗增量/校验 **A**；多月回填 **C**。

### 2.3 Bitget（部分确认 / 文档漂移）

- 旧版 mix 文档站仍存在: https://bitgetlimited.github.io/apidoc/en/mix/
- 新站路径 .../contract/websocket/public/Liquidation-Channel **301 到 UTA intro**（实机），页面内容未给出清算 channel 正文。
- Tardis FAQ 记载: Bitget Futures WS liquidation channel（自 2026-04-28 起收录）— **二手但专业数据商**。
- **未**获得稳定免费深历史 REST。
- **评级**: **B**（可做前向，需自行对照 WS 订阅包稳定后再生产化）。

### 2.4 Gate.io（已确认 REST）

- **公开 REST（探针 200）**:
  - GET https://api.gateio.ws/api/v4/futures/usdt/liq_orders?contract=BTC_USDT&limit=100
  - 返回: contract, size, order_size, fill_price, order_price, time
- **历史窗**: from/to 探针报错 range from/to must in 1 hour → **单次查询跨度 ≤1h**；无参时仅最近数十条（BTC 样本 ~0.7h）。
- GET .../liquidates 无 Timestamp → 400 MISSING_REQUIRED_HEADER（非免鉴权市场流）。
- WS futures.liquidates：文档站 403/反爬，未在本次直接读到正文；**REST 已足够支撑 1h 滚动拉取**。
- API 总文档（可能地区限制）: https://www.gate.io/docs/developers/apiv4/en/
- **评级**: 近实时增量 **A**；长历史回填 **C**。

---

## 3. 免费聚合源

### 3.1 CoinGlass（已确认：API 无免费档）

- 定价页实读 2026-08-08: Hobbyist **$29/mo**、Startup $79、Standard $299、Professional $699；**无 Free API 档**。
  - https://www.coinglass.com/pricing
- 清算聚合历史:
  - GET https://open-api-v4.coinglass.com/api/futures/liquidation/aggregated-history
  - Header: CG-API-KEY
  - 文档: https://docs.coinglass.com/reference/aggregated-liquidation-history
  - 参数: exchange_list, symbol, interval, limit≤1000, start_time, end_time
  - 响应: aggregated_long_liquidation_usd / aggregated_short_liquidation_usd — **与本地 parquet 字段同构**
- Hobbyist: interval **≥4h**；更高档放开更细粒度。
- 网站免费图表 ≠ 可编程历史 API。
- **评级**: **B**（最省心续写 coinglass 序列，但不符合「免费」硬约束）。

### 3.2 Coinalyze（已确认：免费 API + 清算历史）

- 文档: https://api.coinalyze.net/v1/doc/
- OpenAPI: https://api.coinalyze.net/v1/doc/api-spec.json
- 注册免费 key: https://coinalyze.net/account/api-key/
- **清算端点**:
  - GET https://api.coinalyze.net/v1/liquidation-history
  - Query:
    - symbols（逗号分隔，最多 20；每 symbol 计 1 次调用）
    - interval: 1min | 5min | 15min | 30min | 1hour | 2hour | 4hour | 6hour | 12hour | daily
    - from, to: UNIX **秒**
    - convert_to_usd: true/false
- 响应 schema: symbol + history 数组，元素含 t / l / s
  - l = Longs liquidation volume
  - s = Shorts liquidation volume
- **限额**: 40 calls/min/key；429 + Retry-After
- **保留策略（官方原文）**:
  - intraday（1m–12h）只保留约 **1500–2000** 个点，每日删除更旧数据
  - **daily 不删除旧数据**
- **评级**: **A** — 当前唯一「免费用、可程序化、带历史、字段接近 coinglass」的聚合源。

### 3.3 Tardis.dev（付费历史归档）

- 文档: https://docs.tardis.dev
- FAQ 明确支持多所 liquidations 归一化 CSV/重放；完整历史商业授权。
- 捕获的是交易所 WS 原语（含节流后的 forceOrder），**不是**比交易所更全的隐藏全量。
- **评级**: **B**（一次性回填/研究）；不适合作为免费日更主链。

### 3.4 其他

- 名称提及但未在本次完成可验证免费 API 契约的: Hyblock、Coinank 等 → 不写入 A 级推荐。

---

## 4. 链上 / Dune / 替代

| 来源 | 结论 | 说明 |
|---|---|---|
| Dune × CEX（Binance 等） | **无**撮合引擎清算表 | 清算发生在中心化撮合，不上链；Dune 仅有 CEX 充提地址流等 |
| Dune × GMX 等 | 有事件/社区看板 | 仅 DEX 永续，体量与结构 ≠ E21 训练所用 coinglass 多所 CEX 聚合 |
| Hyperliquid | 链上可见，Dune/Allium 部分表 | 单一 venue，不能替代「市场级」多所风暴 |
| 评级 | **C**（对 E21 主路径） | 可作辅助 narrative，不可作 feature 主输入 |

Dune 浏览入口: https://dune.com/browse/dashboards

---

## 5. 与本地 E21 特征的对齐要点

本地 coinglass 1h bar 字段: long_liquidation_usd, short_liquidation_usd（美元名义）, time（ms）

| 候选源 | 能否直接对齐 1h USD long/short | 缺口 2026-06-23→今 | 前向日更 |
|---|---|---|---|
| Coinalyze 1hour + convert_to_usd=true | **高**（l/s 量纲需用 convert 与样本校验） | 受 1500–2000 点保留限制：1h 约可回看 **~2–3 个月**；更早用 daily | 是 |
| Coinalyze daily | 日频，需降采样/改 E21 频率或做日聚合风暴 | **深历史可用** | 是 |
| 多所 WS 自建 | 需自己×价变 USD、聚合 long/short；风暴低估 | **不能回填** | 是（最稳） |
| OKX/Gate REST | 逐笔短窗 | 不能填两月缺口 | 可作校验 |
| CoinGlass 付费 | **同构** | 可精确回填 | 是 |

---

## 6. 结论与推荐接入方案

### 6.1 总推荐（免费约束下）

**主路径（免费）= Coinalyze 历史/日更 + 多所 WS 自建前向双轨**

1. **历史回填 / 缺口填补（2026-06-23 → 今，及以后日归档）**
   - 源: **Coinalyze Free API**
   - 端点: https://api.coinalyze.net/v1/liquidation-history
   - 建议:
     - 先拉 interval=1hour&convert_to_usd=true 覆盖保留窗内全部 1h（填停更后缺口，若缺口 < ~60–80 天通常够用）。
     - 同步拉 interval=daily 建立长历史对照与粗粒度风暴标签。
     - symbol 映射: 用 /future-markets 解析 BTCUSDT_PERP.* 等代码；可按交易所后缀拆分或选主所再加总。
   - 频率: 日批即可；全市场多 symbol 时按 40 rpm 限速（20 symbols/call × 间隔 ≥1.5s）。
   - 校验: 与停更前重叠窗口（2026-05..06）对 coinglass BTC/ETH 1h 做相关/比率标定，写 scale 因子，避免量纲漂移污染 E21 阈值。

2. **前向监测（生产）**
   - **轨 A（必做）**: 常驻 WS 聚合器
     - Binance: wss://fstream.binance.com/ws/!forceOrder@arr
     - Bybit: allLiquidation.*（线性主要 USDT 永续 basket）
     - OKX: liquidation-orders
     - Gate: 每分钟 REST liq_orders 滚动 1h 窗补洞
   - 落库: 逐笔 → 重采样 1h → long_liquidation_usd/short_liquidation_usd parquet，目录可与 coinglass 并行如 data/liq_free_1h/
   - **轨 B（日终对账）**: Coinalyze 1h/daily 拉增量，检测 WS 漏接。

3. **若允许小额付费（非免费，备选）**
   - CoinGlass Hobbyist $29：直接续写同构 API，E21 特征迁移成本最低；4h 下限对「1h 风暴」略粗，必要时升 Startup。
   - Tardis: 仅当需要研究级 tick 回放或标定 WS 低估系数时按需采购。

### 6.2 不推荐

- 依赖 Binance forceOrders USER_DATA 或已死的 allForceOrders
- 依赖 data.binance.vision 清算文件（当前不存在）
- 用 Dune/GMX/HL 代替 CEX 市场级清算
- 假设交易所 WS = 全量真实清算（官方节流 → 风暴日偏差最大，恰与 E21 信号场景冲突）

### 6.3 最小可行工程切片（给主 agent）

```text
Day0: 申请 Coinalyze free key；拉 BTC/ETH 1h 与本地 2026-05 重叠段做相关标定
Day1: 回填 2026-06-23→T0 的 1h（Coinalyze）+ daily 备份
Day2: 上线 Binance+Bybit+OKX WS writer → 1h bar
Day3: 日终 job: Coinalyze 增量 + WS 对账；E21 前向 scanner 切到新路径
```

### 6.4 风险清单（必须写入实现）

1. **交易所 WS 低估**: Binance/OKX 明确限流；E21「风暴」分位阈值需在新数据上 **重新校准**，不可直接复用 coinglass 旧阈值。
2. **Coinalyze intraday 滚动删除**: 必须自建本地归档，不能把云端当永久 1h 湖。
3. **覆盖所差异**: coinglass 多所聚合 vs 自建前 N 所，市场级总分母变化 → 水平不可比。
4. **单位**: 合约张数 vs USD；务必 convert_to_usd 或本地 mark price 折算。
5. **CoinGlass 免费档已关闭 API**: 网页停更（2026-06-23）后不能再靠爬免费页充当研究级时间序列（合规与稳定性均差）。

---

## 7. 关键链接速查

| 用途 | URL |
|---|---|
| Binance forceOrder 说明（docs 路径） | https://developers.binance.com/docs/derivatives/usds-margined-futures/websocket-market-streams/Liquidation-Order-Streams |
| Binance 开发者 llms-full（changelog 可检索） | https://developers.binance.com/en/docs/llms-full.txt |
| Binance 公共数据 | https://data.binance.vision/ |
| Bybit allLiquidation | https://bybit-exchange.github.io/docs/v5/websocket/public/all-liquidation |
| OKX WS liquidation-orders | https://www.okx.com/docs-v5/en/#order-book-trading-market-data-ws-liquidation-orders-channel |
| OKX REST liquidation-orders | https://www.okx.com/api/v5/public/liquidation-orders |
| Gate liq_orders（实机） | https://api.gateio.ws/api/v4/futures/usdt/liq_orders |
| Coinalyze API 文档 | https://api.coinalyze.net/v1/doc/ |
| Coinalyze liquidation-history | https://api.coinalyze.net/v1/liquidation-history |
| CoinGlass 定价 | https://www.coinglass.com/pricing |
| CoinGlass aggregated liquidation history | https://docs.coinglass.com/reference/aggregated-liquidation-history |
| Tardis docs | https://docs.tardis.dev |

---

## 8. 核实标记

| 声明 | 状态 |
|---|---|
| Gate liq_orders HTTP 200 有数据 | **已确认事实**（2026-08-08 探针） |
| OKX public liquidation-orders ~24h | **已确认事实**（探针） |
| Binance forceOrders 无 key → 401 | **已确认事实** |
| Binance vision 无 liquidation 日目录 | **已确认事实**（S3 list） |
| Coinalyze 免费 + liquidation-history schema | **已确认事实**（官方 OpenAPI） |
| CoinGlass 无免费 API、$29 起 | **已确认事实**（定价页） |
| Bybit allLiquidation 文档 | **已确认事实**（官方 GitHub Pages） |
| Bitget 新文档 Liquidation-Channel 正文 | **未完全确认**（URL 301）；存在性依赖 Tardis 等二手 |
| Binance WS 具体 JSON 字段集 | **部分确认**（changelog 行为确认；完整 payload 以连 WS 为准） |
| 多所 WS 加总可复现 coinglass 数值 | **未验证**（需重叠窗标定实验） |

---

*本报告只做数据源侦察，不构成交易建议；不修改任何项目脚本/配置。*
