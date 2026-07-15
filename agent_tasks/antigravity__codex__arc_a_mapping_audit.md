# ARC-A-MAP-AUDIT-001 — independent Binance mapping boundary audit

**agent:** antigravity  
**tier:** T1 / read-only  
**output:** `C:\Users\10639\Desktop\AlphaHive_V3_A_DATA_HEALTH_deliverables\agent_outputs\antigravity\ARC-A-MAP-AUDIT-001_INDEPENDENT_REVIEW.md`

## Required reading

1. `G:\Quant test\AlphaHive_V3\AGENTS.md`
2. `G:\Quant test\AlphaHive_V3\PROJECT_REQUIRED_READING.md`
3. This task file.

## Objective

Independently audit whether M-A1 remains a pure, contract-safe mapping layer.  Verify funding unit conversion, OI semantics, and the absence of an unauthorized scanner-source switch.

## Required inputs

- `G:\Quant test\AlphaHive_V3\harness\lib\binance_free_mapping.py`
- `G:\Quant test\AlphaHive_V3\harness\lib\funding_normalize.py`
- `G:\Quant test\AlphaHive_V3\config\data_contracts.yaml`
- `G:\Quant test\AlphaHive_V3\scripts\02_scan_anomalies.py`
- `G:\Quant test\AlphaHive_V3\tests\test_binance_free_mapping.py`
- `G:\Quant test\AlphaHive_V3\tests\test_scan_anomalies.py`
- commit `d1d127c` diff and its direct parent diff context.

## Required findings

1. Prove or disprove that Binance decimal funding is converted to the contract raw-percent unit exactly once and remains reversible under existing normalization.
2. Prove or disprove that OI mapping preserves the unit boundary and does not substitute notional OI for absolute OI.
3. Prove or disprove that M-A1 reads no database, writes no database, changes no scanner source, and changes no T3 trigger/paper behavior.
4. Identify any missing negative regression that could allow a future source switch or unit ambiguity.  Recommend tests only; do not write code.
5. Give `PASS_FOR_M-A2_READINESS`, `PARK`, or `FAIL` with line-level evidence.

## Hard boundaries

- Read-only.  No repository, Desktop deliverable, database, scheduler, or network modification.
- Do not audit or propose trigger activation, paper `ALLOW`, credentials, or trading.

## Deliverable format

Header must contain `agent=antigravity`, `task_id=ARC-A-MAP-AUDIT-001`, UTC timestamp, all inputs read, verdict, and unresolved items.  Preserve raw evidence and state every inference explicitly.
