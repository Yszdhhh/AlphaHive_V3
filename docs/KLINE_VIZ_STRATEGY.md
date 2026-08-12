# K 线还原与策略可视化（短指南）

## 数据从哪来

| 优先级 | 路径 | 说明 |
|---|---|---|
| 1 | `binance_free_db/history/klines` | 全历史 1h（218 回补） |
| 2 | `binance_free_db/raw_1h/klines` | 与 history **硬链接**同一份 |
| 3 | coinglass raw_1h/klines | 对照冷库（停更 2026-07） |

API：`harness.lib.klines_store.load_klines`

## 一键出图

```bash
cd "G:\Quant test\AlphaHive_V3"
python scripts/223_kline_view.py --symbol BTCUSDT --days 90
```

打开 `reports/kline_views/*.png` 即可；CSV 可用 Excel / TradingView 导入（时间列为 `datetime_utc`）。

## 策略沙盒最小循环

1. `load_klines(symbol, start=, end=)` 取 OHLC  
2. 算信号（你的规则）  
3. 用 `223` 同区间出图，人工核对信号点（可把信号日期标在图上——后续可扩展）  
4. 正式检验仍走 alpha_card + 漏斗，不靠肉眼 GO  

## 与纸面/前向关系

- 可视化 = **研究辅助**，不是 143 虚拟交易  
- 前向事件仍由 108/109/159 日任务写 CSV  
