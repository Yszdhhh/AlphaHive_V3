# Q-CALIBRATION-001 — historical trigger calibration baseline

**owner:** Codex  
**UTC date:** 2026-07-16  
**status:** `CALIBRATION_ONLY / NOT_PAPER_ELIGIBLE`  
**purpose:** establish a direction-neutral historical measurement baseline while
ResearchJob and PaperPlan infrastructure remain unfinished.

## Scope and method

Read-only evaluation of the frozen replay artifacts for:

- `20260408_0000_utc_replay`
- `20260414_0000_utc_replay`
- `20260511_1200_utc_replay`
- `20260528_1200_utc_replay`

The quarantined `20260707_1341_utc` run was excluded because its return tape is
empty. For each candidate, the entry reference is the first completed bar after
the scan time, and forward close/high/low observations are read only from the
run's independent `return_tape.csv`. No future value is fed into trigger
construction. No direction is assigned and no Paper Plan is generated.

## Initial results

| Metric | Result |
|---|---:|
| Replays evaluated | 4 |
| Candidate rows evaluated | 61 |
| `vol_quantile_high` component occurrences | 38 |
| `large_move_abs` component occurrences | 31 |
| `large_move_excess` component occurrences | 33 |

| Horizon | n | Mean raw return | Median | P10 | P90 | Positive share |
|---|---:|---:|---:|---:|---:|---:|
| 4h | 61 | 2.5681% | 0.7856% | -2.0718% | 6.4712% | 73.77% |
| 24h | 61 | 2.3020% | -0.7226% | -5.1589% | 8.3755% | 36.07% |
| 72h | 61 | 5.1038% | -0.8493% | -9.8359% | 32.1031% | 47.54% |
| 168h | 61 | 2956.1112% | -4.8256% | -20.4661% | 24.3909% | 34.43% |

## Interpretation boundary

The 168h mean is dominated by an extreme `90327.5093%` observation and is not
usable as a performance claim. The small four-replay sample, heterogeneous
symbols and unresolved contract/event outliers make this a pipeline and data
quality baseline only. The median and quantile columns are retained to expose
the instability; they are not a GO/NO-GO or alpha verdict.

## Required next work

1. Add symbol identity/contract-event checks and explicit outlier quarantine to
   the calibration harness before computing any risk preset statistics.
2. Split results by trigger component and replay run, preserving cutoff and
   snapshot hashes.
3. Add friction/funding sensitivity only after the raw-return data quality
   checks pass.
4. Keep OI/funding quantile triggers dormant and `paper_eligibility=ALLOW`
   parked. A later PaperPlan implementation requires Owner approval and a
   separate deterministic engine audit.

## Boundary self-check

- No repository production code, scanner, thresholds or configuration changed.
- No database, Parquet, scheduler, credentials or external provider was used.
- No direction, order, Paper Plan or live-trading decision was produced.
