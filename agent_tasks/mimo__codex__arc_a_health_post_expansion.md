# ARC-A-HEALTH-002 - Mimo post-expansion Binance runtime health

**agent:** Mimo
**task_id:** ARC-A-HEALTH-002
**tier:** T1 / read-only runtime reconciliation
**output:** `C:\Users\10639\Desktop\AlphaHive_V3_A_DATA_HEALTH_deliverables\agent_outputs\mimo\ARC-A-HEALTH-002_POST_EXPANSION.md`

Read `G:\Quant test\AlphaHive_V3\AGENTS.md`, `G:\Quant test\AlphaHive_V3\PROJECT_REQUIRED_READING.md`, and this task file first.

Reconcile the live Binance runtime after the universe expansion. Read-only inputs are `G:\Quant test\AlphaHive_V3\config\universe.json`, `C:\Users\10639\AppData\Local\hermes\scripts\binance_data_config.py`, the latest `C:\Users\10639\Desktop\加密\binance_free_db\reports\pull_report_20260715_033659.md`, checkpoint, parquet file counts, and the runtime manifest `G:\Quant test\AlphaHive_V3\reports\BINANCE_PULL_RUNTIME_MANIFEST_20260715.md`.

Verify: configured candidate count and benchmark separation; disabled symbols are not in live pull universe; all effective symbols have four dimensions; latest freshness; 90-day klines coverage sample; OI/Taker retention limits; lock/scheduler state. Do not trigger a pull, modify DB/scheduler, or access CoinGlass/credentials. Classify unknowns as `UNVERIFIED` and write only the specified Desktop report.
