# parallel_delisted_history — 下架币完整列表源 + 1h klines 可得性实测

- **Agent**: DelistedHistory (market-researcher)
- **Generated (UTC)**: 2026-08-08 12:18 UTC
- **Scope**: Binance USDT-M / spot 历史下架枚举 + 1h/4h klines 实测（幸存者偏差从「仅 SETTLING 下界」推向可重建完整 universe）
- **方法**: 全部端点 HTTP 实测；文档检索 pin `gemini`；`xai` 网页搜索本会话多次 timeout，**关键事实以 live HTTP 为准**，Gemini 叙述与实测冲突处已标注
- **不做**: 交易建议 / 代码实现

---

## 0. Executive summary

| 问题 | 结论（已确认事实） |
|------|-------------------|
| 仅 `exchangeInfo` SETTLING 是否完整？ | **否**。2026-08-08 实测 SETTLING=**127**（当前批次）；S3 档案另有 **136** 个已从 exchangeInfo 消失的 UM 符号 |
| 2021–2026 能否枚举全部 UM 合约？ | **基本能**。权威枚举源 = `data.binance.vision` S3 prefix 列表（UM monthly klines **986** symbols），再减交割/BUSD/SETTLED 别名 |
| SETTLING / 多数已下架 1h 能否拉？ | **能**。`fapi/v1/klines interval=1h` 对 SETTLING 全样本 + 27/31 已移除 USDT 永续返回全历史；仅 **4** 个符号 live 报 `-1121`，改走 vision zip 或 `*SETTLED` 别名 |
| 现货下架 1h？ | **能**。`exchangeInfo` 保留 `BREAK`（2303 pairs / 243 USDT）；`api/v3/klines` 1h 对 BREAK 实测可拉至下架时刻 |
| s009 的 4h 确认能否在下架池复测？ | **能**。SETTLING 与已移除（如 SRMUSDT）`interval=4h` 均 200；用 **vol>0 截断** 去掉结算后幽灵 K 线 |

**重建 universe 可行性**: **可以重建含（近）全部历史下架 UM 永续的研究 universe**，路径 = Vision S3 枚举 ∪ 当前 exchangeInfo，K 线 = fapi 优先 + vision 回退；现货用 BREAK 枚举即可。残差主要是极少数 live `-1121` 且需 zip 回退的符号，以及 BUSD/交割合约是否纳入研究定义的问题——不是「枚举不到」。

---

## 1. 下架列表源（实测）

### 1.1 候选矩阵

| 源 | 实测状态 | 用途 | 覆盖 | 格式 | 备注 |
|----|----------|------|------|------|------|
| **A. `GET https://fapi.binance.com/fapi/v1/exchangeInfo`** | ✅ 200 | 当前 TRADING / **SETTLING** / PENDING | **854** symbols：TRADING 726, **SETTLING 127**, PENDING_TRADING 1 | JSON `symbols[].symbol/status/onboardDate/deliveryDate/contractType` | **只含当前仍登记合约**；完全移除后消失 → 历史下界，非全集 |
| **B. `data.binance.vision` S3 ListBucket** | ✅ 200 | **历史 UM 符号全集枚举** | UM monthly klines **986**；daily **989**；其中 **136** 不在当前 exchangeInfo | AWS S3 XML `CommonPrefixes`；符号 = 末级目录名 | **最强可枚举完整源**；无需 API key |
| **C. Binance CMS 公告 catalogId=161 Delisting** | ✅ 200 | 下架事件时间线 / 人工核对 | **421** 篇；futures-ish 标题 ~76，spot-ish ~320 | JSON articles[`title,code,id`]；正文 detail `articleCode=` | 非结构化标题，需 NLP 抽 ticker；**不是**干净 symbol master |
| **D. Spot `GET https://api.binance.com/api/v3/exchangeInfo`** | ✅ 200 | 现货下架枚举 | **3680** symbols；**BREAK 2303**（USDT 243） | JSON `status=BREAK\|TRADING` | 现货下架**仍留在 exchangeInfo**，比期货好做 |
| **E. Spot/Margin `GET /sapi/v1/*/delist-schedule`** | ⚠️ 400 `-2014` API-key format invalid | 计划下架日程 | 需签名 key | JSON（文档） | **无 key 不可用**；且文档指向 spot/margin，**非 futures 历史全集** |
| **F. GitHub 维护 delisted 列表** | ❌ 无可用完整库 | — | `search/repositories?q=binance+delisted+symbols` → total_count=0；仅见 RSS scraper 类仓库 | — | **不能依赖**第三方静态完整列表 |
| **G. CoinGecko / CMC** | ⚠️ 仅活跃/通用列表 | 辅助元数据 | CG `exchanges/binance/tickers` 活跃页；无「Binance futures delisted master」 | JSON | **不能**枚举历史下架合约 |
| **H. Wayback CMC 快照** | 未作为主源实测 | 可能补洞 | 慢、非官方、对合约符号不完整 | HTML | 不推荐作主路径 |
| **I. COIN-M vision** | ✅ 200 | 币本位历史 | CM monthly klines **272** symbols | 同 S3 | 若策略只做 UM 可忽略 |

### 1.2 源 A — 当前 futures exchangeInfo（下界）

```
GET https://fapi.binance.com/fapi/v1/exchangeInfo
```

实测（2026-08-08）:

- `futures symbols = 854`
- `status`: `TRADING=726`, `SETTLING=127`, `PENDING_TRADING=1` (`GAIBUSDT`)
- SETTLING 样本均为 `contractType=PERPETUAL`，带 `onboardDate` + `deliveryDate`（即公告结算/下架时刻）
- `deliveryDate` 年份分布: 2022:3, 2024:21, 2025:45, 2026:58
- `onboardDate` 年份: 2020:12 … 2025:36（含早期永续）
- 样本: `OMGUSDT, WAVESUSDT, MKRUSDT, BLZUSDT, ACXUSDT, …`

**含义**: SETTLING = 「已公告结算但行纪仍保留元数据」的**当前批次**。更早被**彻底摘牌**的合约不在此列表 → 与项目已知「127 下界」一致。

### 1.3 源 B — data.binance.vision S3（完整枚举主源）✅

官方说明: [binance-public-data README](https://github.com/binance/binance-public-data) → [https://data.binance.vision/](https://data.binance.vision/)

**枚举方法（已实测）**:

```
GET https://s3-ap-northeast-1.amazonaws.com/data.binance.vision
    ?delimiter=/&prefix=data/futures/um/monthly/klines/&max-keys=1000
```

- 返回 S3 `ListBucketResult` XML；`IsTruncated=false`（986 < 1000，一页穷尽）
- 每个 `CommonPrefixes.Prefix` = `data/futures/um/monthly/klines/{SYMBOL}/`
- 浏览器 HTML 目录 `https://data.binance.vision/data/futures/um/daily/klines/` 直接 404（NoSuchKey）；**必须用 S3 list 或 `?prefix=` 门户**
- 文件下载: `https://data.binance.vision/data/futures/um/monthly/klines/{SYMBOL}/{interval}/{SYMBOL}-{interval}-{YYYY-MM}.zip`

**实测计数**:

| 集合 | N |
|------|---|
| Vision UM monthly klines symbols | **986** |
| 当前 fapi exchangeInfo | 854 |
| 交集 | 850 |
| **仅 vision（已从 exchangeInfo 消失）** | **136** |
| 仅 exchangeInfo（新上/未进月档） | 4 (`GAIBUSDT,GIGADEVUSDT,KOUSDT,RDDTUSDT`) |
| SETTLING ∩ vision | **127/127**（当前下架批次档案齐全） |

**仅 vision 的 136 分类**（规则分类，已确认）:

| 类 | N | 含义 | 研究是否计入「下架永续」 |
|----|---|------|-------------------------|
| `USDT_PERP_GONE` | **31** | 名称像 USDT 永续且已不在 exchangeInfo | **是（核心幸存者集合）** |
| `BUSD` | 41 | BUSD 报价永续/对（BUSD 退市） | 视 universe 定义 |
| `QUARTERLY_DELIVERY` | 46 | `BTCUSDT_210326` 等交割 | 通常排除（非永续研究） |
| `SETTLED_RENAME` | 17 | `AERGOUSDTSETTLED`, `BTCSTUSDTSETTLED`… | 别名/二次结算残留，映射回原符号 |
| `USDC` | 1 | `MATICUSDC` | 视定义 |

`USDT_PERP_GONE` 完整 31 个（S3 有目录、exchangeInfo 无）:

```
1000BTTCUSDT, AERGOUSDT, AKROUSDT, ANCUSDT, ANTUSDT, AUDIOUSDT, BDXNUSDT,
BLUEBIRDUSDT, BTCSTUSDT, BTSUSDT, BTTUSDT, BZRXUSDT, COCOSUSDT, DODOUSDT,
DOTECOUSDT, EOSUSDT, FOOTBALLUSDT, FRONTUSDT, GALUSDT, HNTUSDT, KEEPUSDT,
LENDUSDT, LUNAUSDT, MATICUSDT, MBLUSDT, NUUSDT, RNDRUSDT, SRMUSDT, SXPUSDT,
TOMOUSDT, YFIIUSDT
```

**K 线 zip 格式**（实测 `BTCSTUSDT-1h-2021-03.zip`）:

- CSV 无/有 header 两种都存在；列顺序与 fapi klines 一致:  
  `open_time,open,high,low,close,volume,close_time,quote_volume,count,taker_buy_volume,taker_buy_quote_volume,ignore`

### 1.4 源 C — 公告 Delisting 目录（事件源）

```
GET https://www.binance.com/bapi/composite/v1/public/cms/article/catalog/list/query
    ?catalogId=161&pageNo=1&pageSize=50
```

- `code=000000`, `data.total=421`, 分页可拉全 421 篇
- 同端点 `catalogId=48` = New Listing（2225）, `49`=Latest News 等
- 详情: `GET .../cms/article/detail/query?articleCode={code}` → 结构化 body
- Futures 标题样例:  
  - `Binance Futures Will Delist USDⓈ-M AERGOUSDT Perpetual Contract (2026-07-24)`  
  - `Binance Futures Will Delist Multiple USDⓈ-M Perpetual Contracts (2026-01-30)`
- Spot 标题样例: `Notice of Removal of Spot Trading Pairs - 2026-08-07`

**用途**: 给每个符号贴「官方下架日」标签、核对 deliveryDate；**不能替代 S3 枚举**（多合约打包公告、标题 ticker 不全，本次 futures-ish 标题仅直接匹配到约 42 个 `*USDT` 字样）。

### 1.5 源 D — Spot BREAK（现货完整下架列表）✅

```
GET https://api.binance.com/api/v3/exchangeInfo
```

| 指标 | 值 |
|------|-----|
| spot symbols | 3680 |
| BREAK 总计 | 2303 |
| BREAK USDT | **243** |
| BREAK by quote (top) | BTC 447, BUSD 378, BNB 366, USDT 243, ETH 217… |
| Vision spot monthly symbols | 3695 |
| BREAK USDT ∈ vision | **243/243** |

现货优势: 下架后 **status 留在 BREAK**，无需 S3 差分即可枚举。

### 1.6 不可用 / 弱源（避免浪费时间）

1. **Gemini 文档叙述**称「完全 delist 后 fapi klines 一律 Invalid」——与本节 §2 实测**冲突**（多数已移除永续仍 200）。以 HTTP 为准。
2. **无**维护中的 GitHub「完整 delisted futures JSON」。
3. **sapi delist-schedule** 无 API key → 400；且非历史全集。
4. CoinGecko/CMC **无** Binance 合约历史下架 master。

### 1.7 推荐「完整下架永续」重建公式

```text
UM_VISION = S3_list("data/futures/um/monthly/klines/")          # ~986
UM_LIVE   = fapi.exchangeInfo.symbols                           # ~854
UM_GONE   = UM_VISION - UM_LIVE                                 # ~136

PERP_DELISTED_HIST = {
    s ∈ UM_GONE
    if s.endswith("USDT")
    and "SETTLED" not in s
    and not re.search(r"_\d{6}$", s)      # drop quarterly
}                                                               # ~31

PERP_DELISTED_CURRENT = {s.status=="SETTLING"}                  # 127

PERP_DELISTED_ALL ≈ PERP_DELISTED_CURRENT ∪ PERP_DELISTED_HIST
                  ∪ map_settled_aliases(SETTLED_RENAME)         # 补 4 个 -1121

# 研究 universe（含幸存者）:
UNIVERSE_RESEARCH = {s.status in {TRADING,SETTLING}} ∪ PERP_DELISTED_HIST
# 或更干净: 全部 UM_VISION 过滤掉 quarterly + 非策略报价
```

**覆盖 2021–2026**: Vision 目录含 2020 起早期永续（如 `LENDUSDT` 2020-07）至 2026 交割/下架；SETTLING.deliveryDate 横跨 2022–2026。对「曾在 Binance UM 上存在过且写入 public data」的合约，**S3 列表即近全集**。

> 未验证传闻: 「是否存在从未进入 data.binance.vision 的极早期/测试合约」——当前无反例；若存在，偏差应远小于「只看 SETTLING 127」。

---

## 2. 1h klines 实测

### 2.1 接口

| 市场 | Endpoint | limit 上限（实测） |
|------|----------|-------------------|
| UM Futures | `GET https://fapi.binance.com/fapi/v1/klines?symbol=&interval=1h&startTime=&limit=` | 1500/页 |
| Spot | `GET https://api.binance.com/api/v3/klines?symbol=&interval=1h&startTime=&limit=` | 1000/页 |
| 档案 | `https://data.binance.vision/data/futures/um/monthly/klines/{SYM}/1h/*.zip` | 按月 zip |

分页: `startTime=0` 取最早，然后 `startTime=last_open_time+1` 直至空页。

### 2.2 SETTLING（仍在 exchangeInfo）— fapi 1h ✅ 全历史

| symbol | onboard | deliveryDate | 1h first | 1h last (wall) | last vol>0 | total 1h bars | pages |
|--------|---------|--------------|----------|----------------|------------|---------------|-------|
| OMGUSDT | 2020-07-02 | 2025-01-31 | 2020-07-02 09:00 | 2026-08-08 12:00 | 2025-01-31 09:00 | 53476 | 36 |
| BLZUSDT | 2020-09-17 | 2024-12-23 | 2020-09-17 07:00 | 2026-08-08 12:00 | 2024-12-23 08:00 | 51630 | 35 |
| ACXUSDT | 2024-12-06 | 2026-08-07 | 2024-12-06 15:00 | 2026-08-08 12:00 | 2026-08-07 08:00 | 14638 | 10 |
| WAVESUSDT | 2020-08-12 | 2024-06-11 | 2020-08-12 07:00 | 2026-08-08 12:00 | (未全表扫 nz，结构同) | first_page=1500 | — |
| RENUSDT / FTMUSDT / MKRUSDT / AGIXUSDT / AMBUSDT | 2020–2023 | 2024–2025 | ≈onboard | 2026-08-08 | 结算后应为 0 量 | first_page=1500 | — |

**关键行为（已确认）**:

1. `startTime=0` 回到 **onboard 附近**，不是截断到近 1 年。
2. 结算后仍持续返回 K 线至「现在」，但 **volume=0**（幽灵 flat bar）。样本 SETTLING 近期 5 根 vol 全 0。
3. 研究必须用 `last_nonzero_vol` 或 `deliveryDate` **截断**，否则会污染特征/标签。
4. `interval=1d` / `4h` 同样 200（见 §2.5）。

### 2.3 已从 exchangeInfo 移除的 USDT 永续 — fapi 1h

对 31 个 `USDT_PERP_GONE` 逐个探测:

| 结果 | N | 符号 |
|------|---|------|
| **fapi 1h 可用** | **27** | 1000BTTCUSDT, AKROUSDT, ANCUSDT, ANTUSDT, AUDIOUSDT, BLUEBIRDUSDT, BTSUSDT, BTTUSDT, BZRXUSDT, COCOSUSDT, DODOUSDT, DOTECOUSDT, EOSUSDT, FOOTBALLUSDT, FRONTUSDT, GALUSDT, HNTUSDT, KEEPUSDT, LENDUSDT, LUNAUSDT, MATICUSDT, MBLUSDT, NUUSDT, RNDRUSDT, SRMUSDT, TOMOUSDT, YFIIUSDT |
| **fapi -1121 Invalid symbol** | **4** | AERGOUSDT, BDXNUSDT, BTCSTUSDT, SXPUSDT |

**全量分页深度样本（fapi 可用）**:

| symbol | first | last bar | last vol>0 | bars | 解读 |
|--------|-------|----------|------------|------|------|
| SRMUSDT | 2020-09-05 | 2024-05-28 | 2022-11-15 | 32670 | 真下架后仍有长尾 0 量至 2024-05-28 |
| ANTUSDT | 2021-12-27 | 2024-05-28 | 2024-04-01 | 21196 | 下架≈last_nz |
| TOMOUSDT | 2020-10-12 | 2024-05-28 | 2023-11-14 | 31777 | 同 SRM 模式 |
| AKROUSDT | 2021-01-19 | 2022-05-27 | 2022-05-27 | 11835 | 末根即停 |
| 1000BTTCUSDT | 2022-01-26 | 2022-04-11 | 2022-04-11 | 1807 | 短寿命 |
| EOSUSDT | 2020-01-08 | 2025-05-21 | 2025-05-21 | (probe) | 较晚移除 |
| LENDUSDT | 2020-07-23 | 2020-11-10 | 2020-10-09 | (probe) | 极早 |
| MATICUSDT | 2020-10-22 | 2024-09-11 | 2024-09-04 | (probe) | 更名/迁移类 |

**4 个 -1121 的回退（已确认可用）**:

| 原符号 | Vision 1h zip | fapi 别名 | 别名 1h 范围 |
|--------|---------------|-----------|--------------|
| BTCSTUSDT | 2021-03 → 2026-06（大量 0 量月） | `BTCSTUSDTSETTLED` | 2021-03-04 → 2026-07-30 |
| AERGOUSDT | 2024-09 → 2026-06（月内仍有量） | `AERGOUSDTSETTLED` → `AERGOUSDTSETTLEDSETTLED` | 2024-09-10→2025-04-16 → 2025-04-16→2026-07-24 |
| SXPUSDT | 2020-07 → 2026-05；nz 至 ~2025-12-05 | `SXPUSDTSETTLED` | 2020-07-21 → 2026-06-02 |
| BDXNUSDT | 2025-06 → 2026-03；nz 至 2026-03-17 | `BDXNUSDTSETTLED` | 2025-06-03 → 2026-04-28 |

→ **没有「完全没 1h」的 UM 下架样本**；最坏 = 下 vision 月 zip。

### 2.4 Spot BREAK — `api/v3/klines` 1h ✅

| symbol | exchange status | first 1h | last 1h | last vol>0 | bars | pages |
|--------|-----------------|----------|---------|------------|------|-------|
| OOKIUSDT | BREAK | 2021-12-24 | 2024-11-06 | 2024-11-06 | 25150 | 26 |
| COCOSUSDT | BREAK | 2019-08-21 | 2023-05-29 | 2023-05-29 | 32913 | 33 |
| NPXSUSDT | BREAK | 2019-08-13 | 2021-04-05 | 2021-04-05 | 14386 | 15 |
| BTTUSDT | BREAK | 2019-01-31 | 2022-01-17 | 2022-01-17 | 25903 | 26 |
| KEYUSDT | BREAK | 2019-08-27 | 2024-12-10 | 2024-12-10 | 45654 | 46 |
| BADGER/MULTI/LOKA/REEF/EPX/VIDT/MDX… | BREAK | 均可 200 | 至下架日 | ≈last | first_page=1000 | — |
| WFLOWUSDT | ABSENT | -1121 | — | — | — | 需 vision 文件名 |

**现货特征**: 下架后 kline **停在最后交易日**，一般不刷长期 0 量幽灵（与 futures SETTLING 不同）。`RAYUSDT/LUNAUSDT/FTTUSDT` 实测仍为 **TRADING**（不是下架样例）。

### 2.5 4h 确认（s009 复测相关）✅

| symbol | API | 4h first | 4h last |
|--------|-----|----------|---------|
| ACXUSDT | fapi | 2024-12-06 12:00 | 2026-08-08 12:00 |
| BLZUSDT | fapi | 2020-09-17 04:00 | 2026-08-08 12:00 |
| SRMUSDT | fapi | 2020-09-05 00:00 | 2024-05-28 04:00 |
| OOKIUSDT | spot | 2021-12-24 04:00 | 2024-11-06 00:00 |

→ **s009 所需 4h（可由 1h 重采样或直拉 4h）在下架池可复测**。  
实务: 用 1h 拉全 + `vol>0`/`deliveryDate` 截断 → 重采样 4h，避免结算后 flat 影响确认逻辑。

### 2.6 与「日线可拉」关系

- 项目已知: SETTLING 日线可拉 — **确认**，且 **1h/4h 同样可拉**，深度到 onboard。
- 扩展: 多数 **已摘牌** 符号 fapi 仍吐历史 1h/1d/4h；不能仅因不在 exchangeInfo 就假设无 REST 数据。

### 2.7 Gemini vs 实测（双源核对）

| 断言来源 | 内容 | 核实 |
|----------|------|------|
| Gemini (data.binance.vision 枚举) | S3 目录可 list 出含下架符号 | ✅ 与 HTTP 一致（986） |
| Gemini (live klines) | 完全 delist 后 fapi 一律无效 | ❌ **部分错误**：31 个 gone 中 27 个 1h 仍 200；仅 4 个 -1121 |
| Live HTTP | SETTLING 与多数 gone 可拉全 1h，注意 0 量尾 | ✅ 主结论
| xAI web search | 本会话连续 timeout | ⚠️ 未提供独立网页侧证；不阻断（REST/S3 已实锤） |

---

## 3. 结论：能否重建含全部下架币的 universe？

### 3.1 答案

**能（UM 永续研究级别：近完整；现货：完整可枚举）。**

| 层级 | 以前（下界） | 现在（可完整化） |
|------|--------------|------------------|
| 当前批次下架 | SETTLING 127 | 同左 + 元数据 deliveryDate |
| 历史已摘牌永续 | 无法从 exchangeInfo 枚举 | Vision S3 差分 **+31 USDT**（+BUSD/别名可选） |
| K 线 1h/4h | 仅知日线 SETTLING | SETTLING 全历史 1h；gone 27/31 REST；4/31 vision/别名 |
| 现货下架 | 未系统化 | BREAK 243 USDT + 1h 直至下架 |

幸存者偏差可从「≥127 下架合约」**升级为**：

```text
bias_set ≈ SETTLING(127) ∪ USDT_PERP_GONE(31) ∪ (可选 BUSD/SETTLED映射)
```

再与全历史 TRADING 快照并集，即可做 **full-universe 回测 / wash_cvd 下架池复测**。

### 3.2 s009 4h 确认在下架池复测？

**可以。** 条件:

1. 标的池 = SETTLING ∪ fapi 仍有效的 gone ∪（可选）vision 回退符号  
2. 数据 = `fapi 1h` 分页至 earliest，或直拉 `4h`  
3. **硬截断** `open_time <= deliveryDate` 或最后 `volume>0` bar（否则 SETTLING/长尾 0 量会破坏 CVD/确认）  
4. 4 个 -1121: 用 `*SETTLED` 符号或 vision 1h zip，再对齐到原 ticker

### 3.3 实操优先级（研究管道）

1. **枚举**: S3 `um/monthly/klines` prefix → 持久化 symbol master（比只存 SETTLING 完整）  
2. **标签**: exchangeInfo status + catalog 161 公告日期 + deliveryDate  
3. **行情**: fapi klines 1h 优先；`-1121` → vision monthly zip；统一 vol>0 截断  
4. **现货**（若需要）: BREAK 过滤 + spot klines  
5. **不要**等第三方 GitHub delist 列表或无 key 的 sapi schedule 当主源  

### 3.4 残留风险（诚实边界）

| 风险 | 级别 | 说明 |
|------|------|------|
| Vision 漏档极冷门合约 | 低 | 未见实例；若有则偏差远小于仅 SETTLING |
| SETTLED 别名与原符号重叠/双份 | 中 | 需映射表去重，避免双计 |
| 0 量幽灵 bar | 中 | 必须截断，否则特征偏差 |
| 公告 ticker 抽取不全 | 低 | 枚举以 S3 为准，公告只做时间戳 |
| BUSD/交割是否进 universe | 定义问题 | 公式上已可分列 |
| xAI 检索 timeout | 低 | 不依赖其叙述 |

---

## 4. 附录 — 可复制探测命令

```bash
# 当前 SETTLING 计数
curl -s https://fapi.binance.com/fapi/v1/exchangeInfo | jq '[.symbols[]|select(.status=="SETTLING")]|length'

# S3 列出 UM 符号（一页）
curl -s 'https://s3-ap-northeast-1.amazonaws.com/data.binance.vision?delimiter=/&prefix=data/futures/um/monthly/klines/&max-keys=1000' | head

# SETTLING/下架 1h 最早一根
curl -s 'https://fapi.binance.com/fapi/v1/klines?symbol=ACXUSDT&interval=1h&startTime=0&limit=1'
curl -s 'https://fapi.binance.com/fapi/v1/klines?symbol=SRMUSDT&interval=1h&startTime=0&limit=1'

# 已移除且 -1121 的档案
curl -sI 'https://data.binance.vision/data/futures/um/monthly/klines/BTCSTUSDT/1h/BTCSTUSDT-1h-2021-03.zip'

# 现货 BREAK 1h
curl -s 'https://api.binance.com/api/v3/klines?symbol=OOKIUSDT&interval=1h&startTime=0&limit=1'

# 下架公告目录
curl -s 'https://www.binance.com/bapi/composite/v1/public/cms/article/catalog/list/query?catalogId=161&pageNo=1&pageSize=5'
```

### 临时产物（本机）

- `reports/external_intel/_tmp_vision_um_syms.txt` — 986 UM vision symbols  
- `reports/external_intel/_tmp_only_vision.txt` — 136 exchangeInfo 缺失符号  

（可被正式 pipeline 吸收后删除。）

---

## 5. Acceptance checklist

| # | 要求 | 状态 |
|---|------|------|
| ① | 下架列表源：实测可用 + 格式 + 覆盖范围 | ✅ §1：S3 986 / SETTLING 127 / 公告 421 / Spot BREAK 2303 |
| ② | 1h klines 实测：接口/币/深度 | ✅ §2：fapi+spot+vision；含全量分页深度表 |
| ③ | 结论：能否重建含全部下架币 universe | ✅ **能（近完整）**；s009 4h 可下架池复测（需 vol 截断） |

**END**
