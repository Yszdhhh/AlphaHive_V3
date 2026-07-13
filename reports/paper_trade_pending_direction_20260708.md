# Paper Trade Pending Direction - 2026-07-08

Purpose: list red-team approved Paper Trade candidates that still require Owner-only Long/Short direction. Agents must not assign direction.

Generated local time: 2026-07-08 15:51:40
Source ledger: `G:\Quant test\AlphaHive_V3\ledger\Anomaly_Ledger.csv`
Pending direction count: 6

## Summary

| symbol | count |
|---|---:|
| LABUSDT | 2 |
| SKYAIUSDT | 1 |
| XLMUSDT | 1 |
| SUIUSDT | 1 |
| VVVUSDT | 1 |

## Pending Rows

| run_id | record_id | scan_time_utc | symbol | rank | turnover_24h_usd | trigger_reason | trigger_quantile | abs_move_pct_24h | excess_move_pct_24h | funding_sign | funding_rate_8h |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| 20260408_0000_utc_replay | 20260408_0000_utc_replay_0008 | 2026-04-08T00:00:00+00:00 | LABUSDT | 31 | 58,913,001 | vol_quantile_high/large_move_abs/large_move_excess | 0.944756554307116 | 31.44821542920697 | 26.98382462390776 | positive | 0.00064626 |
| 20260511_1200_utc_replay | 20260511_1200_utc_replay_0015 | 2026-05-11T12:00:00+00:00 | SUIUSDT | 15 | 1,808,112,908 | vol_quantile_high/large_move_abs/large_move_excess | 0.9985955056179776 | 10.74257856707581 | 10.265987837198765 | positive | 0.0001 |
| 20260511_1200_utc_replay | 20260511_1200_utc_replay_0009 | 2026-05-11T12:00:00+00:00 | LABUSDT | 31 | 400,797,434 | large_move_abs/large_move_excess | 0.6970973782771536 | -10.529201010239452 | -11.0057917401165 | positive | 5e-05 |
| 20260511_1200_utc_replay | 20260511_1200_utc_replay_0017 | 2026-05-11T12:00:00+00:00 | VVVUSDT | 38 | 160,927,666 | large_move_abs/large_move_excess | 0.6970973782771536 | 17.02310231023101 | 16.546511580353965 | positive | 0.0001424699999999 |
| 20260511_1200_utc_replay | 20260511_1200_utc_replay_0014 | 2026-05-11T12:00:00+00:00 | SKYAIUSDT | 64 | 104,154,308 | large_move_abs/large_move_excess | 0.6779026217228464 | -24.01374694763497 | -24.49033767751202 | positive | 0.00053929 |
| 20260528_1200_utc_replay | 20260528_1200_utc_replay_0013 | 2026-05-28T12:00:00+00:00 | XLMUSDT | 48 | 313,615,135 | vol_quantile_high/large_move_abs/large_move_excess | 1.0 | 21.092688230497416 | 24.07507881698052 | negative | -0.00030254 |

## Notes

- `20260408_0000_utc_replay_0008` LABUSDT: red_team_decision=Paper Trade; confidence=High; reason=Triple-trigger at 94.5th quantile, +27% excess, strong volume. LAB is mid-cap with consistent liquidity.; human_check=Verify 24h/72h return persistence; check if move was news-driven; veto_flags=none
- `20260511_1200_utc_replay_0015` SUIUSDT: red_team_decision=Paper Trade; confidence=High; reason=Triple-trigger at 99.9th quantile on $1.8B turnover. SUI is a major L1 with deep liquidity. The move is well-confirmed across multiple dimensions.; human_check=Verify SUI ecosystem didn't have a major event; this is a strong candidate; veto_flags=none
- `20260511_1200_utc_replay_0009` LABUSDT: red_team_decision=Paper Trade; confidence=Medium; reason=LAB appears again with opposite direction (negative excess). $401M turnover confirms move is real. Quantile moderate but magnitude + turnover justify human review.; human_check=LAB is a recurring symbol — check if direction flip across runs is structural; veto_flags=none
- `20260511_1200_utc_replay_0017` VVVUSDT: red_team_decision=Paper Trade; confidence=High; reason=Strong excess (+16.5%) on $161M turnover. VVV is a mid-cap token with decent liquidity. Quantile 0.697 is acceptable for the move size.; human_check=Confirm move direction aligns with broader market; check VVV sector momentum; veto_flags=none
- `20260511_1200_utc_replay_0014` SKYAIUSDT: red_team_decision=Paper Trade; confidence=High; reason=Large excess (-24.5%) on a well-traded token with $104M turnover. Quantile 0.678 is moderate but the magnitude of excess is significant. SKYAI has appeared in multiple runs.; human_check=Verify SKYAIUSDT move wasn't driven by a single large order; check if this is a breakout or breakdown pattern; veto_flags=none
- `20260528_1200_utc_replay_0013` XLMUSDT: red_team_decision=Paper Trade; confidence=High; reason=Extreme quantile (1.0) with +24% excess on $314M turnover. XLM is a well-established altcoin. The move is large but well-confirmed.; human_check=Verify XLM didn't have a protocol event; negative funding adds cost to a long; veto_flags=none

## Required Owner Action

For each row, set exactly one direction: `Long`, `Short`, or explicitly downgrade the decision away from `Paper Trade`. After that, rerun returns and gates for affected runs.
