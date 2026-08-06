# Hermes scheduler continuity diagnosis

Generated: 2026-07-16 (Codex read-only diagnosis)

## Evidence read

- Scheduler registry: `C:\Users\10639\AppData\Local\hermes\cron\jobs.json`
- Runtime report used by Mimo: `C:\Users\10639\Desktop\加密\binance_free_db\reports\pull_report_20260715_090640.md`
- Post-prune checkpoint evidence: `reports/DATA_CHECKPOINT_PRUNE_20260716.md`
- Mimo post-prune report: `C:\Users\10639\Desktop\AlphaHive_V3_A_DATA_HEALTH_deliverables\agent_outputs\mimo\ARC-NEXT-RUNTIME-POSTPRUNE-001.md`

## Current observed state

| Field | Value |
|---|---|
| Job | `binance-hourly-pull` |
| Cron | `5 * * * *` |
| Enabled | `true` |
| State | `scheduled` |
| Last status | `ok` |
| Last run | `2026-07-15T17:06:40+08:00` |
| Next run recorded | `2026-07-15T18:05:00+08:00` (already past) |
| Registry mtime | `2026-07-15T09:31:26Z` |
| `tick.lock` / `scheduler.lock` at diagnosis | not present |

The registry remains enabled and reports the last run as `ok`, but its
`next_run_at` is stale and no pull report exists after the checkpoint prune at
`2026-07-16T06:37:22Z`. This confirms the Mimo classification:
`UNVERIFIED / WAITING_FOR_NEXT_HERMES_REPORT`.

## Boundary

- This diagnosis did not start, retry, stop or reconfigure Hermes.
- No scheduler, lock, database, parquet, checkpoint, log or credential file was modified.
- The post-prune runtime must remain `UNVERIFIED` until a later pull report is
  observed and independently reconciled.

## Next action

Codex/Owner must decide whether to inspect or restart the Hermes scheduler
process. Any restart or scheduler mutation is outside this read-only evidence
and is not performed here.

Status: `UNVERIFIED / RUNTIME_CONTINUITY_BLOCKER`

## Supersession note — 2026-07-16

This diagnosis captured the state before the next post-prune pull. It is kept
for historical provenance only. Mimo later verified
`pull_report_20260716_090607.md` after the prune, with the scheduler enabled
and scheduled and the next run in the future. The current status is recorded
in `reports/HERMES_POSTPRUNE_RUNTIME_20260716.md` as
`ACCEPTED_WITH_ADVISORY_CORRECTION`: continuity verified, six SSL transport
failures awaiting the next run.
