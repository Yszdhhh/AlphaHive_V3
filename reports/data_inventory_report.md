# coinglass_db 数据盘点报告

- 生成时间: 2026-08-06 09:36 UTC
- 数据根: `C:\Users\10639\Desktop\🔒 加密资产\coinglass_db`
- 退市 base_asset 数（delisted_pairs.json）: 404

## 各维度覆盖总览

| 维度 | 文件数 | 数据行中位数 | 最早 | 最晚 | 断点>2h符号数 |
|---|---|---|---|---|---|
| cvd | 120 | 14000 | 2024-06-06 | 2026-05-28 | 0 |
| funding_ohlc | 123 | 14223 | 2024-06-05 | 2026-06-23 | 0 |
| klines | 124 | 14930 | 2021-12-31 | 2026-07-07 | 74 |
| liquidation | 123 | 14246 | 2024-06-06 | 2026-06-23 | 0 |
| ls_global | 123 | 13578 | 2024-06-06 | 2026-05-27 | 0 |
| ls_top_trader | 123 | 14145 | 2024-06-06 | 2026-07-07 | 89 |
| macro | 4 | 3160 | 2004-01-02 | 2026-06-26 | 4 |
| net_position | 123 | 13629 | 2024-06-07 | 2026-05-28 | 0 |
| oi_ohlc | 123 | 14816 | 2024-06-05 | 2026-05-26 | 0 |
| taker_buysell | 123 | 13584 | 2024-06-06 | 2026-05-27 | 0 |

## 回测窗口参考

> 交集列 = 所有 symbol 同时可用的【严格公共窗】（被个别上市晚/退市早的币压缩）。
> 事件研究实际用每个 symbol 自身可用窗口，主覆盖区间才代表真实回测窗。

| 维度 | 严格公共交集 | 主覆盖（中位数 symbol） | 符号数 |
|---|---|---|---|
| cvd | 2026-04-16 → 2026-05-27 | 2024-10-21 → 2026-05-28 | 120 |
| funding_ohlc | 2026-05-21 → 2026-06-23 | 2024-11-07 → 2026-06-23 | 123 |
| klines | 2026-05-21 → 2026-06-08 | 2024-10-12 → 2026-07-07 | 124 |
| liquidation | 2026-05-20 → 2026-05-27 | 2024-11-06 → 2026-06-23 | 123 |
| ls_global | 2026-05-21 → 2026-05-27 | 2024-11-07 → 2026-05-27 | 123 |
| ls_top_trader | 2026-05-21 → 2026-05-26 | 2024-11-07 → 2026-07-07 | 123 |
| macro | 2024-01-02 → 2026-06-26 | 2013-03-21 → 2026-06-26 | 4 |
| net_position | 2026-05-20 → 2026-05-28 | 2024-11-06 → 2026-05-28 | 123 |
| oi_ohlc | 2026-05-21 → 2026-05-26 | 2024-09-16 → 2026-05-26 | 123 |
| taker_buysell | 2026-05-21 → 2026-05-27 | 2024-11-07 → 2026-05-27 | 123 |

## 最大断点 TOP 12

| 维度 | 符号 | 最大gap(h) | >2h断点数 | 区间 |
|---|---|---|---|---|
| klines | XMRUSDT | 2534.0 | 1 | 2021-12-31 → 2026-06-23 |
| macro | DXY | 1800.0 | 543 | 2022-06-08 → 2026-06-26 |
| klines | AERGOUSDT | 465.0 | 1 | 2025-03-21 → 2026-06-23 |
| ls_top_trader | 1000000BOBUSDT | 414.0 | 1 | 2025-06-05 → 2026-07-07 |
| ls_top_trader | 1000RATSUSDT | 414.0 | 1 | 2024-06-06 → 2026-07-07 |
| ls_top_trader | AEROUSDT | 414.0 | 1 | 2024-12-04 → 2026-07-07 |
| ls_top_trader | AMDUSDT | 414.0 | 1 | 2026-05-06 → 2026-07-07 |
| ls_top_trader | BZUSDT | 414.0 | 1 | 2026-04-01 → 2026-07-07 |
| ls_top_trader | CLUSDT | 414.0 | 1 | 2026-04-01 → 2026-07-07 |
| ls_top_trader | CRCLUSDT | 414.0 | 1 | 2026-02-09 → 2026-07-07 |
| ls_top_trader | GRASSUSDT | 414.0 | 1 | 2024-11-08 → 2026-07-07 |
| ls_top_trader | HYPEUSDT | 414.0 | 1 | 2025-05-30 → 2026-07-07 |

## 退市币（coinglass 有历史数据但已下架）

- 47 个符号在 delisted_pairs.json 中：1000000BOBUSDT, 1000000MOGUSDT, 1000LUNCUSDT, 1000PEPEUSDT, 1INCHUSDT, ACEUSDT, ADAUSDT, AIAUSDT, AINUSDT, ALCHUSDT, ALGOUSDT, APEUSDT, ARCUSDT, ASTERUSDT, ATOMUSDT, BCHUSDT, BNBUSDT, BTCUSDT, BZUSDT, CHZUSDT, CLUSDT, CRVUSDT, DASHUSDT, DOGEUSDT, ETHUSDT, FILUSDT, HYPEUSDT, LDOUSDT, LINKUSDT, LTCUSDT, OPUSDT, PUMPUSDT, RIVERUSDT, SKYAIUSDT, SOLUSDT, SUIUSDT, TAOUSDT, TONUSDT, TRXUSDT, WIFUSDT, WLDUSDT, XAGUSDT, XAUUSDT, XLMUSDT, XMRUSDT, XPLUSDT, ZECUSDT

## 单位/列结构采样


### klines（124 文件）
- `0GUSDT` cols=['open_time', 'open', 'high', 'low', 'close', 'volume', 'close_time', 'quote_volume', 'trades', 'taker_buy_volume', 'taker_buy_quote_volume', 'ignore', 'volume_usd', 'datetime']
  - 数值列中位数: {'open': 0.6532, 'high': 0.6586, 'low': 0.6474, 'close': 0.6532, 'volume': 754716.0, 'close_time': 1769030999999.0, 'quote_volume': 672157.3040499999, 'trades': 9996.0, 'taker_buy_volume': 391465.0, 'taker_buy_quote_volume': 345288.5257, 'volume_usd': 141545.8705}
- `ENAUSDT` cols=['open_time', 'open', 'high', 'low', 'close', 'volume', 'close_time', 'quote_volume', 'trades', 'taker_buy_volume', 'taker_buy_quote_volume', 'volume_usd', 'datetime']
  - 数值列中位数: {'open': 0.3634, 'high': 0.3678, 'low': 0.3597, 'close': 0.3633, 'volume': 25408771.0, 'close_time': 1745999999999.0, 'quote_volume': 8956012.9292, 'trades': 28530.0, 'taker_buy_volume': 12542474.0, 'taker_buy_quote_volume': 4435564.534, 'volume_usd': 5170938.6649}

### oi_ohlc（123 文件）
- `0GUSDT` cols=['time', 'open', 'high', 'low', 'close', '_symbol']
  - 数值列中位数: {'open': 12992408.0, 'high': 13126523.0, 'low': 12824670.0, 'close': 12991452.5}
- `ENAUSDT` cols=['time', 'open', 'high', 'low', 'close', '_symbol']
  - 数值列中位数: {'open': 117358941.5, 'high': 118270305.5, 'low': 116137105.5, 'close': 117358941.5}

### funding_ohlc（123 文件）
- `0GUSDT` cols=['time', 'open', 'high', 'low', 'close', '_symbol', 'datetime']
  - 数值列中位数: {'open': -0.020537, 'high': -0.016543000000000002, 'low': -0.0247215, 'close': -0.020537}
- `ENAUSDT` cols=['time', 'open', 'high', 'low', 'close', '_symbol', 'datetime']
  - 数值列中位数: {'open': 0.0019405, 'high': 0.0039795, 'low': -0.0001515, 'close': 0.001938}

### liquidation（123 文件）
- `0GUSDT` cols=['time', 'long_liquidation_usd', 'short_liquidation_usd', '_symbol', 'datetime']
  - 数值列中位数: {'long_liquidation_usd': 0.0, 'short_liquidation_usd': 0.0}
- `ENAUSDT` cols=['time', 'long_liquidation_usd', 'short_liquidation_usd', '_symbol', 'datetime']
  - 数值列中位数: {'long_liquidation_usd': 2601.5937999999996, 'short_liquidation_usd': 375.8861}

### ls_top_trader（123 文件）
- `0GUSDT` cols=['time', 'top_position_long_percent', 'top_position_short_percent', 'top_position_long_short_ratio', '_symbol']
  - 数值列中位数: {'top_position_long_percent': 59.01, 'top_position_short_percent': 38.98, 'top_position_long_short_ratio': 1.44}
- `ENAUSDT` cols=['time', 'top_position_long_percent', 'top_position_short_percent', 'top_position_long_short_ratio', '_symbol']
  - 数值列中位数: {'top_position_long_percent': 60.23, 'top_position_short_percent': 38.94, 'top_position_long_short_ratio': 1.56}

### ls_global（123 文件）
- `0GUSDT` cols=['time', 'global_account_long_percent', 'global_account_short_percent', 'global_account_long_short_ratio', '_symbol']
  - 数值列中位数: {'global_account_long_percent': 42.46, 'global_account_short_percent': 57.54, 'global_account_long_short_ratio': 0.74}
- `ENAUSDT` cols=['time', 'global_account_long_percent', 'global_account_short_percent', 'global_account_long_short_ratio', '_symbol']
  - 数值列中位数: {'global_account_long_percent': 69.1, 'global_account_short_percent': 30.9, 'global_account_long_short_ratio': 2.24}

### net_position（123 文件）
- `0GUSDT` cols=['net_long_change', 'net_short_change', 'net_long_change_cum', 'net_short_change_cum', 'net_position_change_cum', 'time', '_symbol']
  - 数值列中位数: {'net_long_change': 0.0, 'net_short_change': 0.0, 'net_long_change_cum': -184795.0, 'net_short_change_cum': -87832.0, 'net_position_change_cum': -419790.5}
- `ENAUSDT` cols=['net_long_change', 'net_short_change', 'net_long_change_cum', 'net_short_change_cum', 'net_position_change_cum', 'time', '_symbol']
  - 数值列中位数: {'net_long_change': 0.0, 'net_short_change': 0.0, 'net_long_change_cum': -9505184.0, 'net_short_change_cum': 17666293.0, 'net_position_change_cum': -25792506.5}

### cvd（120 文件）
- `0GUSDT` cols=['time', 'taker_buy_vol', 'taker_sell_vol', 'cum_vol_delta', '_symbol']
  - 数值列中位数: {'taker_buy_vol': 340185.67455, 'taker_sell_vol': 356686.67195, 'cum_vol_delta': -11503385.10105}
- `ESPORTSUSDT` cols=['time', 'taker_buy_vol', 'taker_sell_vol', 'cum_vol_delta', '_symbol']
  - 数值列中位数: {'taker_buy_vol': 62984.35735, 'taker_sell_vol': 64315.800950000004, 'cum_vol_delta': 528008.16875}

### taker_buysell（123 文件）
- `0GUSDT` cols=['time', 'taker_buy_volume_usd', 'taker_sell_volume_usd', '_symbol']
  - 数值列中位数: {'taker_buy_volume_usd': 346394.747, 'taker_sell_volume_usd': 366817.6838}
- `ENAUSDT` cols=['time', 'taker_buy_volume_usd', 'taker_sell_volume_usd', '_symbol']
  - 数值列中位数: {'taker_buy_volume_usd': 4136510.4809999997, 'taker_sell_volume_usd': 4319194.1109}