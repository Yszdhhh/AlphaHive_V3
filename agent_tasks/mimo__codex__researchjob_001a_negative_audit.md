# RESEARCHJOB-MVP-001A-NEGATIVE-AUDIT-001 — Mimo

**task_id:** `RESEARCHJOB-MVP-001A-NEGATIVE-AUDIT-001`  
**tier:** T1 read-only post-implementation audit  
**agent:** Mimo  
**dependency:** Execute only after Codex publishes the FIX-03 candidate and its exact test command/result. Do not self-select this task before that handoff.  
**repository write authority:** Codex only  
**exact Desktop output:** `C:\Users\10639\Desktop\AlphaHive_V3_A_DATA_HEALTH_deliverables\agent_outputs\mimo\RESEARCHJOB-MVP-001A-NEGATIVE-AUDIT-001.md`

## Objective

Independently audit the Codex FIX-03 ResearchJob 001A implementation for
negative paths, durability and fail-closed behavior. This is not a code-change
task and must not expand into evidence import, PaperPlan or provider calls.

## Required reading (in order)

1. `G:\Quant test\AGENTS.md`
2. `G:\Quant test\AlphaHive_V3\AGENTS.md`
3. `G:\Quant test\AlphaHive_V3\PROJECT_REQUIRED_READING.md`
4. `G:\Quant test\AlphaHive_V3\PROJECT_OPERATING_PLAYBOOK.md`
5. `G:\Quant test\AlphaHive_V3\agent_tasks\README.md`
6. `G:\Quant test\AlphaHive_V3\reports\RESEARCHJOB_001A_FIX02_ACCEPTANCE_20260713.md`
7. `G:\Quant test\AlphaHive_V3\prompts\researchjob_mvp_001a_fix_01_gemini.md`
8. The Codex FIX-03 handoff report and changed paths supplied in the dispatch message.

## Audit scope

- Exact routes: `POST /api/research/jobs` and
  `GET /api/research/jobs/{job_id}` only for 001A.
- Server-generated path-safe `job_` IDs and complete record/job validation,
  including traversal and Windows reserved-name cases.
- Canonical candidate package hash and pointer integrity.
- Exactly two initial events: `RESEARCH_JOB_CREATED` then
  `AWAITING_EVIDENCE`, with complete hash-chain validation.
- Atomic publication, fsync/failure cleanup, restart recovery and
  cross-process same-key idempotency.
- `quality_status=BLOCK` remains research/Owner-review capable but
  `paper_plan_capability=BLOCK`.
- No writes to authoritative signal-review inputs/results during tests.

## Prohibited actions

- Do not edit the repository, fixtures, tests, database, Parquet, scheduler,
  credentials or `_bus/`.
- Do not run a real pull, create evidence imports, create Paper Plans, change
  Paper eligibility, activate triggers or call external providers.
- Do not accept the maker report solely from its summary; inspect the actual
  changed paths and test evidence.

## Required report shape

Write only the exact Desktop report. Include `agent`, exact `task_id`, UTC
timestamp, all inputs, test commands actually run, PASS/ADVISORY/PARK results,
unresolved items, provenance boundary and `SELF_CHECK`. Final status must be
`GREEN`, `PARK` or `UNVERIFIED`; do not claim Owner acceptance.
