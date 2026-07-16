# ARC-DATA-HISTORY-FINAL-AUDIT-001 - independent audit of historical-data research

**agent:** DeepSeek V4
**task_id:** ARC-DATA-HISTORY-FINAL-AUDIT-001
**tier:** T1 / read-only independent evidence audit
**output:** `C:\Users\10639\Desktop\AlphaHive_V3_A_DATA_HEALTH_deliverables\agent_outputs\deepseek\ARC-DATA-HISTORY-FINAL-AUDIT-001_INDEPENDENT_REVIEW.md`

## Required reading

1. `G:\Quant test\AGENTS.md`
2. `G:\Quant test\AlphaHive_V3\AGENTS.md`
3. `G:\Quant test\AlphaHive_V3\PROJECT_REQUIRED_READING.md`
4. `G:\Quant test\AlphaHive_V3\PROJECT_CONSTITUTION.md`
5. `G:\Quant test\AlphaHive_V3\AGENT_ORCHESTRATION_PROTOCOL.md`
6. `G:\Quant test\AlphaHive_V3\OWNER_APPROVALS.md`
7. `G:\Quant test\AlphaHive_V3\OWNER_DECISIONS_NEEDED.md`
8. `G:\Quant test\AlphaHive_V3\agent_tasks\sonnet__codex__arc_data_history_research_002.md`
9. This task file

## Required inputs

- `C:\Users\10639\Desktop\AlphaHive_V3_A_DATA_HEALTH_deliverables\agent_outputs\sonnet\ARC-DATA-HISTORY-RESEARCH-002.md`
- `G:\Quant test\AlphaHive_V3\reports\DATA_CANONICAL_COVERAGE_20260715.md`
- `G:\Quant test\AlphaHive_V3\reports\BINANCE_PULL_OPERATIONS_20260715.md`
- `G:\Quant test\AlphaHive_V3\config\data_contracts.yaml`
- `G:\Quant test\AlphaHive_V3\config\universe.json`
- Official Binance public-data documentation and the exact archive/index URLs cited by the research report.

## Objective

Independently verify whether the research report supports its claims about Binance Vision/S3 historical Klines, Open Interest, and taker buy/sell data, especially the claimed `2020-09-01` start date and the proposed `2020-09-01` full-feature cutoff.

## Required checks

1. Provenance: determine whether the report's `agent=Sonnet` header is trustworthy when the user reports a Sonnet-to-Gemini handoff. Mark mixed authorship as a provenance limitation if it cannot be reconstructed.
2. Verify exact archive paths, object naming, symbol coverage, first available date, interval/granularity, and whether the cited files are actually downloadable.
3. Separate Klines evidence from OI/taker metrics evidence; do not accept a Klines archive as proof that metrics archives exist.
4. Verify whether OI and taker metrics are historical bulk archives or only rolling REST/API data.
5. Check checksum/reproducibility claims and note whether checksums are SHA-256, CRC, or another format.
6. Reconcile the claimed dates against the local coverage report and identify any unsupported date or universe extrapolation.
7. Assess whether `2020-09-01` is safe as a full-feature replay cutoff, or whether the correct result must be symbol-specific / dimension-specific.
8. List exactly which conclusions remain `UNVERIFIED`, which Owner decisions are T3, and whether any backfill authorization can be issued. No authorization may be inferred from the report.

## Hard boundaries

- Read-only audit only. Do not download bulk archives, run a backfill, modify Parquet/DB, change scheduler, change contracts, or access credentials.
- No live pull and no trading/Paper changes.
- Use official Binance sources for factual verification where possible. If an official object cannot be directly verified, mark it `UNVERIFIED` rather than relying on a search snippet or filename pattern.
- Do not treat the prior Gemini/Agy report, Sonnet report, or any chat summary as independent proof.

## Deliverable format

Write only to the specified Desktop output path. The report header must contain `agent=deepseek_v4`, `task_id=ARC-DATA-HISTORY-FINAL-AUDIT-001`, UTC timestamp, exact inputs/sources read, provenance assessment, unresolved items, and one final verdict:

- `PASS_FOR-DATA-HISTORY-RESEARCH`
- `PARK`
- `FAIL`

Provide file/URL/date evidence for every checked claim. If the `2020-09-01` metrics claim cannot be independently proven, the final verdict must be `PARK`.
