# CANONICAL-PRICE-SCANNER-ACTIVATION-FINAL-AUDIT-001

**agent:** DeepSeek V4  
**tier:** T3 Owner-approved implementation, independent read-only final audit  
**exact Desktop output:** `C:\Users\10639\Desktop\AlphaHive_V3_A_DATA_HEALTH_deliverables\agent_outputs\deepseek\CANONICAL-PRICE-SCANNER-ACTIVATION-FINAL-AUDIT-001.md`

## Objective

Independently audit the Owner-approved activation of the canonical **price**
snapshot as the scanner input. Verify that the activation is hash-checked,
atomic and fail-closed; uses Binance-over-CoinGlass precedence with the
confirmed bounded gap policy; and does not expand into derivative activation,
Paper, trigger ignition, notification, credentials or trading.

## Required reading

1. `G:\Quant test\AGENTS.md`
2. `G:\Quant test\AlphaHive_V3\AGENTS.md`
3. `G:\Quant test\AlphaHive_V3\PROJECT_REQUIRED_READING.md` and all required files
4. `G:\Quant test\AlphaHive_V3\PROJECT_OPERATING_PLAYBOOK.md`
5. This task file

## Required inputs

- `OWNER_APPROVALS.md`, `OWNER_DECISIONS_NEEDED.md`
- `config/data_contracts.yaml`, `config/universe.json`
- `harness/lib/candidate_data_bridge.py`
- `harness/lib/canonical_price_snapshot.py`
- `scripts/102_build_canonical_price_snapshot.py`
- `scripts/02_scan_anomalies.py`
- `tests/test_candidate_data_bridge.py`
- `tests/test_canonical_price_snapshot.py`
- `tests/test_scan_anomalies.py`
- `harness/canonical_price_snapshots/current.json`
- the pointer-target manifest and a read-only inventory of its files
- `harness/runs/20260718_canonical_activation/run_manifest.json`
- `harness/runs/20260718_canonical_activation/candidates.csv`
- repository diff and the Codex activation handoff (if present)

## Required checks

1. Owner authority precisely covers source precedence, bounded gap policy and
   canonical price scanner activation, but does not cover excluded T3 areas.
2. Publisher uses a versioned staging directory, fsync, atomic replace,
   exclusive local lock and a hash-checked current pointer.
3. A tampered pointer, manifest or symbol parquet fails closed; no fallback to
   the CoinGlass kline path exists in the activated scanner.
4. Confirmed gap policy is implemented exactly: no interpolation; fresh 48h
   gaps block; historical 90d gaps allow no more than 4 per interval and 6 in
   total; metrics over a gap are not silently used.
5. `v0001` contains the expected effective price universe with Binance
   precedence/provenance, and the activation scan consumed canonical inputs.
6. Prospective derivative values remain disabled; no Paper, trigger,
   notification, secret, network, order or trading behavior was enabled.
7. Reproduce focused and full regression tests. Report exact commands/counts.

## Hard boundaries

- Read-only audit. Do not change repository, configs, raw databases, canonical
  snapshots, runs, ledger, scheduler, credentials, network state or browser.
- No network/API/provider calls, backfill, source publication, OwnerDecision,
  Paper, trigger ignition, notification delivery or trading.
- If source facts, manifest hashes, run evidence or authority are missing,
  contradictory or insufficient, return `PARK` or `FAIL` rather than guessing.

## Deliverable

Write only the exact Desktop output. Include agent, task id, UTC timestamp,
exact inputs, one verdict (`PASS_FOR_CANONICAL_PRICE_SCANNER_ACTIVATION`,
`PARK`, or `FAIL`), line/file evidence for every check, tests, unresolved
items, `SELF_CHECK`, and a boundary-mutation confirmation.
