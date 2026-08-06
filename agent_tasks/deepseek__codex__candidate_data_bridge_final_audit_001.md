# CANDIDATE-DATA-BRIDGE-FINAL-AUDIT-001

**agent:** DeepSeek V4  
**tier:** T1/T2 independent final audit  
**exact Desktop output:** `C:\Users\10639\Desktop\AlphaHive_V3_A_DATA_HEALTH_deliverables\agent_outputs\deepseek\CANDIDATE-DATA-BRIDGE-FINAL-AUDIT-001.md`

## Objective

Independently audit Codex's non-active candidate-price bridge preparation.
Determine whether it correctly implements the confirmed Binance-over-CoinGlass
price precedence and remains unable to change a scanner, raw database,
publication pointer, trigger, Paper state, notification, credentials, or any
trading path.

## Required reading

Read in order:

1. `G:\Quant test\AGENTS.md`
2. `G:\Quant test\AlphaHive_V3\AGENTS.md`
3. `G:\Quant test\AlphaHive_V3\PROJECT_REQUIRED_READING.md` and all files it requires
4. `G:\Quant test\AlphaHive_V3\PROJECT_OPERATING_PLAYBOOK.md`
5. This task file

## Required inputs

- `OWNER_APPROVALS.md`
- `OWNER_DECISIONS_NEEDED.md`
- `harness/lib/candidate_data_bridge.py`
- `harness/lib/canonical_data.py`
- `tests/test_candidate_data_bridge.py`
- `tests/test_canonical_data.py`
- `reports/CANDIDATE_DATA_BRIDGE_PRECONDITIONS_20260718.md`
- `reports/CANDIDATE_DATA_BRIDGE_ACCEPTANCE_20260718.md`
- `reports/OWNER_DECISION_CONFIRMATION_TEMPLATE_20260718.md`
- `config/data_contracts.yaml`
- `scripts/02_scan_anomalies.py`
- the repository diff for the listed files

## Required checks

1. Exact Binance field mapping uses verified `quote_volume`; it does not invent
   `quote_asset_volume`.
2. On a same-symbol/timestamp overlap, Binance is selected and divergent bars
   are counted, not silently merged.
3. The bridge rejects malformed data and no completed price rows; it preserves
   gap intervals and never interpolates.
4. The bridge filters uncompleted bars using the declared one-hour semantics.
5. It has no code path that reads/writes a configured database, switches the
   scanner path, writes a publication pointer, changes a threshold, enables a
   derivative trigger/Paper status, sends a notification, accesses a secret,
   makes a network request, or trades.
6. The Owner approval is recorded narrowly and the gap recommendation remains
   explicitly `PARK`, not silently active.
7. Reproduce focused tests and a relevant full-project test run; report exact
   commands and counts.

## Hard boundaries

- Read-only audit only. Do not modify repository, configuration, raw data,
  results, Desktop inputs, scheduler, credentials, browser, external systems
  or the designated output after writing it.
- No network/API/provider calls, data pull, backfill, source switch, Paper,
  OwnerDecision, notification, trigger ignition or trading action.
- If any required evidence is missing or contradictory, use `PARK` or `FAIL`;
  do not infer authority.

## Deliverable

Write only the exact Desktop output. Include agent, task id, UTC timestamp,
exact inputs read, one verdict (`PASS_FOR_NON_ACTIVE_BRIDGE`, `PARK`, or
`FAIL`), file/line evidence for every check, tests run, unresolved items and
`SELF_CHECK`. Return the exact path, verdict, evidence summary and unresolved
items in chat.
