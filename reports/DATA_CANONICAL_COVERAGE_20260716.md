# CoinGlass/Binance canonical coverage report

Generated: 2026-07-16T06:38:02Z
Live symbols evaluated: 59
CoinGlass root: `C:\Users\10639\Desktop\加密\coinglass_db`
Binance root: `C:\Users\10639\Desktop\加密\binance_free_db`

## Coverage and adapter checks

| Source | Dimension | Files | Live present | Date range UTC | Adapter | Checked files | Failures | Sample schema |
|---|---|---:|---:|---|---|---:|---:|---|
| CoinGlass | klines | 124 | 59/59 | 2021-12-31 → 2026-07-07 | PASS | 124 | 0 | open_time, open, high, low, close, volume, close_time, quote_volume, trades, taker_buy_volume, taker_buy_quote_volume, ignore, volume_usd, datetime |
| CoinGlass | funding | 123 | 59/59 | 2024-06-05 → 2026-06-23 | PASS | 123 | 0 | time, open, high, low, close, _symbol, datetime |
| CoinGlass | oi | 123 | 59/59 | 2024-06-05 → 2026-05-26 | PASS | 123 | 0 | time, open, high, low, close, _symbol |
| CoinGlass | taker | 123 | 59/59 | 2024-06-06 → 2026-05-27 | PASS | 123 | 0 | time, taker_buy_volume_usd, taker_sell_volume_usd, _symbol |
| Binance | klines | 73 | 59/59 | 2019-11-27 → 2026-07-15 | PASS | 73 | 0 | open_time, open, high, low, close, volume, close_time, quote_volume, trades, taker_buy_vol, taker_buy_quote_vol, turnover_usd |
| Binance | funding | 73 | 59/59 | 2026-06-07 → 2026-07-15 | PASS | 73 | 0 | symbol, fundingTime, fundingRate_raw, fundingRate_decimal, markPrice |
| Binance | oi | 73 | 59/59 | 2026-06-16 → 2026-07-15 | PASS | 73 | 0 | symbol, timestamp, sumOpenInterest, sumOpenInterestValue |
| Binance | taker | 73 | 59/59 | 2026-06-16 → 2026-07-15 | PASS | 73 | 0 | symbol, timestamp, buySellRatio, buyVol, sellVol |

## Integration boundary

- This is a read-only comparison report; no parquet data was merged or overwritten.
- Adapter status is based on the complete contents of every discovered parquet file, not a head-only sample.
- The existing AlphaHive scanner still consumes the CoinGlass paths declared in `config/data_contracts.yaml` and `config/universe.json`.
- Binance remains a separate live store. The canonical adapters preserve `source`, `source_schema`, and source-unit provenance.
- Funding is exposed as decimal plus contract-compatible raw-percent view; OI absolute units remain `UNDECLARED` unless an authoritative contract declares them.
- If Binance `fundingRate_raw` and `fundingRate_decimal` are equal, the adapter labels them `decimal_alias_columns`; the column name alone is not treated as proof of percent conversion.
- Source precedence, historical cutoff, and any scanner source switch remain Owner decisions.

## Status

`GREEN_FOR_ADDITIVE_RECONCILIATION` — adapters can be tested without changing the production scanner.
