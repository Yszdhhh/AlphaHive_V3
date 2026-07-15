# Binance Pull Runtime Manifest

The live Hermes runtime is intentionally outside the repository. This manifest pins the reviewed files and prevents an untracked runtime edit from being mistaken for a repository change.

Runtime root: `C:\Users\10639\AppData\Local\hermes\scripts`

| File | Role | SHA-256 |
|---|---|---|
| `binance_data_config.py` | paths, benchmark set, request pacing | `90BD585E142EA31D1C9436B6104F6AF2556EEB69ECFEAFE911A0DB907F362A6E` |
| `binance_data_puller.py` | lock, orchestration, freshness report | `65E81422D47190935EDBAF9830FF1804A6E32F283B9BB45ADD0D3D5449CF59D1` |
| `binance_klines_engine.py` | 1h klines, latest bootstrap, 90-day backfill, bounded transport retry and non-zero failure exit | `AA3CCE51FF19538A54B736F1ADECF699ACE751CD4FCC3BE6910DAE8142618BE0` |
| `binance_funding_engine.py` | raw 8h funding | `EE5525AE167165A2E5D45FF0E54695662E99839CFCD3BE8EB0FB21BC0E2BBDFC` |
| `binance_oi_engine.py` | 1h open interest, bounded transport retry and non-zero failure exit | `D64EFE9CE8FC5C0C3A1146BFD657D7D64973745E84F4CB3F2428751A4DB3B7A3` |
| `binance_taker_engine.py` | 1h taker buy/sell | `99317EAD85877D87A790F757F276BE5D5602358EFBC9800E86C66927E439EF40` |
| `binance_klines_reset.py` | destructive rebuild utility; do not run during scheduled pulls | `328699932A90A4FE721DD0AC97544C2A9040B59133853EE37449520D407D861D` |

The effective live universe is derived from `config/universe.json`: 66 liquidity-qualified candidates plus BTC/ETH/SOL benchmarks, with ten inactive/non-perpetual entries excluded from requests. No credentials, CoinGlass calls, trigger changes, Paper permission, or trading actions are part of this runtime.
