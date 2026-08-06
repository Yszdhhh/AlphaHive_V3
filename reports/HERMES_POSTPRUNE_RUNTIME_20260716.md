# Hermes post-prune runtime verification — 2026-07-16

**Evidence source:** Mimo `ARC-NEXT-RUNTIME-SCHEDULER-VERIFY-001`  
**Formal source:** `C:\Users\10639\Desktop\AlphaHive_V3_A_DATA_HEALTH_deliverables\agent_outputs\mimo\ARC-NEXT-RUNTIME-SCHEDULER-VERIFY-001.md`  
**Checkpoint prune cutoff:** `2026-07-16T06:37:22Z`  
**Latest pull report:** `pull_report_20260716_090607.md`, generated `2026-07-16T09:06:07Z`  
**Codex acceptance:** `ACCEPTED_WITH_ADVISORY_CORRECTION`

## Conclusion

Post-prune runtime continuity is verified: the Hermes job is enabled and
scheduled, a run occurred 190 seconds after the prune, the next run is in the
future, and no lock file is present. The checkpoint retains 59 keys in each of
its eight partitions (472 keys total).

This is not a clean four-dimension freshness result. The latest run recorded
transport-level SSL failures and partial stale results:

| Dimension | Fresh | Stale | Failures | Failed symbols / cause |
|---|---:|---:|---:|---|
| klines | 56/59 | 3 | 3 | ORDIUSDT, TRUMPUSDT, CRVUSDT / SSL |
| funding | 57/59 | 2 | 2 | FILUSDT, LDOUSDT / SSL |
| oi | 59/59 | 0 | 0 | — |
| taker_buysell | 58/59 | 1 | 1 | LDOUSDT / SSL |

The scheduler registry reports `last_status=error` because the failed engines
returned non-zero status; this is consistent with the pull report and does not
indicate a scheduler stall. No process, scheduler, checkpoint, database,
Parquet, credential, or repository file was changed during the verification.

## Required follow-up

1. Observe the next scheduled pull and record whether the six SSL failures
   recover; keep the runtime state `PARTIAL / TRANSIENT_TRANSPORT_FAILURE`
   until then.
2. Do not restart or modify Hermes without an explicit Owner instruction.
3. Keep OI/funding quantile trigger ignition, Paper `ALLOW`, source changes and
   data gap-fill parked.
