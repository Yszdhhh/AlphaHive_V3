# RESEARCHJOB-MVP-002-GROK-PREFLIGHT-AUDIT-001

**task_id:** `RESEARCHJOB-MVP-002-GROK-PREFLIGHT-AUDIT-001`  
**agent:** Grok external agent proxy  
**tier:** T1 read-only prerequisite and fixture audit  
**repository write authority:** Codex only  
**replaces:** `RESEARCHJOB-MVP-002-PREFLIGHT-AUDIT-001` (Mimo unavailable)  
**exact Desktop output:** `C:\\Users\\10639\\Desktop\\AlphaHive_V3_A_DATA_HEALTH_deliverables\\agent_outputs\\grok\\RESEARCHJOB-MVP-002-GROK-PREFLIGHT-AUDIT-001.md`

## Objective

Independently audit the accepted ResearchJob MVP 001B store for MVP 002
prerequisites. Identify exactly what exists, what can be reused and what Codex
must implement for immutable, versioned `EvidenceVerificationReport` and
direction-neutral `ResearchAssessment` artifacts. This is an audit only; do
not implement MVP 002 or mutate repository, fixtures or authoritative stores.

## Required reading

Read the shared materials in the exact order required by
`G:\\Quant test\\AlphaHive_V3\\PROJECT_REQUIRED_READING.md`, then read this
task, the research orchestration contract, the 001B Codex handoff, the Gemini
001B/002 architecture reports available at their Desktop paths, current
ResearchJob server files and current `tests/test_research_jobs.py`.

## Checks

- Establish SHA-256 hashes for ResearchJob server/test files and authoritative
  `signal_review/latest.json` before and after read-only checks.
- Map the current job/evidence/import/event/pointer/quarantine structure and
  identify exact extension points for `verification/vNNNN.json` and
  `assessment/vNNNN.json`.
- Identify valid temporary fixtures for an accepted-evidence job; do not
  import authoritative evidence.
- Audit required binding fields, canonical ordered evidence-set hash, monotonic
  version allocation, duplicate/idempotency, tamper detection, crash recovery
  and concurrent publication risks.
- Define negative cases for missing/incorrect predecessor hashes, evidence-set
  drift, record/job mismatch, invalid state, duplicate versions, corrupted
  version artifacts and no mutation of quality/Owner/Paper/trading paths.
- Separate PASS, ADVISORY and PARK evidence. List any true Owner-only decision.

## Hard boundaries and output

No repository/config/test/fixture writes; no external providers or source
fetches; no scheduler/database/checkpoint/outbox change; no Owner/Paper/trade
operation. Write only the exact Desktop report. Its header must include agent,
task ID, UTC, inputs, hashes, status and unresolved items, followed by
file:line evidence, a PASS/ADVISORY/PARK matrix, prioritized Codex worklist,
test matrix and `SELF_CHECK`.
