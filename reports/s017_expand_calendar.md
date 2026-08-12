# s017 扩日历报告

- date: 2026-08-12 08:17 UTC
- script: `scripts/s017_expand_calendar.py`
- klines candidates: 109
- API ok / fail: 101 / 8
- symbols with non-empty schedule this run: 20
- **merged unique events**: 14686
- **unique symbols in events**: 31
- rows pct≥0.5% / ≥1%: 3174 / 1491

## 有 schedule 的币（n_events>0）

```
    symbol                    asset  n_schedule  n_events
   SEIUSDT                      Sei        2558      2558
   SUIUSDT                      Sui        2558      2558
  NEARUSDT            NEAR Protocol        1827      1827
   WLDUSDT                Worldcoin        1462      1462
   CRVUSDT                Curve DAO        1460      1460
   TIAUSDT                 Celestia        1097      1097
  ALGOUSDT                 Algorand         120       120
    OPUSDT                 Optimism          50        50
   UNIUSDT                  Uniswap          48        48
   ICPUSDT        Internet Computer          48        48
  API3USDT                     API3          42        42
  AVAXUSDT                Avalanche          41        41
  ANKRUSDT                     Ankr          38        38
   ARBUSDT                 Arbitrum          38        38
   LDOUSDT                 Lido DAO          29        29
   INJUSDT                Injective          27        27
  HBARUSDT                   Hedera          18        18
  ONDOUSDT                     Ondo          17        17
 1INCHUSDT                    1inch           9         9
ALPINEUSDT Alpine F1 Team Fan Token           5         5
```

## 产出

- `G:\Quant test\derived_data\token_unlocks\sample_events.parquet`
- `G:\Quant test\derived_data\token_unlocks\coverage_expanded.csv`

下一步：`python scripts/s017_expand_diagnose.py`（冻结 pct=1% 重算残差+集中度）
