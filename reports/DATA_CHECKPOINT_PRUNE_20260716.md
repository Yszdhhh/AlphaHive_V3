# Binance checkpoint prune evidence

Generated: 2026-07-16T06:37:22Z (UTC)

## Operation

- Target: `C:\Users\10639\Desktop\加密\binance_free_db\checkpoint_1h.json`
- Backup: `C:\Users\10639\Desktop\加密\binance_free_db\checkpoint_1h.pre_n4_20260716T063722Z.json`
- No `*.lock` file was present under the Binance runtime root before the operation.
- Raw parquet files were not deleted or rewritten.

## Preconditions and result

| Check | Before | After |
|---|---:|---:|
| Effective universe | 59 | 59 |
| Checkpoint keys per partition | 73 | 59 |
| Missing effective symbols | 0 | 0 |
| Extra checkpoint symbols | 14 | 0 |
| Non-zero `_fail` counters | 0 | 0 |

The same 14 keys were removed from all four data partitions and all four
failure-counter partitions:

`BZUSDT`, `CHZUSDT`, `CRCLUSDT`, `INTCUSDT`, `MUUSDT`, `NVDAUSDT`,
`SAHARAUSDT`, `SEIUSDT`, `SNDKUSDT`, `SPCXUSDT`, `TSLAUSDT`, `XAGUSDT`,
`XAUUSDT`, `ZROUSDT`.

SHA-256 evidence:

- Backup: `f6bb96aed4adc0edeff11648d21547e93f3fa3f73e3cf238c96aeffa14a63cd9`
- Pruned target: `f12cc094ab657c7ddc1dd970fa2f8c14eeb95b9d79a4909d3bc57669460bf2bb`

Post-operation read-only verification confirmed 59 identical keys in all
eight partitions, zero missing symbols, and zero failure counters. Full
repository regression after the operation: `340 passed`.

Status: `ACCEPTED / GREEN`
