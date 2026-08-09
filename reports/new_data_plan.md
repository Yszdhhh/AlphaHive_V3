# new_data_plan — E 方向：新数据补充（CME 快照实证 + 5 类候选评估）

## 0. 元信息
- **生成 UTC 时间**：2026-08-06 16:23 UTC（2026-08-07 00:23 北京时间）
- **方法**：① 写脚本 `scripts/125_cme_snapshot.py` 实际拉取 CME 机构持仓 45 个工作日并落盘 parquet（实证结果见 §1）；② 对 5 类候选数据源逐一做公开 API 连通性探测（DefiLlama / yfinance / mempool.space / farside / blockchain.info / bitcointreasuries / CoinGecko），结果写入各节评估表；③ 按"可得性 × 研究价值"给出接入优先级。
- **数据源路径**：CME 快照落盘 `C:\Users\10639\Desktop\🔒 加密资产\coinglass_db\macro\cme_bitcoin.parquet`（带 emoji，写死）；候选源 URL 见各节表。
- **局限**：
  1. 连通性探测受本机网络环境影响（部分源返回 SSL 错误/Cloudflare 403，已如实标注，不代表源永久不可用）。
  2. CME 数据发布滞后 1–2 自然日（2026-08-06/07 拉取时为空，见 §1），事件研究须容忍该滞后。
  3. DefiLlama 单币种（USDT/USDC 分列）历史端点实测不稳定，当前可用的是聚合总量序列。
  4. 链上"大户储备/交易所净流入"的免费源在 2026 年已基本消失（blockchain.info API 404 实测、farside 403 实测），该维度评级诚实偏低，需 Owner 提供外部资料（§5）。
  5. 本报告为研究模块，不含任何订单路径；所有接入均为 shadow_only 语义。

---

## 1. CME 机构持仓 —— 本次快照实证（可用 ✅）

### 1.1 快照实证结果（2026-08-06 16:23 UTC 运行）
`python scripts/125_cme_snapshot.py`（默认参数，45 个工作日窗口 2026-06-08 → 2026-08-07，end=北京时间今天）：

| 指标 | 值 |
|---|---|
| 工作日窗口 | 2026-06-08 → 2026-08-07（45 个工作日） |
| 成功日期数 | 41 |
| 空结果日期数 | 4（20260619=六月节美盘休市、20260703=独立日前休市、20260806、20260807=上游发布滞后） |
| 失败日期数（网络异常） | 0 |
| 本次新增行数 | 205（41 天 × 5 行/天） |
| 合并后总行数 | 205（首跑，幂等合并逻辑就绪） |
| 实际数据覆盖 | 2026-06-08 → 2026-08-05（最近数据滞后 2 天） |
| pulled_at | 2026-08-06T16:23:15+00:00（UTC，整窗统一时间戳） |

每日固定 5 行结构：`比特币-期货 / 比特币-期权 / 比特币-看涨(期权细分) / 比特币-看跌(期权细分) / 微型比特币-期货`。Schema：`date, 商品, 类型, 电子交易合约, 场内成交合约, 场外成交合约, 成交量, 未平仓合约, 持仓变化, source, pulled_at`；数值列已 `pd.to_numeric` 强制（场内成交合约常为 NaN，不虚构）。

最近 12 个交易日摘要（比特币期货 OI 单位=张）：

| date | MBTC期货OI | BTC期货OI | BTC持仓变化 |
|---|---|---|---|
| 2026-07-21 | 31118 | 20527 | +606 |
| 2026-07-22 | 30568 | 20384 | −143 |
| 2026-07-23 | 29505 | 19967 | −417 |
| 2026-07-24 | 28941 | 19938 | −29 |
| 2026-07-27 | 30263 | 20008 | +70 |
| 2026-07-28 | 31572 | 20019 | +11 |
| 2026-07-29 | 33091 | 20548 | +529 |
| 2026-07-30 | 37062 | 20951 | +403 |
| 2026-07-31 | 41694 | 21422 | +471 |
| 2026-08-03 | 20328 | 18990 | −2432 |
| 2026-08-04 | 21203 | 20143 | +1153 |
| 2026-08-05 | 23793 | 20679 | +536 |

（注意 2026-08-03 为 8 月首个交易日，持仓变化 −2432 系跨月滚动/仓位重建，非单日资金流出信号，解读时需结合交割日历。）

### 1.2 评估表

| 候选数据源 | URL/API | 获取方式 | 是否需要 key | 历史深度 | 更新频率 | 新鲜度契约风险 | 建议评级 |
|---|---|---|---|---|---|---|---|
| akshare `crypto_bitcoin_cme`（CME 官方结算数据转售） | https://akshare.akfamily.xyz/（接口 `ak.crypto_bitcoin_cme(date=YYYYMMDD)`） | Python 脚本逐日调用（本次 45 日实证） | 否 | 逐日可回溯（按日调参，历史深度取决于 CME 上架日 ≈ 2017-12 比特币期货） | 日频（交易日），周一至周五 | 中：上游滞后 1–2 自然日（2026-08-06/07 实测为空）；周末/节假日空；接口无批量参数需逐日循环 | **可用**（已实证） |

**研究用途（对应命题一环）**：「大饼见底→山寨蓄力」的**机构资金流**验证——① wash_cvd 事件前后 CME 期货/期权 OI 与持仓变化方向（机构是否在 washout 后加仓，与 120 的 VIX 调制交叉验证）；② CME 与币本位/币安 OI 的机构–散户背离度；③ 期权看涨/看跌持仓变化作为「蓄力」的机构情绪代理。注意 CME 数据只覆盖 BTC（微型=1/10 张），无山寨维度，定位为**宏观/机构情绪调制器**而非山寨信号本身。

**数据纪律要求**：
- 时间戳：`date`（交易日，北京时间自然日）+ `pulled_at`（UTC ISO，整窗统一）；
- 来源 URL：`source` 列固定 `akshare crypto_bitcoin_cme, https://akshare.akfamily.xyz/`；
- schema：上述 11 列固定，数值列强制 numeric，空值保留 NaN 不填充；
- 新鲜度门槛：研究接入时若 `max(date)` 距拉取日 > 3 个自然日 → 判定新鲜度违约并告警（容忍发布滞后）。

**T3 签批点**：**无**。一次性快照已由本任务完成。仅当 Owner 希望升级为**定时刷新**（进入 hermes 调度）时需签批——本脚本刻意未做定时化。

---

## 2. 稳定币供给（USDT/USDC 总供应）

| 候选数据源 | URL/API | 获取方式 | 是否需要 key | 历史深度 | 更新频率 | 新鲜度契约风险 | 建议评级 |
|---|---|---|---|---|---|---|---|
| DefiLlama Stablecoins（聚合总量） | `https://stablecoins.llama.fi/stablecoincharts/all?stablecoin=1`（实测 200，3173 个日点，2017-11-29 → 2026-08-06） | HTTP GET + 解析 JSON | 否（免费、无 key） | **深（≈8.7 年日频）** | 日频 | 低：24h 内更新；聚合口径含全部 USD 锚定币 | **可用**（实测连通） |
| DefiLlama Stablecoins（USDT/USDC 分列历史） | `https://stablecoins.llama.fi/stablecoincharts/1`（USDT id=1，USDC id=2，实测 404/空） | HTTP GET | 否 | 理论上有，实测端点不稳定 | 日频 | 中：端点行为漂移（404/空结果实测） | **待验证**（退化为聚合总量 + `stablecoins?includePrices=true` 当前构成快照） |
| Tether 官方透明度页 / USDC 官方 | tether.to / centre.io（手工/爬虫） | 爬取 | 否 | 长（官方报表） | 日频/月频 | 中：反爬风险，非结构化 | 待验证（仅作交叉校验，不主用） |

**研究用途**：命题「存储见顶→山寨蓄力」中**流动性弹药检验**——稳定币总供给的 30d 变化率领先山寨 24h 收益（蓄力期 = 弹药积累期）；与 wash_cvd 事件叠加检验「washout + 弹药增长」是否显著优于单独 washout。DefiLlama 免费 + 深历史，是本方向性价比最高的一类。

**数据纪律要求**：拉取时记录 `pulled_at`（UTC）+ 来源 URL 常量 `DefiLlama Stablecoins, https://stablecoins.llama.fi/`；schema 固定 `date(unix秒→UTC日), totalCirculatingUSD.peggedUSD`；新鲜度门槛 `max(date) ≥ 拉取日−2`；USDT/USDC 分列落地前一律用聚合总量，避免口径混用。

**T3 签批点**：无（免费源，无需签批）；若 Owner 要求 USDT/USDC **分列历史**且拒绝容忍聚合口径，则需外部资料确认 DefiLlama 正确端点或购买替代（T3 可选）。

---

## 3. BTC ETF 持仓 / 净流入

| 候选数据源 | URL/API | 获取方式 | 是否需要 key | 历史深度 | 更新频率 | 新鲜度契约风险 | 建议评级 |
|---|---|---|---|---|---|---|---|
| yfinance 单 ETF 日线（IBIT/BITB/FBTC/ARKB/HODL/BTCO/EZBC/BRRR/BTCW，9 只全现货） | `yf.download("IBIT", period=..., interval="1d")`（实测 5d OK，含 OHLCV 至 2026-08-06） | Python 脚本 | 否（免费） | 中（ETF 上市日以来，2024-01 起） | 日频（美盘收盘后） | 中低：盘后发布，T+1 早可拉全；yfinance 偶发限流需重试 | **可用**（价格/成交量代理维度，实测连通） |
| Farside 净流入表 | `https://farside.co.uk/btc/` | HTTP 抓取 | 订阅（Premium） | 深（2024-01 起） | 日频 | **高：实测 2026-08-07 返回 403 Cloudflare 反爬** | **需外部资料**（免费路径已封） |
| BlackRock 官方 IBIT 份额（shares outstanding） | ibit.btic.sh 官方持仓页 | 爬取/手工 | 否 | 上市以来 | 日频 | 中：HTML 解析脆弱 | 待验证（可作净流入的免费近似：份额变化 × NAV） |

**研究用途**：「大饼见底」的**机构需求确认**——ETF 净流入（或代理：成交量放大 + 份额变化）与 wash_cvd 触发后的 24–72h 反弹共现检验；IBIT 等价格序列可与币安现货价差构建「溢价/折价」情绪。诚实口径：**yfinance 只有价格/成交量，不是净流入**；净流入需份额数据（BlackRock 官方页可解析，或 farside 订阅）。

**数据纪律要求**：每只 ETF 记录 `ticker` + `pulled_at`（UTC）+ 来源 URL；schema 固定 `date, ticker, open, high, low, close, volume`；新鲜度门槛 `max(date) ≥ 拉取日−3`（跨周末放宽）；净流入若走 BlackRock 份额页，须固化解析断言（份额列存在才写库）。

**T3 签批点**：**需要**——若研究要求**真实净流入序列**（而非价格代理），Farside Premium 订阅或 BlackRock 份额爬虫的合规使用需 Owner 签批/提供凭证；yfinance 价格维度可立即做，无需签批。

---

## 4. 链上大户储备 / 交易所净流入

| 候选数据源 | URL/API | 获取方式 | 是否需要 key | 历史深度 | 更新频率 | 新鲜度契约风险 | 建议评级 |
|---|---|---|---|---|---|---|---|
| Glassnode 交易所余额/大户指标 | glassnode.com API | SDK/HTTP | **是（API key，免费层级受限）** | 深（2010s 起） | 日频/小时级 | 低（付费稳定性好） | **需外部资料**（免费层级配额低） |
| CryptoQuant 交易所净流入 | cryptoquant.com API | HTTP | **是（API key）** | 深（2017+） | 小时级 | 低 | **需外部资料** |
| blockchain.info charts API（原免费替代） | `https://api.blockchain.info/charts/exchange-balance` | HTTP | 否 | 深 | 日频 | **高：实测 2026-08-07 返回 404，端点已停用** | **需外部资料**（免费路径已死） |
| bitcointreasuries 上市公司持仓 | `https://api.bitcointreasuries.net/v1/treasuries` | HTTP | 否 | 中 | 不定期 | 高：实测 SSL 连接失败（本机网络环境） | 待验证 |
| 链上战壕类项目（Arkham 等） | arkhamintelligence.com | HTTP | 是（API key） | 中 | 实时 | 中 | 需外部资料 |

**研究用途**：命题**「存储见顶」验证的链上一环**——交易所 BTC 余额下降（流出自托管）→ 卖方压力枯竭 → 山寨蓄力的弹药前提；大户（矿工/巨鲸）流向作为 washout 底部的确认。**诚实结论**：该类是 5 类中免费可得性最差的一类——2026 年免费替代（blockchain.info API）已实测停用，仅剩付费/受限 API 与残破的替代品。

**数据纪律要求**：任何该维度接入都必须满足：来源 URL + 拉取时间戳 + 指标定义（余额=交易所可动用地址合计、净流入=转入−转出）三要素落库；新鲜度门槛小时级指标 ≤ 6h、日级 ≤ 2 天；跨源（Glassnode vs CryptoQuant）口径不同禁止混用，须锚定单一主源。

**T3 签批点**：**核心签批项**——Glassnode/CryptoQuant/Arkham 任选其一的 API key 或预算授权（Owner 提供外部资料），否则该维度**本阶段放弃**，不在 shadow 研究中编造代理。

---

## 5. 备选（值得接入，且不与 Binance 前向维度重复）

| 候选数据源 | URL/API | 获取方式 | 是否需要 key | 历史深度 | 更新频率 | 新鲜度契约风险 | 建议评级 |
|---|---|---|---|---|---|---|---|
| mempool.space 手续费/区块数据 | `https://mempool.space/api/v1/fees/recommended`（实测 200） | HTTP | 否（免费） | 中（2020s 起） | 实时/块级 | 低 | **可用**（实测连通，交易拥挤度代理） |
| CoinGecko 免费 API（市值） | `api.coingecko.com/api/v3/...` | HTTP | 否（限频 10–30/min） | 深 | 实时/日频 | 低 | **不重复接入**（107 已覆盖市值） |
| Binance klines/funding/OI 前向 | 本地 `binance_free_db` + `coinglass_db` | 本地 parquet | 无 | 深 | 1h | — | **不重复**（前向已有 101/107/113 等覆盖） |
| Dune（链上 SQL） | dune.com API | SQL | 是（API key） | 深 | 块级 | 中 | 需外部资料（若 Owner 已有 Dune key 可查交易所余额历史，但全历史要付费） |

**研究用途**：mempool.space 手续费 → 链上活跃度/拥挤度，作为「蓄力」的能量维度（牛市前夜往往手续费抬升）；Dune 若接入可部分填补 §4 的交易所净流入缺口（但历史需付费，诚实标注）。

**数据纪律要求**：mempool 拉取记录 `pulled_at`（UTC）+ 来源 URL；schema `ts, fastestFee, halfHourFee, hourFee, economyFee`；新鲜度门槛 ≤ 1h（属高频旁证，不进事件研究主链）。Dune 接入须先固化查询 SQL 版本号（query id）以便复现。

**T3 签批点**：mempool.space 无；Dune 若要走**历史交易所余额**查询（付费层）需 Owner 签批。

---

## 6. 结论：接入优先级（可得性 × 研究价值）

| 优先级 | 数据源 | 可得性 | 研究价值（命题环节） | 状态 |
|---|---|---|---|---|
| P0 | **CME 机构持仓**（akshare） | ✅ 已实证可用，45 日快照已落盘 | 机构资金流调制器（wash_cvd × 机构 OI 交叉验证） | **立即可用**，无需任何签批 |
| P1 | **稳定币供给**（DefiLlama 聚合） | ✅ 实测连通，免费无 key，8.7 年日频 | 「蓄力」流动性弹药检验（供给变化率领先山寨） | **可立即做**（写拉取脚本即可，无签批） |
| P2 | **BTC ETF 价格/成交量**（yfinance 9 只） | ✅ 实测连通，免费 | 「见底」机构需求确认（价格代理） | **可立即做**（代理维度） |
| P2' | BTC ETF **净流入**（份额/Farside） | ⚠️ farside 403 实测封禁；BlackRock 份额页可解析 | 同上（真实净流入） | **等 Owner 签批/资料**（T3） |
| P3 | **链上大户/交易所净流入**（Glassnode/CryptoQuant/Arkham） | ❌ 免费替代已死（blockchain.info 404 实测） | 「存储见顶」链上验证 | **等 Owner 提供 key/预算**（T3 核心签批项），否则本阶段放弃 |
| P3 | **mempool.space 手续费** | ✅ 实测连通 | 蓄力能量维度（旁证） | 可立即做（低优先级） |

### 可立即做（无签批）
1. **CME 机构持仓**（本任务已落地：`cme_bitcoin.parquet`，205 行 41 交易日）——下一步直接进事件研究：wash_cvd 事件日前后的 CME 持仓变化方向统计。
2. **稳定币供给拉取脚本**（DefiLlama 聚合总量，日频追加 parquet，对齐 117 的 merge 模式）。
3. **ETF 价格代理**（yfinance 9 只日线，日频追加）。

### 需 Owner 外部资料 / 签批（T3 清单）
- **T3-1**：BTC ETF **真实净流入**——Farside Premium 订阅凭证，或批准 BlackRock 官方份额页爬虫（合规边界确认）。
- **T3-2**：**链上交易所净流入**——Glassnode / CryptoQuant / Arkham 任一 API key 或预算授权（§4 为该维度唯一可行路径；免费替代 2026-08-07 实测不可用）。
- **T3-3**：CME 快照**定时化**升级（进入 hermes 调度）——本脚本按约定只做一次性快照；Owner 签批后才可加调度。
- **T3-4（可选）**：Dune 付费层历史交易所余额查询（若 Owner 已有 Dune key）。

**一句话结论**：CME（P0，已实证）与稳定币供给（P1，免费深历史）为当前**唯一可立即接入且与研究 edge 直接相关**的新数据；ETF 净流入与链上净流入受付费墙约束，列为 T3 签批项，签批前不做任何编造性代理。
