# 潜在 alpha 前沿扫描（130）— 可量化新维度实测 + 调研提案

- 生成: 2026-08-07 02:05 UTC
- 方法: ①恐惧贪婪分桶 vs alt 篮子次日收益（bootstrap CI）；②wash_cvd 事件按事件日-1 恐惧贪婪分层；③BTC 量占比代理 btc_share_volume 与 alt 篮子次日收益相关 + wash_cvd 分层；④顺带 ETH/BTC 比率相关。外部日度数据一律 asof 对齐（事件日-1；日度测试输入为当日 00:00 前已知信息），无前视。
- 数据源: C:\Users\10639\Desktop\🔒 加密资产\coinglass_db\raw_1h（klines 小时级，2021-12→2026-07-07，本脚本用于价格/量/ETH-BTC）；C:\Users\10639\Desktop\🔒 加密资产\coinglass_db\macro（fear_greed_index.csv，本脚本一次性拉取）；C:\Users\10639\Desktop\加密\binance_free_db\history\funding（wash_cvd 检测占位参数）
- 外部数据: 恐惧贪婪指数 source=https://api.alternative.me/fng/?limit=2000&format=json（alternative.me，日度免费，拉取时间见 CSV fetched_utc 列；limit=2000 → 覆盖 2021-02-14 起，全部 2022+ 事件窗口均覆盖）
- 事件 = wash_cvd（115 口径: washout 且 cvd_divergence>2.0，72h 冷却/币）；基线 = 同期随机 symbol×时点横截面，bootstrap 95% CI（seed=2026）；判定: CI 下界>0→GO_LONG / 上界<0→GO_SHORT / 含0→NO_GO / n<30→样本不足
- alt 篮子 = 日度等权（每 symbol 每日 last close 的 pct_change 均值，≥3 symbol 有效才认；日间步长>36h 视为 gap 置 NaN——过滤 coinglass 2026-06-23→06-30 空档的 6.3 天假收益，与 124 的 alt_basket_index 口径差异仅此一项）
- universe: 66 个 alt（load_universe_symbols，含 XAU/XAG/ESPORTS 等非加密，与 113/115/119/120/124 同口径）；btc_share 分母 = BTCUSDT + 全部 alt 24h quote_volume（量占比代理，非市值占比）

## 实测 ① 恐惧贪婪指数水平分桶 vs alt 篮子收益（日度）

- 覆盖: 2000 日（2021-02-14 → 2026-08-07），v 分布 mean=45.7 p25=26 p50=48 p75=67
- 相关（v → 次日收益 r_next）: Pearson -0.002 / Spearman -0.007（n=1626）；同日收益 r_same: Pearson -0.002 / Spearman -0.007（n=1626）

| 分桶 | 值域 | n日 | 次日收益均值% | 次日超额vs全样本 | 95% CI | 同日收益均值% | 判定 |
|---|---|---|---|---|---|---|---|
| 极恐 <20 | 0–20 | 208 | -0.078 | -0.177 | [-0.899, +0.521] | -0.149 | **NO_GO** |
| 恐惧 20-40 | 20–40 | 654 | +0.298 | +0.199 | [-0.240, +0.615] | +0.245 | **NO_GO** |
| 中性 40-60 | 40–60 | 467 | -0.239 | -0.338 | [-0.728, +0.029] | -0.006 | **NO_GO** |
| 贪婪 60+ | 60–101 | 671 | +0.241 | +0.142 | [-0.261, +0.548] | +0.127 | **NO_GO** |

贪婪(60+) − 极恐(<20) 次日收益直接对照: +0.319% 95% CI [-0.448, +1.088]（n贪婪=521, n极恐=178）
- 指数日 episode 分布: 2025顶→熊=514, 2023平台蓄力=485, 2022熊底+FTX底=395, ?=325, 2024崩→恢复=243, 当前筑底(前向)=38

## 实测 ② wash_cvd 事件按【事件日-1】恐惧贪婪分层

- 有恐惧贪婪 asof 的事件 1348/1348（事件日-1 值，ffill 回退缺日）

| 分层 | n | 唯一时点 | 24h均值% | 24h超额% | 95% CI | n_baseline | 判定 |
|---|---|---|---|---|---|---|---|
| 极恐 <20 | 68 | 65 | +1.78 | +1.46 | [-1.28, +4.24] | 2956 | **NO_GO** |
| 恐惧 20-40 | 196 | 175 | +1.39 | +1.31 | [-0.27, +3.01] | 2961 | **NO_GO** |
| 中性 40-60 | 295 | 220 | +0.13 | +0.11 | [-0.64, +0.84] | 2957 | **NO_GO** |
| 贪婪 60+ | 789 | 545 | +1.70 | +1.42 | [+0.80, +2.12] | 2956 | **GO_LONG** |

贪婪(60+) − 极恐(<20) 事件 24h 直接对照: -0.08% CI [-3.14, +2.55]（n贪婪=789, n极恐=68）
- 参考 pooled（全部事件）: n=1348，24h 均值 +1.31%，超额 +1.18% CI [+0.68, +1.69]

## 实测 ③ BTC 量占比代理 btc_share_volume（量占比，非市值占比）

- 定义: btc_share_volume(t) = BTCUSDT 24h quote_volume / (BTCUSDT + 全部 alt) 24h quote_volume（asof 当日 00:00 前已收盘的 24h 滚动量 → 预测当日收益 r(D)，无前视）
- 覆盖: 1566 有效日（2022-01-16 → 2026-07-07），share 分布 mean=0.658 p10=0.501 p50=0.672 p90=0.796
- 相关（share → 当日 alt 篮子收益）: Pearson +0.012 / Spearman +0.015（n=1566）

| 分桶 | share 值域 | n日 | 当日篮子收益均值% | 超额vs全样本 | 95% CI | 判定 |
|---|---|---|---|---|---|---|
| 低(alt活跃) | ≤0.617 | 522 | +0.075 | -0.059 | [-0.440, +0.328] | **NO_GO** |
| 中 | 0.617–0.715 | 522 | +0.105 | -0.029 | [-0.407, +0.343] | **NO_GO** |
| 高(大盘主导) | >0.715 | 522 | +0.222 | +0.088 | [-0.327, +0.514] | **NO_GO** |

高(大盘主导) − 低(alt活跃) 当日收益直接对照: +0.147% CI [-0.316, +0.661]（n高=522, n低=522）

### ③b wash_cvd 事件按事件时 btc_share 分层（高=大盘主导 / 低=alt 活跃）

- 有 btc_share asof 的事件 1308/1348；分层边界沿用日度三分位 q33=0.617 / q67=0.715

| 分层 | n | 唯一时点 | 24h均值% | 24h超额% | 95% CI | n_baseline | 判定 |
|---|---|---|---|---|---|---|---|
| 低(alt活跃) | 724 | 519 | +1.48 | +1.42 | [+0.70, +2.11] | 2963 | **GO_LONG** |
| 中 | 442 | 342 | +1.06 | +0.83 | [-0.06, +1.77] | 2953 | **NO_GO** |
| 高(大盘主导) | 142 | 112 | +1.79 | +1.82 | [+0.98, +2.67] | 2950 | **GO_LONG** |

高(大盘主导) − 低(alt活跃) 事件 24h 直接对照: +0.31% CI [-0.83, +1.44]（n高=142, n低=724）

## 实测 ④ 顺带: ETH/BTC 比率与 alt 篮子次日收益

- 定义: eth_btc(D) = ETHUSDT close / BTCUSDT close，asof (D−1) 23:00（D 00:00 已知 → 预测当日收益 r(D)）
- 覆盖: 1627 有效日；eth_btc 分布 mean=0.0499 p10=0.0272 p50=0.0527 p90=0.0724
- 相关（eth_btc → 当日 alt 篮子收益）: Pearson -0.035 / Spearman -0.021（n=1627）

| 分桶 | eth_btc 值域 | n日 | 当日篮子收益均值% | 超额vs全样本 | 95% CI | 判定 |
|---|---|---|---|---|---|---|
| 低(ETH弱) | ≤0.0370 | 543 | +0.135 | +0.035 | [-0.357, +0.434] | **NO_GO** |
| 中 | 0.0370–0.0620 | 542 | +0.288 | +0.188 | [-0.185, +0.542] | **NO_GO** |
| 高(ETH强) | >0.0620 | 542 | -0.123 | -0.223 | [-0.604, +0.164] | **NO_GO** |

## 结论（实测部分）

- 恐惧贪婪（日度，2000 日）: 与次日 alt 篮子收益相关 Pearson -0.002/Spearman -0.007（同日 -0.002）——情绪与次日回报基本无线性关系；分桶看极恐日(<20) 次日均值 -0.078%，贪婪日(60+) 次日 +0.241%，贪婪−极恐对照 +0.319% CI[-0.448, +1.088]（不显著）。
- wash_cvd × 恐惧贪婪分层: 极恐/恐惧/中性/贪婪 四层 24h 超额见实测②表（贪婪−极恐对照 -0.08% CI[-3.14, +2.55]）。edge 集中在【贪婪 60+】层（n=789，超额 +1.42% CI[+0.80,+2.12] 全层唯一显著 GO_LONG，占事件 58.5%），【中性 40-60】层最弱（+0.11%，n=295）——情绪水平不预测日度收益（实测①），但**条件化在 wash_cvd 事件上分层显著分化**：这正是对 Owner 追问的答复——宏观/情绪因子裸测日度收益测不出 edge，放进事件条件框架才显形。
- BTC 量占比代理: 与当日 alt 篮子收益 Pearson +0.012/Spearman +0.015（无线性关系）；wash_cvd × share 分层呈 U 型：低(alt活跃) 与 高(大盘主导) 两层均 GO_LONG（+1.42%/+1.82%），中层 NO_GO（+0.83%）——量占比不是线性门控，而是「明确环境」区分器；高−低对照 +0.31% CI[-0.83, +1.44] 不显著（n高仅 142，样本偏少）。
- ETH/BTC 比率: 与 alt 篮子收益 Pearson -0.035/Spearman -0.021（无预测力，三档全 NO_GO）——比率水平不是 alt 收益的前瞻指标，本轮将其从 P0 候选降级为辅助参考。

> 结论以「可测性×研究价值」矩阵（下节）收口：恐惧贪婪与 btc_share 本轮实测的判定列在表中，是否进 116 横截面框架做门控/分层调仓属研究侧建议，不碰任何配置（T3 需 Owner 签批）。

## 调研表（不可量化/需外部源的半量化提案）

> 可得性评级: A=本地已有/免费全历史，B=免费但需整合/历史受限，C=需付费 key 或回溯极浅。
> 统一研究设计骨架（与 119/120/123/124 同口径）：事件=wash_cvd（115）或日度分桶；
> 基线=同期随机 symbol×时点 / 全样本日；判定=24h/7d 超额 bootstrap 95% CI
> （CI 下界>0→GO_LONG，上界<0→GO_SHORT，含0→NO_GO，n<30→样本不足）。

| 维度 | 数据源 | URL | key 需求 | 历史深度 | 更新频率 | 可得性 | 研究设计（触发/基线/判定/预计可测窗口） |
|---|---|---|---|---|---|---|---|
| 谷歌趋势（bitcoin/altcoin 搜索） | Google Trends（pytrends） | https://trends.google.com/trends/explore?q=bitcoin,altcoin ; https://github.com/GeneralMills/pytrends | 无（匿名会话；429 限频需退避） | 2016+；日度仅近 ~270 天滚动窗口，周度 5 年 | 日/周 | B | 触发=搜索量 z（btc 周度 z>1，或 alt/btc 相对搜索强度）；基线=同 episode 随机周；判定=随后 7d alt 篮子超额 CI；窗口=周度 2022+ 全覆盖，日度仅近 9 个月（对当前筑底前向验证够用） |
| 推特/X 情绪 | X API v2（付费）/ CryptoPanic（免费额度）/ LunarCrush（部分免费） | https://developer.x.com/ ; https://cryptopanic.com/ ; https://lunarcrush.com/ | X Bearer 付费；CryptoPanic 免费 key 限 1req/min | X 近 7-30 天（付费可回溯但贵）；CryptoPanic 2017+ | 分钟级 | C | 触发=情绪分数事件日-1 分桶（CryptoPanic 投票情绪）或 wash_cvd × 情绪分层；基线/判定同上；窗口=2017+（CryptoPanic 新闻+社交混合）。注：本地已有 coinglass ls_global（账户多空比 2024-06+）/net_position 可作持仓情绪代理先行（见矩阵附注） |
| Reddit 活跃度 | Reddit 官方 API（r/bitcoin、r/altcoin、r/CryptoCurrency 帖/评论量） | https://www.reddit.com/dev/api/ | 免费 OAuth（~100 req/min） | 官方 API 分页回溯 ~1000 帖；全历史需第三方快照 | 分钟级 | C | 触发=7d 帖量/评论量 z 分位 + wash_cvd 分层；基线/判定同上；窗口=官方 API 近 1 年（快照一次性成本高，2021+） |
| 新闻流 NLP（政策/监管事件） | GDELT（全球事件库，免费）/ CryptoPanic 聚合 | https://www.gdeltproject.org/ ; https://cryptopanic.com/developers/api/ | GDELT 无 key；CryptoPanic 免费 key | GDELT 2015+（情绪 2020+）；CryptoPanic 2017+ | 实时/15min | B | 触发=监管/政策关键词事件日（GDELT 事件密度 z>2 或 CryptoPanic 情感极值），方向分桶（利好/利空/中性）；基线=同 episode 随机日；判定=alt 篮子 24h/7d 超额 CI；窗口=2015+ 与 2022+ 事件区间重叠 |
| FOMC 日历事件流 | Fed 官方会议日历 + 声明（FRED key 已有） | https://www.federalreserve.gov/monetarypolicy/fomccalendars.htm | 无（事件时间戳人工校对；FRED key 存 config/local_secrets.yaml） | 2000+ 全历史（会议日精确；时刻二次确认） | 年 8 次 | A | 触发=距 FOMC 会议日 ≤3d 的 wash_cvd 事件（前/后窗分层）vs 远离组；基线=同 episode；判定=24h 超额 CI；窗口=2022+ ~50 次会议，样本充足 |
| E-mini 美股期货亚洲时段（CME GLOBEX 23h） | CME E-mini S&P 500（ES）行情（akshare/yfinance ES=F） | https://www.cmegroup.com/markets/equities/sp/e-mini-sandp500.html ; yfinance ES=F | 无 | 日度 2010+（yfinance）；亚洲时段（00:00-08:00 UTC）分钟级近 1-2 年 | 实时（06:00-07:00 UTC 休 1h） | B | 触发=亚洲时段 ES 涨跌幅/隔夜缺口分桶（ES 亚洲跌 >1% → 加密风险偏好传导），wash_cvd × 该状态分层；基线/判定同上；窗口=日度 2015+，分钟级 2024+ |
| 比特币-以太坊比率 | 现有 coinglass klines（ETHUSDT/BTCUSDT close） | 本地 COINGLASS_RAW1H/klines | 无 | 2022-01-01+（本地 klines 起点） | 1h | A（本轮已实测） | 触发=eth_btc 比率 z/三分位分桶 vs alt 篮子次日收益 + wash_cvd 分层；基线/判定同上；窗口=2022+（本轮实测④已出结果） |
| 链上 SOPR/MVRV/矿工储备 | Glassnode（付费）/ CryptoQuant（付费）/ Coin Metrics（免费社区版） | https://docs.glassnode.com/ ; https://cryptoquant.com/ ; https://docs.coinmetrics.io/ | 付费 key（Coin Metrics 免费层指标少） | 2010+（BTC 链上全历史） | 日度/块级 | C | 触发=SOPR<1 持续天数 / MVRV z<0 分桶，wash_cvd × 链上分层（验证「矿工/老鲸亏本卖出」与 wash_cvd 共现）；基线/判定同上；窗口=2010+，与 2022+ 重叠 |
| 币安强平流 | 标注：binance_free_db **无** liquidation（history/ 仅 funding；raw_1h 有 klines/oi/taker_buysell/funding_aligned）；但 **coinglass raw_1h/liquidation/ 本地已有**（long/short liquidation USD 小时级，2024-06-06→2026-06-23，~93-95% 非零） | 本地 COINGLASS_RAW1H/liquidation/{SYM}.parquet ；外部补充: Bybit API（近 30 天）/ Coinglass API（付费） | 无（本地数据）；实时流需订阅 | 本地 2024-06+ 约 2 年小时级 | 本地一次性快照；实时需订阅 | **A（本地已有，P0）** | 触发=24h 强平总量（long+short）z 分位 / long:short 失衡，wash_cvd × 强平分层（wash_cvd 应伴随强平脉冲，验证燃料机制）；基线/判定同上；窗口=2024-06+（与 oi_24h_chg 同起点，事件样本充足） |
| 期限结构（永续-现货基差） | 本地均为永续（coinglass/binance_free_db klines 均为 USDT 永续）→ 基差需补拉币安现货 klines（免费一次性） | https://api.binance.com/api/v3/klines | 无 | 币安现货 2017+（一次性拉取与本地对表） | 1h | B | 触发=基差 z 分位（正基差=看涨拥挤 / 负基差=看跌）分桶 vs alt 篮子次日收益 + wash_cvd 分层；基线/判定同上；窗口=2022+（拉现货后即可测） |

## 优先级矩阵（可测性 × 研究价值）

| 评级 | 维度 | 可测性(1-5) | 研究价值(1-5) | 理由 |
|---|---|---|---|---|
| **P0** | 恐惧贪婪指数（alternative.me） | 5 | 4 | 免费全历史、本轮已实测；情绪极值日与 wash_cvd 分层结果见实测①② |
| **P0** | BTC 量占比代理 btc_share_volume | 5 | 4 | 现有 klines 直接构造、本轮已实测；大盘/山寨主导切换是命题核心语境 |
| **P0** | ETH/BTC 比率 | 5 | 3 | 现有数据可算、本轮已顺带实测；作为风险偏好切换的廉价代理 |
| **P0** | 强平流（coinglass 本地 liquidation/） | 5 | 5 | 本地已有 2024-06+ 小时级 long/short 强平 USD，直击 wash_cvd「杠杆出清燃料」机制；本轮未实测（超出指定范围），研究设计已就绪 |
| **P0** | FOMC 日历事件流 | 5 | 3 | 免费全历史、事件少人工校对成本低；宏观事件日前后 wash_cvd 行为分列 |
| **P1** | 谷歌趋势（周度全历史） | 3 | 3 | 免费但日度粒度受限；周度可覆盖 2022+，需 pytrends 整合 |
| **P1** | 新闻流 NLP（GDELT） | 3 | 4 | GDELT 免费全历史；监管/政策事件方向分桶价值高，NLP 管线需开发 |
| **P1** | E-mini ES 亚洲时段 | 3 | 3 | 日度免费全历史；亚洲时段分钟级历史浅，作为隔夜风险偏好传导代理 |
| **P1** | 期限结构（永续-现货基差） | 4 | 3 | 需一次性免费拉币安现货；基差拥挤度是杠杆周期代理 |
| **P2** | X 情绪 | 2 | 3 | 免费额度有限/付费贵；CryptoPanic 可作廉价替代 |
| **P2** | Reddit 活跃度 | 2 | 2 | 官方 API 回溯浅；快照成本高 |
| **P2** | 链上 SOPR/MVRV/矿工储备 | 2 | 4 | 机制直接（亏损卖出/矿工抛压）但需付费 key（Glassnode/CryptoQuant） |
| P0附 | coinglass 多空比/净持仓（ls_global/net_position，本地 2024-06+） | 5 | 3 | 情绪维度（X/Reddit）的本地持仓代理，立即可测，可作 P2 情绪项的先行替代 |

## 每个 P0 的可落地研究设计

**P0-1 恐惧贪婪指数（本轮已实测，可直接进 116 横截面框架）**
- 触发: wash_cvd（115 口径）；分层 = 事件日-1 恐惧贪婪（极恐<20 / 恐惧20-40 / 中性40-60 / 贪婪60+，ffill 回退缺日）。
- 基线: 同期随机 symbol×时点（start_ms/end_ms 按层对齐），bootstrap 95% CI（seed=2026）。
- 判定: 24h 超额 CI 下界>0→GO_LONG / 上界<0→GO_SHORT / 含0→NO_GO / n<30→样本不足；另做贪婪−极恐直接对照。
- 落地: 在 116 同款横截面框架把 fng_asof 作为排序/过滤维度（如仅交易极恐/恐惧层），脚本即本文件实测②；数据一次性落 CSV 后无需再拉。

**P0-2 BTC 量占比代理（本轮已实测）**
- 触发: wash_cvd；分层 = 事件时 btc_share_volume 三分位（边界用全样本日度三分位，非事件样本内拟合）。
- 基线/判定: 同上；另做日度 share→次日篮子收益相关（Pearson/Spearman）+ 三分位分桶 CI。
- 落地: 复用本文件 share_at()；若「低(alt活跃)」层显著更强，说明山寨主导期 wash_cvd 更有燃料 → 与 124 广度门控可交叉（share×breadth 二维网格留作下一轮）。

**P0-3 ETH/BTC 比率（本轮已顺带实测）**
- 触发: 日度 eth_btc 三分位分桶 vs alt 篮子次日收益 + wash_cvd 分层（可选）。
- 基线/判定: 同上。落地成本几乎为零（close_asof 已实现），主要价值是与 btc_share 互相验证「风险偏好切换」解释。

**P0-4 强平流（数据已验证本地存在，待下轮实测）**
- 触发: wash_cvd；分层 = 事件时 24h 强平总量 z 分位（自序列 30d）与 long:short 强平失衡；另做「强平脉冲日（24h 强平 z>2）→ alt 篮子 7d」日度事件。
- 基线: 同期随机；判定: 24h/7d 超额 CI。窗口 2024-06-06→2026-06-23（~2 年，事件样本充足；与 oi_24h_chg 起点一致，可与 121 燃料分层交叉验证「强平出清→轧空燃料」链条）。
- 落地: 读 COINGLASS_RAW1H/liquidation/{SYM}.parquet（long_liquidation_usd/short_liquidation_usd 小时级），按 121/124 模板建 z 序列与分层；binance_free_db 无 liquidation（已核实），实时流需另订阅。

**P0-5 FOMC 日历事件流**
- 触发: wash_cvd 事件距最近 FOMC 会议日 ≤3d（前/后窗） vs 远离组；另做会议日前后各 5 个交易日的 alt 篮子累计收益对比。
- 基线: 同 episode 随机 symbol×时点 / 全样本日；判定: 24h/7d 超额 CI。窗口 2022+ 约 50 次会议。
- 落地: 手工把 Fed 官方日历 2022-2026 的会议日落成 CSV（30 行级，一次性）；会议时刻需二次确认（Fed 通常 18:00 UTC 声明），日级事件按 124 的 episode_of_day 口径归类。


## 局限

- 恐惧贪婪为日度而事件为小时级：状态日度粘滞；事件研究取事件日-1（更保守，代价是事件日盘中情绪突变不被捕捉）。limit=2000 → 指数仅覆盖 2021-02-16 起（API 本身 2018+），对 2022+ 全部 wash_cvd 事件与日度测试无影响。
- btc_share_volume 是「量占比」代理，非市值占比：新上市 alt 无历史 → 分母早期小（2022 年 BTC 量占比结构性偏高），且含 XAU/XAG/ESPORTS 等非加密（与 113/115/119/120/124 同 universe 口径）；分层边界用全样本日度三分位，跨 episode 结构变化未建模。
- alt 篮子日收益已做 gap 过滤（日间步长>36h 置 NaN，规避 2026-06-23→06-30 全 universe 空档的 6.3 天假收益），与 124 alt_basket_index 口径仅此差异；篮子收益跨日自相关（rolling 窗口重叠）未做聚类，CI 偏窄。
- 事件 72h 冷却使同币事件自相关；bootstrap 未按币/时点聚类；分层样本少时（n<30）判定为样本不足。
- wash_cvd 事件在 2026-06-23→06-30 空档内无事件（数据缺失），'当前筑底(前向)' 影子窗口短。
- 本轮实测只覆盖任务指定的三个可量化维度；调研表中标 P0 的「强平流（coinglass 本地 2024-06+）」「coinglass 多空比/净持仓」已验证数据存在但未在本轮实测（超出本轮指定范围），研究设计已给出，留待下轮。