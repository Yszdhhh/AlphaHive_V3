# RESEARCHJOB-MVP-001B-GEMINI-LONG-GOAL-REVIEW-001

**task_id:** `RESEARCHJOB-MVP-001B-GEMINI-LONG-GOAL-REVIEW-001`  
**agent:** Gemini external agent proxy, long-thread goal mode  
**tier:** T1/T2 read-only architecture, security and implementation review  
**repository write authority:** Codex only  
**exact Desktop output:** `C:\Users\10639\Desktop\AlphaHive_V3_A_DATA_HEALTH_deliverables\agent_outputs\antigravity\RESEARCHJOB-MVP-001B-GEMINI-LONG-GOAL-REVIEW-001.md`

## Long-thread goal

Independently follow ResearchJob MVP 001B from the accepted architecture into
implementation acceptance. Continue until every in-scope contract item is
either supported by reproducible evidence or explicitly marked `PARK` with the
missing evidence and next safe check. Do not stop at a summary and do not
modify either repository tree.

The goal is to catch design drift while Codex remains the sole writer. Review
the actual current files each time; never infer implementation from Codex chat
or an older report.

## Required reading

Read in the exact order mandated by:

1. `G:\Quant test\AGENTS.md`
2. `G:\Quant test\AlphaHive_V3\AGENTS.md`
3. `G:\Quant test\AlphaHive_V3\PROJECT_REQUIRED_READING.md` and every file it lists, in order
4. `G:\Quant test\AlphaHive_V3\PROJECT_OPERATING_PLAYBOOK.md`
5. `G:\Quant test\AlphaHive_V3\agent_tasks\README.md`
6. This task file
7. `G:\Quant test\AlphaHive_V3\config\research_orchestration_contract.yaml`
8. `G:\Quant test\AlphaHive_V3\reports\RESEARCHJOB_001A_FIX03_CODEX_HANDOFF_20260716.md`
9. `C:\Users\10639\Desktop\AlphaHive_V3_A_DATA_HEALTH_deliverables\agent_outputs\antigravity\RESEARCHJOB-MVP-001B-GOAL-ARCH-001.md`
10. `C:\Users\10639\Desktop\AlphaHive_V3_A_DATA_HEALTH_deliverables\agent_outputs\mimo\RESEARCHJOB-MVP-001B-PREFLIGHT-AUDIT-001.md`
11. `G:\Quant test\AlphaHive_V3\reports\RESEARCHJOB_001B_CODEX_HANDOFF_20260717.md`
12. Current `G:\Quant test\alpha_hive\server\research_job_*.py`
13. Current `G:\Quant test\AlphaHive_V3\tests\test_research_jobs.py`

## Mandatory review decisions

- Confirm the route is exactly `POST /api/research/jobs/{job_id}/evidence/import`.
- Resolve canonical bundle-hash compatibility with the existing normalizer
  while keeping evidence-file bytes and normalized content hashes distinct.
- Verify provider neutrality; reject any Grok-only category or source-job
  requirement leaking into the generic import boundary.
- Verify Job/bundle/record binding, historical and prospective cutoff rules,
  missing-cutoff fail-closed behavior, maximum size/depth/count and path safety.
- Verify every attempt status: `ACCEPTED`, `REJECTED_SCHEMA`, `REJECTED_HASH`,
  `REJECTED_CUTOFF`, `REJECTED_RECORD_MISMATCH`, `DUPLICATE`.
- Verify rejected imports persist an attempt and append
  `EVIDENCE_IMPORT_REJECTED` without changing Job state.
- Verify only an accepted import may append `EVIDENCE_IMPORTED` and move the
  Job to `EVIDENCE_IMPORTED`. Do not mislabel import success as
  `RESEARCH_TASK_EXPORTED`.
- Verify quarantine, immutable publication, pointer coverage, event-chain
  integrity, same-content concurrency and recoverable partial commits.
- Verify no rejected or accepted import mutates signal review, quality gates,
  Owner decisions, Paper capability, notification delivery or trading paths.
- Produce an exact failure-injection oracle and identify any contract ambiguity
  that truly requires Owner approval rather than inventing a default.

## Required output

The report header must include agent identity, exact task ID, UTC timestamp,
all inputs and hashes, status (`GREEN`, `PARK`, or `UNVERIFIED`) and unresolved
items. Include:

1. Contract-to-code traceability table with file:line evidence.
2. State/event decision table.
3. Hash/cutoff/binding decision table.
4. Failure, crash and concurrency matrix.
5. Test-oracle matrix and observed results if tests are available.
6. Scope-boundary audit.
7. Findings by severity, with no unsupported claims.
8. `SELF_CHECK` covering every item above.

## Hard boundaries

No repository edits, external provider/API calls, credentials, source changes,
database or scheduler mutation, trigger ignition, Paper `ALLOW`, Owner
signature, notification delivery or trading action. The Desktop report is the
only allowed output.
