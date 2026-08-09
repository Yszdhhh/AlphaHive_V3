### 核心结论

1. **最高效且 100% 免费路径**：直接使用 Binance 官方数据仓 **[data.binance.vision](https://data.binance.vision/)**。官方免费提供所有永续合约（包含小众标的）的每日/每月 **`bookTicker`**（最优 bid/ask 毫秒级/秒级快照）与 **`aggTrades`**（逐笔成交）ZIP 文件。
2. **抽样快速校准路径**：使用 **[Tardis.dev](https://tardis.dev)** 的 Python/Node.js SDK，官方免费开放**每月 1 号**的全量 L2 订单簿 snapshot 与 tick-level 数据。
3. **最佳替代近似算法**：若仅有 OHLCV K线，推荐 **Corwin-Schultz (2012) High-Low 估算模型**（Python 包 `bidask`）；若有成交数据，使用 **Taker 买卖成交价差法 (Realized/Effective Spread from `aggTrades`)** 最接近真实的盘口+滑点执行成本。

---

### 1. Binance 公开 REST/WS 与历史快照归档

#### API 局限性
* **REST API** (`GET /fapi/v1/ticker/bookTicker` 或 `GET /fapi/v1/depth`)：仅能获取**当前实时单帧**订单簿快照，不支持按历史时间戳回溯查询。
* **WebSocket** (`<symbol>@bookTicker` / `<symbol>@depth`)：仅支持实时数据流推送。
* **Klines (K线)**：仅包含 OHLCV 及成交量/成交笔数，无 bid/ask 字段。

#### 官方历史数据归档：data.binance.vision
Binance 官方运行着开放数据中心 **`data.binance.vision`**，每日和每月自动归档所有 USDS-M (`um`) 和 COIN-M (`cm`) 永续合约的历史数据：

* **`bookTicker`（最优买卖价快照）**：
  * **目录路径**：`https://data.binance.vision/?prefix=data/futures/um/daily/bookTicker/`
  * **下载 URL 格式**：
    `https://data.binance.vision/data/futures/um/daily/bookTicker/{SYMBOL}/{SYMBOL}-bookTicker-{YYYY-MM-DD}.zip`
  * **包含字段**：`event_time`, `transaction_time`, `symbol`, `best_bid_price`, `best_bid_qty`, `best_ask_price`, `best_ask_qty`
* **`bookDepth`（订单簿深度快照）**：
  * **目录路径**：`https://data.binance.vision/?prefix=data/futures/um/daily/bookDepth/`
* **`aggTrades`（归集成交数据）**：
  * **目录路径**：`https://data.binance.vision/?prefix=data/futures/um/daily/aggTrades/`
* **自动化批量下载工具**：
  * Binance 官方脚本仓库：[binance-public-data](https://github.com/binance/binance-public-data)
  * 开源 Python 工具：`pip install binance-historical-data`

---

### 2. Dune Analytics 数据集评估

* **结论**：Dune Analytics **不适用**于 CEX 小众永续合约的历史点差校准。
* **原因**：
  1. **数据源类型**：Dune 专注于**链上 EVM / Solana 数据**。其 `dex.trades` 仅记录 DEX（如 Uniswap/Raydium）的 Swap 最终结算，完全没有 CEX（如 Binance/OKX）的 L2/L3 订单簿或 Bid-Ask 盘口。
  2. **Kaiko 数据在 Dune 的实际情况**：Kaiko 在 Dune 上仅提供 Chainlink 预言机节点运行指标或定制项目分析，**未开放免费的全量 CEX 订单簿/Bid-Ask 点差数据表**。Kaiko 商业点差表需付费通过其 API 或 Snowflake Data Share 获取。
  3. **免费档限制**：Dune 免费账户仅有 2500 Credits/月，无法支持大批量点差导出。

---

### 3. 其他免费 / 低成本数据源横向比对

| 数据源 | 历史 Bid-Ask / 盘口支持 | 免费/低成本策略 | 适用场景与资源链接 |
| :--- | :--- | :--- | :--- |
| **data.binance.vision** | **完全支持** (`bookTicker`, `bookDepth`) | **100% 免费**，全量历史每日 ZIP 压缩包 | 币安永续/现货首选（[Binance Vision](https://data.binance.vision/)） |
| **Tardis.dev** | **完全支持** (Tick-level L2/L3) | **每月 1 号数据完全免费**（无需 API Key） | 跨交易所抽样校验（[Tardis.dev Docs](https://docs.tardis.dev/)） |
| **Bybit Data Archive** | **完全支持** (OrderBook, Ticker, Trades) | **100% 免费**，官方数据导出中心 | Bybit 标的校准（[Bybit Public Data](https://public.bybit.com/)） |
| **OKX Data Center** | **完全支持** (OrderBook snapshots, Trades) | **100% 免费**，官方历史行情中心 | OKX 标的校准（[OKX Historical Market Data](https://www.okx.com/cdn/disaster_recovery/market_data)） |
| **Gate.io Archive** | **完全支持** (Orderbooks, Deals) | **100% 免费**，开放 HTTP CSV 归档 | Gate.io 标的校准（`https://download.gatedata.org/`） |
| **CoinAPI** | 支持 (Quotes, OrderBook) | **免费额度极少**（仅限测试），历史 Flat Files 按量高额收费 | 机构级付费回测（[CoinAPI Flat Files](https://www.coinapi.io/)） |
| **CoinGecko** | **不支持** (仅 OHLCV/Volume) | 免费 10,000 次/月 | 仅能用于宏观价格跟踪 |
| **CryptoCompare** | **已停用** | **不可用** | API 已于 2026 年 5 月彻底关停服务 |
| **Kaggle / HuggingFace** | 部分支持 (如 OKX 1s LOB, Kraken High-Freq) | 免费开源 | 学术 Benchmark（如 Kaggle 的 `OKX Crypto Orderbook & Trades`） |

> **Tardis 免费抽样代码示例**（`pip install tardis-dev`）：
> ```python
> from tardis_dev import download_datasets
> # 无须 API key，可免费下载每月 1 号全天数据
> download_datasets(
>     exchange="binance-futures",
>     data_types=["book_ticker", "agg_trades"],
>     from_date="2024-01-01",
>     to_date="2024-01-02",
>     symbols=["AAOIUSDT"]
> )
> ```

---

### 4. 历史 Spread 缺失时的替代近似方案

针对偏门标的或缺盘口快照的场景，计算真实执行成本的算法优先级如下：

#### 方案 1：【最推荐·最逼真】基于 `aggTrades` 的实效点差法 (Realized / Effective Spread)
* **原理**：利用免费可得的 `aggTrades` 中的 `is_buyer_maker` 标识（`True` 表示主动卖单吃 Bid 盘，`False` 表示主动买单吃 Ask 盘）。
* **计算公式**（按 1 分钟 / 5 分钟窗口聚合）：
  $$\text{Realized Spread} \approx \frac{\bar{P}_{\text{Taker Buy}} - \bar{P}_{\text{Taker Sell}}}{P_{\text{mid}}}$$
  * $\bar{P}_{\text{Taker Buy}}$：该窗口内 `is_buyer_maker == False` 的成交加权均价。
  * $\bar{P}_{\text{Taker Sell}}$：该窗口内 `is_buyer_maker == True` 的成交加权均价。
* **优势**：不仅涵盖了静态盘口 Bid-Ask Spread，还计入了主动单吃深度的**市场冲击滑点 (Slippage)**，最贴近量化系统真实执行成本。

#### 方案 2：【统计学最优】Corwin-Schultz (2012) High-Low 模型
* **原理**：利用连续两期（如 2 个单小时 vs 1 个双小时）的 High 和 Low 价格比值。从波动率中分离出 Bid-Ask Spread（因为买卖点差会系统性扩大 High-Low 区间）。
* **Python 实现**：
  ```bash
  pip install bidask
  ```
  ```python
  from bidask import edge
  # 传入 High 和 Low 序列即可一键计算历史 Spread
  spread_series = edge(df['high'], df['low'])
  ```
* **评价**：适合**仅有 OHLCV 历史 K 线**时的估计。但在极度不活跃标的出现恶意“插针”（针尖拉大 High-Low）时会高估点差。

#### 方案 3：Roll (1984) 模型
* **公式**：$\text{Spread} = 2 \sqrt{-\text{Cov}(\Delta P_t, \Delta P_{t-1})}$。
* **缺点**：加密市场在短周期存在强动量（正自相关），常导致协方差为正而无法开平方，失效概率 >30%，不推荐。

#### 方案 4：DEX vs CEX 溢价
* **评价**：**不适用于 CEX 执行成本校准**。小众标的在 DEX 的流动性通常显著落后于 CEX，DEX-CEX 价差反映的是跨市场套利摩擦而非单边盘口点差，用其估算会导致执行成本严重高估。

---

### 5. 小众永续标的历史点差校准的最可行免费路径

针对贵团队“小众永续标的（如 AAOI/ALAB/WDC/AMAT，24h 成交额较低）”的执行成本校准，请按以下 3 步落地：

1. **获取精确历史盘口**：编写 Python 脚本连接 **`data.binance.vision`**，批量下载目标合约上市以来的 `bookTicker` daily ZIP。解压即可获取毫秒级的 `best_bid` / `best_ask`，直接算出静态 Bid-Ask Spread 分布。
2. **计算滑点与实效成本**：同步下载对应的 `aggTrades` daily ZIP，按 1 分钟/5 分钟窗口计算 **Realized Spread**（`is_buyer_maker` 买卖成交价差），将其作为实际市价吃单的成本上界。
3. **补全缺失时段**：对少数极早上市或缺少盘口快照的时段，使用 **Corwin-Schultz (2012)** 算法（`bidask` 包）基于已有的 1-min K 线 High/Low 进行插值估算。
