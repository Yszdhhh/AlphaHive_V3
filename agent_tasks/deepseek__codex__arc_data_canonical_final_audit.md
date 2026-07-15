# ARC-DATA-CANONICAL-FINAL-AUDIT-001 - additive dual-source adapter final audit

**agent:** DeepSeek V4
**task_id:** ARC-DATA-CANONICAL-FINAL-AUDIT-001
**tier:** T1 / read-only independent final audit
**output:** `C:\Users\10639\Desktop\AlphaHive_V3_A_DATA_HEALTH_deliverables\agent_outputs\deepseek\ARC-DATA-CANONICAL-FINAL-AUDIT-001_INDEPENDENT_REVIEW.md`

## Required reading

1. `G:\Quant test\AGENTS.md`
2. `G:\Quant test\AlphaHive_V3\AGENTS.md`
3. `G:\Quant test\AlphaHive_V3\PROJECT_REQUIRED_READING.md`
4. `G:\Quant test\AlphaHive_V3\PROJECT_CONSTITUTION.md`
5. `G:\Quant test\AlphaHive_V3\AGENT_ORCHESTRATION_PROTOCOL.md`
6. `G:\Quant test\AlphaHive_V3\OWNER_APPROVALS.md`
7. `G:\Quant test\AlphaHive_V3\OWNER_DECISIONS_NEEDED.md`
8. This task file

## Objective

Independently audit Codex's additive CoinGlass/Binance canonical adapter and
the Binance reliability hardening. Confirm that the work remains read-only
with respect to production source selection and trading behavior, and that
unit/schema provenance is explicit.

## Required inputs

- `G:\Quant test\AlphaHive_V3\harness\lib\canonical_data.py`
- `G:\Quant test\AlphaHive_V3\scripts\100_dual_source_coverage.py`
- `G:\Quant test\AlphaHive_V3\tests\test_canonical_data.py`
- `G:\Quant test\AlphaHive_V3\harness\lib\binance_free_mapping.py`
- `G:\Quant test\AlphaHive_V3\tests\test_binance_free_mapping.py`
- `G:\Quant test\AlphaHive_V3\config\data_contracts.yaml`
- `G:\Quant test\AlphaHive_V3\config\universe.json`
- `G:\Quant test\AlphaHive_V3\scripts\01_build_universe.py`
- `G:\Quant test\AlphaHive_V3\scripts\02_scan_anomalies.py`
- `G:\Quant test\AlphaHive_V3\reports\DATA_CANONICAL_COVERAGE_20260715.md`
- `G:\Quant test\AlphaHive_V3\reports\BINANCE_PULL_OPERATIONS_20260715.md`
- `G:\Quant test\AlphaHive_V3\reports\BINANCE_PULL_RUNTIME_MANIFEST_20260715.md`
- `C:\Users\10639\AppData\Local\hermes\scripts\binance_klines_engine.py`
- `C:\Users\10639\AppData\Local\hermes\scripts\binance_oi_engine.py`
- `C:\Users\10639\AppData\Local\hermes\scripts\binance_taker_engine.py`
- repository diff and commit containing this change

## Required checks

1. Canonical adapters accept the verified CoinGlass/Binance schemas and reject missing or contradictory fields without guessing.
2. Funding preserves decimal values, derives the contract-compatible percent view explicitly, and treats equal Binance raw/decimal columns as aliases rather than proof of conversion.
3. OI absolute units remain `UNDECLARED`; no unit inference is introduced.
4. Taker ratio provenance distinguishes source-provided and arithmetic-derived values.
5. Coverage report is read-only and does not switch scanner paths or overwrite raw stores.
6. Klines/OI retry hardening uses bounded existing pacing and non-zero failure exits; checkpoint advancement remains write-success-only.
7. Scope: no trigger, threshold, Paper eligibility, credential, source-path switch, or trading behavior change.
8. Tests and report evidence are present and reproducible.

## Hard boundaries

- Read-only audit. Do not modify repository, Desktop outputs, database, parquet, scheduler, Hermes scripts, credentials, or browser state.
- No network calls, no manual pull, no backfill, and no source switch.
- If a required input or exact task/output path is missing, report `PARK`.

## Deliverable format

The report header must contain `agent=deepseek_v4`, `task_id=ARC-DATA-CANONICAL-FINAL-AUDIT-001`, UTC timestamp, exact inputs read, final verdict, and unresolved items. Use exactly one final verdict: `PASS_FOR-DATA-CANONICAL-ADAPTER`, `PARK`, or `FAIL`. Provide file/line evidence for all eight checks.
