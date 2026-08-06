# LOCAL-RESEARCH-PAPER-OUTBOX-FOUNDATION-FINAL-AUDIT-001

**Agent:** DeepSeek  
**Tier:** T1/T2 independent read-only final audit  
**Exact Desktop output:** `C:\Users\10639\Desktop\AlphaHive_V3_A_DATA_HEALTH_deliverables\agent_outputs\deepseek\LOCAL-RESEARCH-PAPER-OUTBOX-FOUNDATION-FINAL-AUDIT-001.md`

## Objective

Independently audit the new local-only candidate preview, immutable synthetic
PaperPlan ledger, and no-network notification Outbox. Confirm that the slice
can exercise lifecycle mechanics while being incapable of a real ResearchJob,
PaperPlan, Feishu delivery, trigger, or trade action.

## Required reading

1. `G:\Quant test\AGENTS.md`
2. `G:\Quant test\AlphaHive_V3\AGENTS.md`
3. `G:\Quant test\AlphaHive_V3\PROJECT_REQUIRED_READING.md` and every listed document
4. `G:\Quant test\AlphaHive_V3\PROJECT_OPERATING_PLAYBOOK.md`
5. This exact task file

## Required inputs

- `reports\LOCAL_RESEARCH_PAPER_OUTBOX_FOUNDATION_CODEX_HANDOFF_20260719.md`
- `harness\lib\candidate_research_job_bridge.py`
- `harness\lib\local_paper_plan_ledger.py`
- `harness\lib\local_notification_outbox.py`
- `harness\lib\paper_plan_engine.py`
- `harness\lib\offline_execution_simulator.py`
- all four named new test files under `harness\tests\`
- `harness\fixtures\paper_allow.json` and `paper_bonk_block.json`
- `config\research_orchestration_contract.yaml`, `config\paper_execution_presets.yaml`
- `OWNER_APPROVALS.md`, `OWNER_DECISIONS_NEEDED.md`

## Required checks

1. Candidate bridge is a preview only: it requires prospective/fresh/clean/
   no-lookahead inputs, rejects historical/stale/BLOCK/directional candidates,
   produces no job-directory write, and always blocks Paper capability.
2. Paper ledger takes an explicit root, verifies `paper_plan_v1` hash and
   `no_live_order_path`, writes immutable `vNNNN.json`, rejects a second
   active plan, has an event-hash chain and validates/recover staged state.
3. Outbox rejects all non-`local:` destinations and contains no HTTP, Feishu,
   credential, webhook, provider, bot or scheduler call. Verify idempotency,
   pending/sending/sent/dead lifecycle, interrupted-send recovery and tamper
   fail-closed behavior.
4. Integration test uses only the synthetic fixture and ends with
   `DRY_RUN_NO_NETWORK`; it does not create a real job or plan.
5. Confirm BONK/historical inputs still fail closed and no configuration,
   threshold, ownership or execution authority is changed.
6. Reproduce local focused tests and full regression, run whitespace/conflict
   checks, and hash `alpha_hive/results/signal_review/latest.json` before and
   after a controlled test run.

## Hard boundaries

- Read only: write only the exact Desktop report.
- Do not modify either repository, configuration, result state, job store,
  PaperPlan store, scheduler, credentials, browser, or any Desktop file other
  than the stated report.
- Do not invoke a ResearchJob route, create/import evidence, publish a
  PaperPlan, run a scanner/backfill, call a network/provider, configure Feishu,
  send a notification, enable a trigger or trade.
- If a stated claim is not reproducible, use `PARK` or `FAIL`; do not infer an
  authorization from the existence of a synthetic test fixture.

## Deliverable

Include agent/model, task ID, UTC time, exact inputs/hashes, a single verdict
(`PASS_FOR_LOCAL_RESEARCH_PAPER_OUTBOX_FOUNDATION`, `PARK`, or `FAIL`), every
required-check result, test command/count evidence, unresolved items,
`SELF_CHECK`, and an explicit mutation-boundary confirmation.
