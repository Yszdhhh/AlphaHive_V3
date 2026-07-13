# Paper Trade Virtual Results - 2026-07-09

Direction rule: positive pre-scan excess momentum -> Long; negative pre-scan excess momentum -> Short. No future-return input used for direction assignment.

Generated UTC: 2026-07-09 00:35:08
Source ledger: `G:\Quant test\AlphaHive_V3\ledger\Anomaly_Ledger.csv`
CSV: `G:\Quant test\AlphaHive_V3\reports\paper_trade_virtual_results_20260709.csv`

## Direction Assignments

| record_id | symbol | direction | basis excess 24h | funding 8h | friction bps |
|---|---|---:|---:|---:|---:|
| 20260408_0000_utc_replay_0008 | LABUSDT | Long | 26.98% | 0.00064626 | 51.0 |
| 20260511_1200_utc_replay_0009 | LABUSDT | Short | -11.01% | 5e-05 | 31.0 |
| 20260511_1200_utc_replay_0014 | SKYAIUSDT | Short | -24.49% | 0.00053929 | 31.0 |
| 20260511_1200_utc_replay_0015 | SUIUSDT | Long | 10.27% | 0.0001 | 31.0 |
| 20260511_1200_utc_replay_0017 | VVVUSDT | Long | 16.55% | 0.00014247 | 31.0 |
| 20260528_1200_utc_replay_0013 | XLMUSDT | Long | 24.08% | -0.00030254 | 31.0 |

## Net Directional Excess Returns

| symbol | direction | 4h net | 24h net | 72h net | 7d net |
|---|---:|---:|---:|---:|---:|
| LABUSDT | Long | -4.35% | -2.52% | 30.14% | 15.96% |
| LABUSDT | Short | -7.01% | -0.26% | -25.01% | -11.99% |
| SKYAIUSDT | Short | 9.59% | -34.95% | 3.73% | 21.64% |
| SUIUSDT | Long | 0.73% | -0.21% | -3.52% | -12.80% |
| VVVUSDT | Long | -6.05% | -3.68% | -19.32% | -15.87% |
| XLMUSDT | Long | 14.07% | 14.53% | 44.21% | 34.58% |

## Aggregate

- 4h: mean=1.16%, median=-1.81%, win_rate=50.0%, n=6
- 24h: mean=-4.51%, median=-1.39%, win_rate=16.7%, n=6
- 72h: mean=5.04%, median=0.10%, win_rate=50.0%, n=6
- 7d: mean=5.25%, median=1.99%, win_rate=50.0%, n=6

## Caveat

This is a small paper-trade batch (n=6), useful for pipeline verification and early falsification only. It is not a GO/NO-GO statistical result yet.