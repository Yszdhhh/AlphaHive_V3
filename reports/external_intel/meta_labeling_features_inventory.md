# Meta-Labeling 特征字段级清单

- 生成：2026-08-08 UTC
- 性质：字段级特征清单（对应 `meta_labeling_plan.md` §3.2 特征集，零新数据源）
- 配套：`meta_labeling_purgedcv_blueprint.md`（purged CV 实现）
- 口径：事件 = wash_cvd（115 口径，n=1348，2022-01→2026-06，72h 冷却）；标签 y = 1[r168 − 54bps > 0]
- 缺失率：**实测值**（2026-08-08 对 1348 事件逐一 asof 计算，非估计）

---

## 1. 总表（10 特征组 → 确切列名）

| 组 | 特征列（推荐） | 来源脚本/函数 | asof 方式 | 实测缺失率 | 注意点 |
|---|---|---|---|---|---|
| ① 信号强度 | `price_z` | 113 `load_price_ctx`（ctx 列） | searchsorted 事件 ts | **0/1348 (0%)** | 30d=720h 自序列滚动 z，min_periods=360 |
| ① 信号强度 | `ret_24h` | 113 `load_price_ctx`（ctx 列） | 同上 | **0/1348 (0%)** | pct_change(24)×100 |
| ① 信号强度 | `cvd_divergence` | 113 `load_price_ctx`（ctx 列） | 同上 | **0/1348 (0%)** | = price_z − cvd_z；cvd_z = cumsum(2·taker_buy_qv − qv) 的 720h z |
| ① 信号强度 | `oi_24h_chg` | 113 `load_price_ctx`（ctx 列，oi_ohlc） | 同上 | **487/1348 (36.1%)** | 仅 oi_ohlc 窗口（2024-06→2026-05）；窗口外 NaN，建议作为受限特征或丢弃 |
| ② 确认信息 | `r4` | 148/157/160 事件循环（`close[pos+4]/close[pos]−1`） | **事件后 4h 才可得** | 近数据末端事件缺（事件池已要求 pos+168 存在 → 实际 ~0%） | 主口径下作特征；预注册：标签仍锚定事件 ts（见 blueprint §1） |
| ③ 时间锚 | `age_days` | 157 `listing_dates()` + 事件 ts | 事件 ts − listing_ms | **0/1348 (0%)** | listing = klines `open_time` 最小值 |
| ③ 时间锚 | `is_new90` | 157（`age_days < 90`） | 同 age_days | **0/1348 (0%)** | 新币期 135/1348 = **10.0%** |
| ④ 容量锚 | `liq24` | 160（klines `quote_volume` rolling 24 求和） | searchsorted 事件 ts | **0/1348 (0%)** | 建议同时给 `log1p(liq24)` 与 s010 分层哑变量 |
| ⑤ 周期 | `mayer` | 164 `btc_cycle()`（日线 close/ma200） | 事件日 map（日线） | **38/1348 (2.8%)** | 2022 初 ma200 预热期缺 |
| ⑤ 周期 | `cycle_z` | 164 `btc_cycle()`（log 价全期回归残差 z） | 同上 | **38/1348 (2.8%)** | ⚠️ **169 已警告：全期拟合是统计口径，交易口径必须滚动重算**；见 §7 处理建议 |
| ⑤ 周期 | `regime` | 108/`regime_engine.assign_regime`（btc_recovery/risk_off/default） | searchsorted asof BTC+SP500 | 可算，~100%（SP500 至 2026-08-06） | 依赖 BTC 20d 回撤/5d MA + SP500 50d MA；SP500 停更时降级 |
| ⑥ 大户行为 | `div` | 161 `add_positioning`（`ls_top_trader.top_position_long_percent − ls_global.global_account_long_percent`） | searchsorted 事件 ts（attach_asof） | **487/1348 (36.1%)** | 数据窗 2024-06-06→2026-05-26，只覆盖 864 事件；窗口内 ~100% |
| ⑥ 大户行为 | `np_z` | 161 `add_positioning`（`net_position_change_cum` 的 `rolling_z(720)`） | 同上 | **500/1348 (37.1%)** | 同窗口 + 30d 滚动预热期（窗口内 98.1%）；**必须滚动口径** |
| ⑦ 成交结构 | `imb_24h` | raw `taker_buysell/`（`(buy−sell)/(buy+sell)` rolling 24） | searchsorted 事件 ts | **487/1348 (36.1%)** | 数据窗 2024-06-06→2026-05-27；与 151 的 `imb_24h`（klines 口径）不同源，二选一预注册 |
| ⑦ 成交结构 | `imb_norm` | 151 `build_imbalance_ctx`（imb 的 720h min-max 归一） | 同上 | 同上 | 151 是 washout 外的独立事件流；作为特征时按 151 公式从 klines 算 |
| ⑧ 上市形态 | `pump_gain` | 160（上市以来 `close[:i+1]` max/min − 1） | 事件 ts 截断（**只用 ≤ 事件时点**） | **0/1348 (0%)** | 160 用 `close[:i+1]` 无前视；`pump = pump_gain > 300` |
| ⑨ 市场环境 | `vix_close` | 108 `load_vix_state`/120 `load_macro_series("VIX")`（FRED VIXCLS 日线） | **asof 日−1 searchsorted**（108 `vix_gate_state`） | **0/1348 (0%)**（searchsorted 口径） | 同日 map 会因周末/假日缺 355 个（80.3%）——必须 searchsorted asof |
| ⑨ 市场环境 | `vix_low`/`vix_high` | 120 `build_state_frame`（1y 滚动 75 分位） | 同上 | ~0% | 动态滚动分位，非全样本分位 |
| ⑨ 市场环境 | `breadth_pct`/`breadth_z` | 124 `build_grid`+`build_breadth_series`+`attach_breadth`（6h 网格） | searchsorted 取事件前最近 6h 网格点 | **0/1348 (0%)** | n_active≥5 才有效；2022 粒度粗（n≈18） |
| ⑨ 市场环境 | `fear_greed` | 130/132（`macro/fear_greed_index.csv`，alternative.me 日度 0-100） | 事件日 map（建议日−1，132 口径） | **1/1348 (0.07%)** | 覆盖 2021-02→2026-08-07，全窗口可算 |
| ⑩ 波动率 | `vol_24h` | 02/07 口径：小时收益 `rolling(24).std()`（ctx close 可算） | searchsorted 事件 ts | **0/1348 (0%)** | 与 `atr24 = rolling(24).max − min` 二选一；vol-target 相关 |
| （备选）| `market_cap_usd` / `oi_to_mc_ratio` | 108 流 / `market_cap_provider` | 事件 ts | 108 流内可查 | 容量锚补充，非 §3.2 必需 |

> 窗口外特征（oi_24h_chg / div / np_z / imb_24h）**不是均匀缺失**：全部集中在 2024-06 之前 + 2026-06 尾部 → 弃行会系统性丢掉 2022-2023 样本（320 事件）与最新语境。建议：**主口径不含窗口特征**（n=1348 全用），窗口特征单独跑"2024-06 后子口径"（n≈900）作对照——两个口径各自 pre-register。

---

## 2. 数据源与 schema

```
COINGLASS_RAW1H = C:\Users\10639\Desktop\🔒 加密资产\coinglass_db\raw_1h
├─ klines/{sym}.parquet          open_time, close, quote_volume, taker_buy_quote_volume   (124 币)
├─ oi_ohlc/{sym}.parquet         time, open, high, low, close                            (2024-06→2026-05, 66 币)
├─ ls_top_trader/{sym}.parquet   time, top_position_long_percent, top_position_short_percent, top_position_long_short_ratio  (2024-06-06→2026-05-26, 66 币)
├─ ls_global/{sym}.parquet       time, global_account_long_percent                        (同窗, 66 币)
├─ net_position/{sym}.parquet    time, net_long_change, net_short_change, net_long_change_cum, net_short_change_cum, net_position_change_cum  (2024-06-07→2026-05-28, 66 币)
├─ taker_buysell/{sym}.parquet   time, taker_buy_volume_usd, taker_sell_volume_usd       (2024-06-06→2026-05-27, 66 币)
├─ liquidation/{sym}.parquet     time, long_liquidation_usd, short_liquidation_usd       (备选，liq_short_z 见 131)
└─ macro/
   ├─ VIX.parquet                1990-01→2026-08-06（FRED VIXCLS，118 拉取）
   ├─ VIX_SYNTH.parquet          2004-01→2026-06-26（合成备用；VIX.parquet 覆盖更全 → 优先 VIX）
   ├─ SP500.parquet              2004-01→2026-08-06
   ├─ fear_greed_index.csv       date, value, value_classification, source_url, fetched_utc（2021-02→2026-08-07，2000 行）
   └─ (DOLLAR/GOLD/TREASURY/CPI 等 120 流，如需 regime 扩展)

FUNDING_DIR = C:\Users\10639\Desktop\加密\binance_free_db\history\funding   fundingTime, fundingRate（110 回填）
BINANCE_ROOT = C:\Users\10639\Desktop\加密\binance_free_db\raw_1h          （BTC regime 前向 + 169 拼接历史）
```

---

## 3. ctx 列 / detect_events 输出列（确切 schema）

**113 `load_price_ctx` → ctx DataFrame**（index = ts ms int64）：

| 列 | 公式 | 备注 |
|---|---|---|
| `close` | klines close（30d rolling median 偏离 50× 抹假 bar） | 清洗口径 113 |
| `ret_24h` | `close.pct_change(24)×100` | % |
| `price_z` | `rolling_z(close, 720)` | 30d 自序列 z，min_periods=360 |
| `cvd_z` | `rolling_z(cumsum(2·taker_buy_qv − quote_volume), 720)` | CVD 代理 |
| `cvd_divergence` | `price_z − cvd_z` | 信号核心 |
| `oi_24h_chg` | oi_ohlc close 的 `pct_change(24)×100` | 窗口外 NaN |
| （161 追加）`div` / `np_z` | 见 §1 ⑥ | 数据窗内 |

**115 `detect_events(sym, ctx, funding, "wash_cvd")` 输出**：仅 `symbol`, `timestamp`（ms int）。触发 = `(price_z<−2 | ret_24h<−8%) & cvd_divergence>2.0`，72h 冷却/币。

**113 `detect_washout_events` 输出（washout_settle 变体，备选事件池）**：`symbol, timestamp, feature, feature_value, ret_24h_at_event, conf_cvd, conf_fund, conf_oi`——其中 `conf_cvd/conf_fund/conf_oi` 是事件时点布尔确认特征，若换用该池可直接入特征矩阵。

**`forward_stats` 追加列**：`ret_4h, ret_24h, ret_72h, ret_168h, mfe_pct, mae_pct`（时间对齐 asof，无前视）。标签只用 `ret_168h`（= r168）。

---

## 4. 逐特征组细节

### ① 信号强度（washout 深度 + CVD 背离）
- `price_z`：30d 滚动 z。事件触发本就要求 <−2，故事件处取值集中在 (−2, −5] 附近，**信息主要在"有多极端"**；分桶比连续值更稳（plan：单特征已被 115 用尽，ML 价值在交互）。
- `cvd_divergence`：事件要求 >2.0，取值上界无约束（瀑布语境可 >5）。作为连续特征输入。
- `ret_24h`：触发要求 <−8%，极端可达 −40%+。
- `oi_24h_chg`：**36.1% 缺失（仅 2024-06+）**。杠杆出清代理；若主口径要 n=1348 全用，此列必须排除或给 NaN 掩码（推荐排除，另跑子口径）。

### ② 确认信息 r4
- `r4 = (close[pos+4]/close[pos] − 1)×100`（148 口径，pos 为事件 ts 的 bar 位置）。
- 语义：**事件后 4h 的已实现反弹**，决策时点 = t+4h（148 的 V_confirm 即 4h 确认后入场）。主口径下模型把它当特征，输出概率天然是"事件后 4h 的信息"，入场延迟 4h。
- 事件池已要求 pos+168 存在（forward 完整），故 r4 本身不缺（除数据末端事件已被过滤）。
- 与标签的关系必须预注册：**标签 r168 从事件 ts 起算**（与 148 一致），不因 r4 特征而偏移。

### ③ 时间锚 days_since_listing
- `listing_dates()`（157/160）：读 `klines/{sym}.parquet` 的 `open_time` min。
- `age_days = (ts − listing_ms) / 86400_000`；`is_new90 = age_days < 90`。
- 全部事件都有 listing（universe 66 币全部已上市）→ 0% 缺失；新币期占比 10.0%（135 事件）。
- 注意：listing 用 klines 首 bar，实际可能晚于真实上线（数据起点），对 2022 年老币无影响，对新币是保守偏移。

### ④ 容量锚 24h 成交额
- `liq24 = quote_volume.rolling(24).sum()`（160 口径，klines）；`log1p(liq24)` 建议作为连续输入（量纲跨 6 个数量级）；s010 分层哑变量（中位数切）可保留作对照。
- 0% 缺失。事件时点 asof（事件 bar 已收盘的成交额）。

### ⑤ 周期 Mayer / cycle_z / BTC regime
- `mayer`：BTC 日线 close / 200 日均线（min_periods=120）；2.8% 缺失（2022 初预热）。
- `cycle_z`：log(price) 对**全期**日序线性回归的残差 z（164/169 彩虹图简化）。**⚠️ 169 明确标注"统计口径，交易口径需滚动拟合重算"**——这个特征在历史回测里天然含未来拟合（回归系数用了全期数据），meta 实验有两条路（预注册选一）：
  1. **交易口径滚动重算**：每事件日只用截至当日的数据拟合线性趋势再取残差 z（≈ 172/175 或 169 的滚动替代），无前视；
  2. **保守放弃** `cycle_z`，只用 `mayer`（纯 rolling，无前视）——mayer 缺失率与信息量已足够表达周期带。
  推荐 2（半天实验的最小化路径）；若选 1，实现要按 §5 模板写成纯函数并在 asof 审计里复核。
- `regime`：`assign_regime`（btc_recovery = BTC 20d 回撤 < 阈值 且 >5d MA；risk_off = SP500 < 50d MA；否则 default）。SP500.parquet 至 2026-08-06，全窗口可算；2022 熊市多为 risk_off、2024/2025 崩盘恢复多为 btc_recovery。类别特征 → one-hot 或顺序编码。

### ⑥ 大户行为 div / np_z
- `div = top_position_long_percent − global_account_long_percent`（聪明钱−散户多头占比差）。161 已证：div>q67 层 168h 更强（信息锚成立）。
- `np_z = rolling_z(net_position_change_cum, 720)`（30d 净持仓 z；161 分层显示 np_z<−1 与 168h 负向关联）。
- 两列都只覆盖 2024-06-06→2026-05-26/28 窗口（36.1%/37.1% 全样本缺失；窗口内 100%/98.1%）。**滚动口径硬要求**（`rolling_z` 只用 ≤ 时点数据，天然无前视）。
- 子口径建议：`events_2024plus = 事件窗内 864 事件` 上把 ①④⑤⑦⑧⑨⑩ + div/np_z 一起建模。

### ⑦ 成交结构 taker_buysell
- raw `taker_buysell/` 目录（USD 口径）：`imb_24h = rolling_24((buy−sell)/(buy+sell))`，取值 [−1,1]。
- 151 另有 klines 口径：`imb_24h = rolling_24(2·taker_buy_qv − qv)/rolling_24(qv)` 与 `imb_norm`（720h min-max 归一）。**两个口径不同源，建模时预注册选一个**（推荐 raw taker_buysell 目录，字段直接、无 CVD 代理近似）。
- 缺失：同 ⑥ 窗口（36.1%）。

### ⑧ 上市形态 pump 哑变量
- `pump_gain = (nanmax(close[:i+1])/nanmin(close[:i+1]) − 1)×100`（160 口径：只用 ≤ 事件时点的价格，无前视）；`pump = pump_gain > 300`。
- 0% 缺失（160 要求至少 2 个有限值，全部事件满足）。
- 160 结论：非 pump 类更强 → 该特征预期负向贡献，正好是模型该学的交互。

### ⑨ 市场环境 VIX / breadth / 贪婪
- `vix_close`：**必须 searchsorted asof（108 `vix_gate_state` 的 day−1 口径）**。同日 map 会丢 26.3%（周末/假日）；searchsorted 后 0% 缺失。VIX 日度粘滞是已知局限（123 局限说明：事件日盘中 VIX 波动不捕捉）。
- `vix_low/vix_high`：1y 滚动 75 分位动态边界（120 口径；108 已落地 vix_gate 标注：`vix_status/vix_close/vix_q75/vix_gate_ok` 四列在 forward 流可直接用）。
- `breadth_pct/breadth_z`：6h 网格市场级出清广度（124：逐币 washout 判定，breadth=100×出清币数/有效币数，n_active≥5）。0% 缺失；breadth≥5% 占事件 52.0%。2022 网格粒度粗（n_active≈18）→ breadth 离散度高，分桶时注意。
- `fear_greed`：日度 0-100，99.9% 覆盖；建议事件日−1 asof（132 口径：贪婪 60+ 层是唯一显著层）。

### ⑩ 波动率 ATR / vol
- `vol_24h = close.pct_change().rolling(24).std()`（02/07 口径，小时收益 24h 波动）；`atr24 = rolling(24).max − rolling(24).min` 可选。0% 缺失。
- 用途：vol-target 相关（事件前波动越大 → 仓位越小），在 meta 层是天然"下注大小"输入。

---

## 5. 事件时点 asof 实现模板（照抄）

```python
def attach_asof(ctxs: dict[str, pd.DataFrame], events: pd.DataFrame,
                cols: list[str]) -> pd.DataFrame:
    """逐列 searchsorted 取事件前最近已完成 bar 的值（161 attach_asof 口径，无前视）。"""
    ev = events.copy()
    for c in cols:
        ev[f"{c}_at"] = np.nan
    for sym, g in ev.groupby("symbol", sort=False):
        if sym not in ctxs:
            continue
        t = ctxs[sym]
        idx = t.index.to_numpy(dtype=np.int64)
        pos = np.searchsorted(idx, g["timestamp"].to_numpy(dtype=np.int64), side="right") - 1
        pos = np.clip(pos, 0, len(idx) - 1)
        for c in cols:
            vals = pd.to_numeric(t[c], errors="coerce").to_numpy(dtype=float)
            ev.loc[g.index, f"{c}_at"] = vals[pos]
    return ev

# 日度宏观（VIX/fear_greed）：searchsorted asof 日-1（108 vix_gate_state 口径）
def macro_asof(events: pd.DataFrame, macro: pd.Series, back_days: int = 1) -> np.ndarray:
    """macro.index = ms int64；事件 ts 向前 back_days 天找最近已收盘值。"""
    asof_ms = events["timestamp"].to_numpy(dtype=np.int64) - back_days * 86_400_000
    idx = macro.index.to_numpy(dtype=np.int64)
    pos = np.searchsorted(idx, asof_ms, side="right") - 1
    out = np.full(len(events), np.nan)
    ok = pos >= 0
    out[ok] = macro.to_numpy()[pos[ok]]
    return out

# 6h 网格（breadth）：事件 ts 取前最近网格点（124 attach_breadth 口径）
def grid_asof(events: pd.DataFrame, grid_vals: pd.Series) -> np.ndarray:
    pos = np.searchsorted(grid_vals.index.to_numpy(dtype=np.int64),
                          events["timestamp"].to_numpy(dtype=np.int64), side="right") - 1
    out = np.full(len(events), np.nan)
    ok = pos >= 0
    out[ok] = grid_vals.to_numpy()[pos[ok]]
    return out
```

**宽表拼装顺序（对照 blueprint §2 第 1 步）**：
1. `m115.detect_events` 全币 → 1348 事件（symbol, ts）
2. `forward_stats` → r168（标签）+ r4（特征）
3. ①③④⑦⑩：`attach_asof(ctxs, events, ["price_z","ret_24h","cvd_divergence","oi_24h_chg","liq24","vol_24h","imb_24h",...])`
4. ⑤：`m164.btc_cycle()` 日 map（mayer/cycle_z）+ `assign_regime`
5. ⑥：`m161.add_positioning(ctxs)` 后 attach（div/np_z）
6. ⑧：`close[:i+1]` 截断计算 pump_gain（160 循环）
7. ⑨：`macro_asof`（VIX/fear_greed）+ `grid_asof`（breadth）
8. 标签 `y = (r168 > 0.54).astype(int)`；剔除 y NaN（forward 不完整）行

---

## 6. 缺失率汇总（实测，n=1348）

| 覆盖 | 列 | 说明 |
|---|---|---|
| 100% | price_z / ret_24h / cvd_divergence / liq24 / vol_24h / atr24 / age_days / pump_gain / breadth_pct / vix_close(searchsorted) / funding | 核心列，全窗口 |
| 99.9% | fear_greed | 1 个日期空洞 |
| 97.2% | mayer / cycle_z | 2022 初预热 38 事件 |
| 63.9% | oi_24h_chg / div / imb_24h | 数据窗 2024-06 起 |
| 62.9% | np_z | 同窗 + 30d 滚动预热 |
| ~100% (窗口内) | div(100%) / np_z(98.1%) / imb_24h(100%) | 2024-06→2026-05 子口径 |

**缺失处理建议**（预注册）：
- 全窗口口径（n≈1348）：只入 100% 列（①price_z/ret_24h/cvd_divergence ③age_days/is_new90 ④liq24/log_liq24 ⑤mayer/regime ⑧pump_gain ⑨vix/breadth/fear_greed ⑩vol_24h）；`cycle_z` 保守弃用或滚动重算。
- 2024-06+ 子口径（n≈864）：上述 + ⑥div/np_z ⑦imb_24h ①oi_24h_chg。
- NaN 在 `SimpleImputer(median)` 处理（每 fold train 内拟合，blueprint §7）；窗口特征缺失集中在时间轴两端，**不要用"全样本均值填充"**（会把 2022 事件填成 2024 语境的值）。
