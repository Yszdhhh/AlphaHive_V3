# ARC-A-HEALTH-001 — Binance runtime health reconciliation

**agent:** Mimo  
**tier:** T1 / read-only  
**output:** `C:\Users\10639\Desktop\AlphaHive_V3_A_DATA_HEALTH_deliverables\agent_outputs\mimo\ARC-A-HEALTH-001_RUNTIME_HEALTH.md`

## Required reading

1. `G:\Quant test\AlphaHive_V3\AGENTS.md`
2. `G:\Quant test\AlphaHive_V3\PROJECT_REQUIRED_READING.md`
3. This task file.

## Objective

Produce one evidence-based snapshot of the currently running Binance public-data service.  Reconcile the latest pull report, checkpoint, file freshness, and Hermes schedule.  Do not make a recommendation to change a source, frequency, credential, proxy, or database.

## Allowed inputs (read-only)

- `C:\Users\10639\AppData\Local\hermes\scripts\binance_data_puller.py`
- `C:\Users\10639\AppData\Local\hermes\scripts\binance_data_config.py`
- `C:\Users\10639\Desktop\加密\binance_free_db\checkpoint_1h.json`
- `C:\Users\10639\Desktop\加密\binance_free_db\reports\pull_report_*.md`
- `C:\Users\10639\Desktop\加密\binance_free_db\raw_1h\` and `raw_8h\`
- `G:\Quant test\AlphaHive_V3\config\universe.json`
- `G:\Quant test\AlphaHive_V3\reports\BINANCE_PULL_OPERATIONS_20260715.md`

## Required checks

1. Identify the newest report by timestamp and quote its per-engine outcome, elapsed time, and dimensional freshness table.
2. Recompute 40-symbol coverage from actual parquet filenames for klines, raw funding, OI, and taker data.  State the exact set of symbols missing or stale per dimension.
3. Read the checkpoint failure counters and report every non-zero Taker, OI, Klines, or Funding counter with its checkpoint UTC timestamp.
4. Read Hermes cron status/list only.  Record schedule, last status, next run, and whether a pull lock file exists.  Do not run the puller, a manual retry, or any network request.
5. Reconcile any discrepancy between engine log summaries and report freshness counters.  Label unknowns `UNVERIFIED`; do not infer success from an exit code alone.

## Hard boundaries

- Do not modify the repository, Hermes scripts, scheduler, database, checkpoints, parquet files, locks, logs, or configuration.
- Do not call Binance, CoinGlass, or any network endpoint.
- Do not select a different task, suggest a trigger, or discuss paper/trading changes.

## Deliverable format

Header must contain `agent=mimo`, `task_id=ARC-A-HEALTH-001`, UTC timestamp, every input path read, `GREEN`/`PARK`/`UNVERIFIED`, and unresolved items.  Include a compact evidence table and exact commands used.  Raw evidence only; no invented remediation plan.
