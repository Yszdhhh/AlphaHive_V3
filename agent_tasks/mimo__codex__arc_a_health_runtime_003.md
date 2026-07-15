# ARC-A-HEALTH-003 - latest Binance runtime health reconciliation

**agent:** Mimo
**task_id:** ARC-A-HEALTH-003
**tier:** T1 / read-only runtime reconciliation
**output:** `C:\Users\10639\Desktop\AlphaHive_V3_A_DATA_HEALTH_deliverables\agent_outputs\mimo\ARC-A-HEALTH-003_RUNTIME_RECON.md`

## Required reading

Read in this order:

1. `G:\Quant test\AGENTS.md`
2. `G:\Quant test\AlphaHive_V3\AGENTS.md`
3. `G:\Quant test\AlphaHive_V3\PROJECT_REQUIRED_READING.md`
4. `G:\Quant test\AlphaHive_V3\OWNER_APPROVALS.md`
5. `G:\Quant test\AlphaHive_V3\KNOWN_LIMITATIONS.md`
6. This task file

## Objective

Reconcile the latest Binance Hermes runtime after the most recent non-green pull. Determine whether the OI/Taker/Kline failures are transient transport failures, stale checkpoint behavior, or a logic defect. This is an evidence task only; do not repair anything.

## Required inputs

- `C:\Users\10639\Desktop\加密\binance_free_db\reports\pull_report_*.md` (latest five reports, sorted by timestamp)
- `C:\Users\10639\Desktop\加密\binance_free_db\checkpoint_1h.json`
- `C:\Users\10639\AppData\Local\hermes\cron\jobs.json`
- `C:\Users\10639\AppData\Local\hermes\scripts\binance_data_config.py`
- `C:\Users\10639\AppData\Local\hermes\scripts\binance_data_puller.py`
- `C:\Users\10639\AppData\Local\hermes\scripts\binance_klines_engine.py`
- `C:\Users\10639\AppData\Local\hermes\scripts\binance_oi_engine.py`
- `C:\Users\10639\AppData\Local\hermes\scripts\binance_taker_engine.py`
- `G:\Quant test\AlphaHive_V3\reports\BINANCE_PULL_OPERATIONS_20260715.md`
- `G:\Quant test\AlphaHive_V3\reports\BINANCE_PULL_RUNTIME_MANIFEST_20260715.md`
- `G:\Quant test\AlphaHive_V3\config\universe.json`

## Required checks

1. Latest run status and per-dimension freshness for all 59 effective symbols.
2. Exact failed/stale symbols, retry counts, and checkpoint fail counters.
3. Whether checkpoints advance only after successful writes and whether the lock/scheduler state is safe.
4. Whether the latest failures are transport/rate-limit/TLS symptoms or a deterministic code/config error.
5. Whether the runtime script hashes still match the manifest.
6. Minimal non-mutating recommendations for the next Codex repair, explicitly separating facts from inference.

## Hard boundaries

- Read-only only. Do not trigger a pull, run a retry, modify the database, parquet files, checkpoint, lock, scheduler, or Hermes scripts.
- Do not access credentials, CoinGlass, or external APIs.
- Do not change the candidate universe, thresholds, Paper status, or data-source policy.
- If any required input is missing, report `PARK` rather than guessing.

## Deliverable format

Write only to the specified Desktop output path. The report header must contain `agent=Mimo`, `task_id=ARC-A-HEALTH-003`, UTC timestamp, exact inputs read, status (`GREEN`, `UNVERIFIED`, or `PARK`), and unresolved items. Include a concise evidence table and distinguish current facts from recommendations.
