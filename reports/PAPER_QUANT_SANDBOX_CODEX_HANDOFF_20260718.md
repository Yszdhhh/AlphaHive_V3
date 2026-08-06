# Paper/quant sandbox Codex handoff (2026-07-18)

**implementation slice:** `PAPER-QUANT-SANDBOX-CODEX-IMPLEMENTATION-001`  
**architecture input:** `PAPER-QUANT-SANDBOX-GEMINI-GOAL-ARCH-001`  
**status:** `ACCEPTED / GREEN — isolated local dry-run only`

## Visible capabilities now available

`harness.lib.paper_plan_engine.export_research_job_prompt(job_id, package)`
returns a deterministic provider-neutral local export with an input hash and
`provider_calls=false`.

`harness.lib.paper_plan_engine.build_paper_plan(job, owner_decision, preset, bars)`
creates a content-addressed `paper_plan_v1` only for a synthetic
`PROSPECTIVE_LIVE`/ALLOW job with an approved preset and verified fixture Owner
context. Historical/BLOCK BONK fails closed.

`harness.lib.offline_execution_simulator.run_simulation(plan, bars, ...)`
executes only local bars, applies deterministic adverse friction, sizes risk,
handles targets/stop/time exits, records event hashes and supports ledger
replay idempotency. It has no exchange or live order dependency.

## Acceptance evidence

- fixtures: `harness/fixtures/paper_allow.json` and
  `harness/fixtures/paper_bonk_block.json`;
- focused: `12 passed`;
- full regression: `370 passed, 15 subtests passed`;
- no authoritative research job, signal review, credentials or external state
  changed.

## Next stage

1. Use the synthetic ALLOW fixture to expose a local demo/report or UI view of
   plan → fills → PnL; this remains T1/T2 and can proceed without a real symbol.
2. Continue the separate candidate-production diagnostic. The current real
   inventory still has only the historical BONK BLOCK fixture.
3. Do not connect the simulator to OwnerDecision/PaperPlan production stores
   until the Owner supplies confirmation text, identity/authentication and
   immutable preset binding, and a prospective ALLOW candidate exists.
