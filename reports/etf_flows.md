# BTC 现货 ETF 每日净流入免费实测

- 生成 UTC: 2026-08-07 05:41:34 UTC
- 方法: ① pandas.read_html 直抓（M1）；② requests+UA → lxml 解析静态表格（M2，主路径）；③ SoSoValue（M3）；④ TheBlock（M4）。抓取日志: etf_flows_fetch_log.json（每次尝试时间戳/状态码）
- 数据源: farside.co.uk 官网 `https://farside.co.uk/bitcoin-etf-flow-all-data/`（页面静态表格，全历史 2024-01-11 起，单位百万 USD）；另 `https://farside.co.uk/btc/` 仅最近约 2 周表（交叉核对用）。CSV: `C:\Users\10639\Desktop\🔒 加密资产\coinglass_db\macro\etf_flows_farside.csv`（含 source_url + fetched_utc 列）
- 收益口径: 113/115 同款（alt 等权篮子日收益，coinglass klines 至 2026-07-07）
> 目的：为山寨合约异动研究补充『机构资金流』免费数据维度，实测可用性（抓取稳定性/覆盖/滞后）并做两处关联检验（表2 相关、表3 wash_cvd 分层）。

## 1. 抓取实证（每方法成功/失败）

| 方法 | 目标 | 结果 | 证据 |
|---|---|---|---|
| M1 pandas.read_html | farside /btc/ | **OK** | rc=0; stderr:  |
| M2 requests+UA+lxml | farside all-data | **OK** | status=200; rows=660 2024-01-11→2026-08-06 |
| M3_sosovalue_www | https://www.sosovalue.com/ | 403 | len=5706 ctype=text/html; charset=UTF-8 |
| M3_sosovalue_api | https://api.sosovalue.com/ | FAIL SSLError | len=None ctype= |
| M4_theblock_cat | https://www.theblock.co/data/crypto-markets/bitcoin-etf | 200 | len=664212 ctype=text/html;charset=utf-8 |
| M4_theblock_flows | https://www.theblock.co/data/crypto-markets/bitcoin-etf/bitcoin-etf-flows | 404 | len=11764 ctype=text/html;charset=utf-8 |

> 注：M1 用独立子进程（urllib 抓取 + read_html 解析）隔离执行——实测本环境长驻进程里 `pd.read_html` 会挂死内核（连内存小表都挂，交互测试观测），但子进程内工作正常，gemini 调研的 read_html 路径实测可行；M2（requests+UA+lxml）为主路径，两者数据一致（同源静态表格）。

## 2. 数据覆盖实证（表1）

- 日期范围: **2024-01-11 → 2026-08-06**（660 个交易日，2024-01-11 ETF 上市日起全历史）
- 最新日期: 2026-08-06，相对今天（2026-08-07）**滞后 1 天**（farside 于次日晨发布前一日流量，T-1 为正常滞后）
- ETF 数量: 12 只（IBIT/FBTC/BITB/ARKB/BTCO/EZBC/BRRR/HODL/BTCW/MSBT/GBTC/BTC）+ Total 列；Total 缺失 0 行
- Total 日流量: mean=+79M USD，min=-1114，max=+1374

## 3. ETF 总净流入 × 日收益相关（表2）

> 流量当日晨发布 → 『当日』配对为描述性；『次日』= flow(t) vs 收益(t+1)，可交易、无前视。判定窗口至 2026-06-30（与 113/115 一致）。r=Pearson，括号内 n=配对日。

| era | n | 当日alt r | 当日btc r | 次日alt r | 次日btc r |
|---|---|---|---|---|---|
| 全期 2024-01→2026-06 | 634 | +0.258 (629) | +0.385 (629) | +0.017 (628) | +0.062 (628) |
| 2024 | 254 | +0.243 (254) | +0.357 (254) | -0.027 (254) | +0.015 (254) |
| 2025-26 | 380 | +0.268 (375) | +0.410 (375) | +0.038 (374) | +0.084 (374) |
| 2023平台蓄力 | 101 | +0.233 (101) | +0.325 (101) | +0.097 (101) | +0.045 (101) |
| 2024崩→恢复 | 174 | +0.284 (174) | +0.395 (174) | -0.106 (174) | -0.024 (174) |
| 2025顶→熊 | 356 | +0.251 (352) | +0.403 (352) | +0.056 (351) | +0.094 (351) |

## 4. wash_cvd 事件 × 事件日-1 ETF 净流入分层（表3）

> 检验『机构流入 → wash_cvd 后反弹更强』。特征 = 事件日 D-1 已发布流量（事件日晨可知，无前视）。事件窗口 2022-01-01→2026-06-30；ETF 数据 2024-01 起 → 事件 1348 个中 有流量 1005 个、24h 收益可得且可研究 1005 个。基线 = 同期随机 symbol×时点 n=2941，bootstrap 95% CI（seed=2026）。对照 115 pooled n=1348、24h超额 +1.31%。

| 层 | n | 24h均% | 24h超额% | 95% CI | 判定 |
|---|---|---|---|---|---|
| 流入(事件日-1流量>0) | 617 | +1.22 | +1.03 | [+0.27, +1.84] | **GO_LONG** |
| 流出(事件日-1流量≤0) | 388 | +1.19 | +1.00 | [+0.08, +2.08] | **GO_LONG** |
| 低分位 | 336 | +1.24 | +1.04 | [-0.04, +2.20] | **NO_GO** |
| 中分位 | 334 | +1.07 | +0.87 | [-0.02, +1.87] | **NO_GO** |
| 高分位 | 335 | +1.33 | +1.13 | [+0.14, +2.20] | **GO_LONG** |
| 高分位−低分位 | 335/336 | +0.09 | — | — | 描述性 |

## 5. 判定

### 5.1 免费 ETF 净流入路径可用性

- **可用（T3-1 免费解法）**：farside.co.uk 官网静态 HTML，`requests` 带浏览器 UA 即返回 200，lxml 解析即得全历史日频净流入（2024-01-11 → T-1，660 个交易日，12 只 ETF + Total）。单次请求约 2-4s，无限流迹象（本次连续多次请求均 200）。
- **read_html 路径亦可行（子进程隔离）**：gemini 调研的 `pd.read_html` 直抓路子实测成功（urllib 带 UA 抓取 → read_html 解析，rc=0）；注意 read_html 在长驻进程内可能挂死（本环境交互观测），脚本用子进程+超时隔离保证稳定；M2 的 requests+UA+lxml 为等价且更可控的主路径。
- **SoSoValue**：www 403（Cloudflare 'Just a moment'）、api.sosovalue.com DNS 不存在；浏览器 Network 实测无公开 json 接口（登录墙 privy.io，仅 walletconnect/GA/image-proxy 调用）→ 不可用。
- **TheBlock**：类别页 200 但是 JS SPA（数据不在静态 HTML）；flows 子页 404 / latest 403 → 无稳定免费端点。

### 5.2 关联结论

- 表2 全期 flow(t)→alt 次日收益: Pearson +0.017（无明显相关，描述性）
- 表3 流入/流出分层: 流入(事件日-1流量>0) n=617 超额 +1.03% [+0.27,+1.84]; 流出(事件日-1流量≤0) n=388 超额 +1.00% [+0.08,+2.08]; 低分位 n=336 超额 +1.04% [-0.04,+2.20]; 中分位 n=334 超额 +0.87% [-0.02,+1.87]; 高分位 n=335 超额 +1.13% [+0.14,+2.20]
- 判定口径：CI 下界>0 → GO_LONG；上界<0 → GO_SHORT；含 0 → NO_GO；n<30 → 样本不足。
- **表3 调制判定：流入−流出 24h 超额差 +0.03pp（含 CI 重叠），高分位−低分位 +0.09pp → ETF 净流入对 wash_cvd 24h 反弹无有效调制**（与 128 dStable 无调制结论方向一致；两组超额本身仍为正，即 wash_cvd 基线效应主导）。

### 局限

- 流量为工作日发布，周末/节假日缺失；『次日』配对用交易日对齐（flow 上周五 vs 本周一收益也算次日）。
- farside 为自发统计（FCA 注册机构），与官方 13F 有口径差；Total 以其页面为准，未做他源复核。
- 相关检验为描述性、无多重检验校正；wash_cvd 事件侧 2024 前无 ETF 流量（样本天然截断）。
- 分位断点取事件样本 flow_prev 的三分位（分层定义用）；事件日-1 流量取值无前视（严格取 < 事件日的最近流量）。