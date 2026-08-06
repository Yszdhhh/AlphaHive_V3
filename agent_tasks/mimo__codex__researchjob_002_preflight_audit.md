# RESEARCHJOB-MVP-002-PREFLIGHT-AUDIT-001

**task_id:** `RESEARCHJOB-MVP-002-PREFLIGHT-AUDIT-001`  
**agent:** Mimo external agent proxy  
**tier:** T1 read-only prerequisite and fixture audit  
**repository write authority:** Codex only  
**exact Desktop output:** `C:\Users\10639\Desktop\AlphaHive_V3_A_DATA_HEALTH_deliverables\agent_outputs\mimo\RESEARCHJOB-MVP-002-PREFLIGHT-AUDIT-001.md`

## Objective

Independently audit the accepted 001B store for MVP 002 prerequisites. Identify
exactly what exists, what can be reused and what Codex must implement for
immutable versioned verification/assessment. This is an audit only; do not
implement 002 or mutate repository, fixtures or authoritative stores.

## Required reading

Read the shared materials in the exact order required by
`G:\Quant test\AlphaHive_V3\PROJECT_REQUIRED_READING.md`, then read this task,
the research orchestration contract, the 001B Codex handoff, the two accepted
001B long-goal reports, current ResearchJob server files and current
`tests/test_research_jobs.py`.

## Checks

- Establish hashes for ResearchJob server/test files and authoritative
  `signal_review/latest.json` before and after read-only checks.
- Map the current Job/evidence/import/event/pointer/quarantine structure and
  identify the exact extension points for `verification/vNNNN.json` and
  `assessment/vNNNN.json`.
- Identify valid temporary fixtures for a job with accepted evidence; do not
  import authoritative evidence.
- Audit required binding fields, ordered evidence-set hash feasibility,
  version allocation, duplicate/idempotency, tamper detection, crash recovery
  and concurrent publication risks.
- Define negative cases for missing/incorrect predecessor hashes, evidence-set
  drift, record/job mismatch, invalid state, duplicate versions, corrupted
  version artifacts and no-mutation of quality/Owner/Paper/trading paths.
- Separate PASS, ADVISORY and PARK evidence; list any true Owner-only decision.

## Hard boundaries and output

No repository/config/test/fixture writes; no external providers or source
fetches; no scheduler/database/checkpoint/outbox change; no Owner/Paper/trade
operation. Write only the exact Desktop report. Its header must include agent,
task ID, UTC, inputs, hashes, status and unresolved items, followed by
file:line evidence, a PASS/ADVISORY/PARK matrix, prioritized Codex worklist,
test matrix and `SELF_CHECK`.
