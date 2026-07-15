# ARC-DATA-CANONICAL-RESEARCH-001 - CoinGlass/Binance canonical integration review

**agent:** antigravity / Gemini 3.1 Pro
**task_id:** ARC-DATA-CANONICAL-RESEARCH-001
**tier:** T1 / read-only independent architecture research
**output:** `C:\Users\10639\Desktop\AlphaHive_V3_A_DATA_HEALTH_deliverables\agent_outputs\antigravity\ARC-DATA-CANONICAL-RESEARCH-001.md`

## Required reading

Read in this order:

1. `G:\Quant test\AGENTS.md`
2. `G:\Quant test\AlphaHive_V3\AGENTS.md`
3. `G:\Quant test\AlphaHive_V3\PROJECT_REQUIRED_READING.md`
4. `G:\Quant test\AlphaHive_V3\PROJECT_CONSTITUTION.md`
5. `G:\Quant test\AlphaHive_V3\AGENT_ORCHESTRATION_PROTOCOL.md`
6. `G:\Quant test\AlphaHive_V3\OWNER_APPROVALS.md`
7. `G:\Quant test\AlphaHive_V3\OWNER_DECISIONS_NEEDED.md`
8. This task file

## Objective

Independently review a safe, additive design for combining the existing CoinGlass historical store and the Binance public-data store into a canonical AlphaHive snapshot layer. This is a design/research deliverable, not an implementation authorization.

## Required inputs

- `G:\Quant test\AlphaHive_V3\config\data_contracts.yaml`
- `G:\Quant test\AlphaHive_V3\config\universe.json`
- `G:\Quant test\AlphaHive_V3\harness\lib\funding_normalize.py`
- `G:\Quant test\AlphaHive_V3\harness\lib\binance_free_mapping.py`
- `G:\Quant test\AlphaHive_V3\tests\test_binance_free_mapping.py`
- `G:\Quant test\AlphaHive_V3\scripts\01_build_universe.py`
- `G:\Quant test\AlphaHive_V3\scripts\02_scan_anomalies.py`
- `G:\Quant test\AlphaHive_V3\scripts\06_build_return_tape.py`
- `G:\Quant test\AlphaHive_V3\scripts\07_historical_replay_sampler.py`
- `G:\Quant test\AlphaHive_V3\reports\DATA_REFRESH_RECON.md`
- `G:\Quant test\AlphaHive_V3\reports\BINANCE_PULL_OPERATIONS_20260715.md`
- `G:\Quant test\AlphaHive_V3\reports\BINANCE_PULL_RUNTIME_MANIFEST_20260715.md`
- `C:\Users\10639\Desktop\AlphaHive_V3_A_DATA_HEALTH_deliverables\agent_outputs\antigravity\ARC-DATA-HISTORY-RESEARCH-001.md`
- Representative read-only schema/date-range samples from:
  - `C:\Users\10639\Desktop\加密\coinglass_db\raw_1h\`
  - `C:\Users\10639\Desktop\加密\binance_free_db\raw_1h\`
  - `C:\Users\10639\Desktop\加密\binance_free_db\raw_8h\`

## Required checks

1. Compare CoinGlass and Binance schemas for klines, funding, OI, and taker data.
2. Identify unit, timestamp, resolution, symbol-identity, and field-semantic mismatches.
3. Evaluate the current contract `raw_unit: percent` and Binance decimal funding adapter; do not propose a silent unit flip.
4. Recommend source precedence for live, overlapping, and older historical periods, including how to preserve provenance.
5. Define overlap reconciliation tests and safe missing-data behavior, especially for OI absolute units and older ratio fields.
6. State whether an additive canonical layer can be built without changing scanner inputs, triggers, thresholds, Paper eligibility, credentials, or trading behavior.
7. List exact Owner decisions required before any source-path switch or historical backfill.

## Hard boundaries

- Read-only research only. Do not modify the repository, databases, parquet files, scheduler, Hermes scripts, or credentials.
- No external API calls, no CoinGlass login, no Binance credential access, and no batch backfill.
- Do not recommend replacing CoinGlass or changing `data_contracts.yaml` as an already-approved action.
- Do not infer OI absolute units from column names.
- Separate verified facts, inference, recommendation, and Owner decision. Mark unknowns `UNVERIFIED`.

## Deliverable format

Write only to the specified Desktop output path. The report header must contain `agent=antigravity_gemini_3_1_pro`, `task_id=ARC-DATA-CANONICAL-RESEARCH-001`, UTC timestamp, exact inputs read, status (`GREEN`, `UNVERIFIED`, or `PARK`), and unresolved items. Include a source-comparison table and a minimal recommended integration boundary.
