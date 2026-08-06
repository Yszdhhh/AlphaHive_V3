# RESEARCHJOB-MVP-001B-GOAL-ARCH-001 — Gemini 3.1 Pro goal-mode task

**task_id:** `RESEARCHJOB-MVP-001B-GOAL-ARCH-001`  
**agent:** Gemini 3.1 Pro (goal mode)  
**tier:** T1/T2 read-only architecture, security and test-design package  
**repository write authority:** Codex only  
**exact Desktop output:** `C:\Users\10639\Desktop\AlphaHive_V3_A_DATA_HEALTH_deliverables\agent_outputs\antigravity\RESEARCHJOB-MVP-001B-GOAL-ARCH-001.md`

## Goal-mode objective

Produce a complete, implementation-ready design and acceptance package for
ResearchJob MVP 001B: evidence-import quarantine, schema/hash/cutoff validation,
immutable evidence records and import-attempt ledger. Continue until every
section of the Definition of Done below is addressed or explicitly marked
`PARK` with an evidence-based reason. You may use multiple internal subagents
for independent contract, security, failure-injection and test-matrix reviews,
but merge their findings into one final report.

This task must not modify the repository. The final report is the only output.

## Required reading (in order)

1. `G:\Quant test\AGENTS.md`
2. `G:\Quant test\AlphaHive_V3\AGENTS.md`
3. `G:\Quant test\AlphaHive_V3\PROJECT_REQUIRED_READING.md`
4. `G:\Quant test\AlphaHive_V3\PROJECT_OPERATING_PLAYBOOK.md`
5. `G:\Quant test\AlphaHive_V3\agent_tasks\README.md`
6. `G:\Quant test\AlphaHive_V3\config\research_orchestration_contract.yaml`
7. `G:\Quant test\AlphaHive_V3\reports\NEXT_STAGE_HANDOFF_20260712.md`
8. `G:\Quant test\AlphaHive_V3\reports\RESEARCHJOB_001A_FIX03_CODEX_HANDOFF_20260716.md`
9. `G:\Quant test\AlphaHive_V3\reports\RESEARCHJOB_001A_FIX02_ACCEPTANCE_20260713.md`
10. `G:\Quant test\AlphaHive_V3\harness\lib\external_evidence_normalizer.py`
11. `G:\Quant test\AlphaHive_V3\harness\lib\external_evidence_schema_validator.py`
12. `G:\Quant test\AlphaHive_V3\tests\test_research_jobs.py`
13. `G:\Quant test\AlphaHive_V3\tests\test_grok_regression.py`
14. `G:\Quant test\AlphaHive_V3\reports\PROMPT_FRAMEWORK_FREEZE_ACCEPTANCE_20260717.md`

## Required design coverage

### A. API and state boundary

Define the exact behavior of:

`POST /api/research/jobs/{job_id}/evidence/import`

The Job remains `AWAITING_EVIDENCE` after any rejected import. Only an accepted
import may create an immutable evidence artifact and the `EVIDENCE_IMPORTED`
state transition, with no Owner decision or PaperPlan transition.

### B. Import-attempt outcomes

Cover every contract status:

`ACCEPTED`, `REJECTED_SCHEMA`, `REJECTED_HASH`, `REJECTED_CUTOFF`,
`REJECTED_RECORD_MISMATCH`, `DUPLICATE`.

Specify which outcomes are persisted, where they are stored, and how the
attempt is linked to the Job without allowing a rejected artifact to become
authoritative evidence.

### C. Artifact and security rules

Define canonical JSON/hash semantics, provider-neutral fields, source/citation
requirements, cutoff validation, record/job binding, maximum size/depth,
path-traversal protection, quarantine naming, immutable publication and
duplicate-key semantics. Missing data must never default to zero.

### D. Failure and concurrency matrix

Cover malformed JSON, schema mismatch, wrong package hash, wrong record_id,
late source/cutoff, duplicate content, write/fsync/rename failure, process crash
between quarantine and publication, concurrent same-import requests and
corrupted pre-existing evidence. Specify fail-closed response and recovery.

### E. Test and acceptance plan

Provide exact test names or test groups for API, schema, hash, cutoff,
quarantine, immutability, replay/idempotency, crash recovery, path safety and
no mutation of signal-review data. Include a migration-free temporary-store
strategy and exact evidence needed for Codex acceptance.

### F. Scope locks

Explicitly exclude automatic providers, web/API calls, Owner decisions, Paper
Plan generation, Paper `ALLOW`, trigger ignition, source changes, credentials,
notifications and trading paths.

## Required report shape

Header must contain `agent`, exact `task_id`, UTC timestamp, status
(`GREEN`, `PARK` or `UNVERIFIED`) and all inputs read. The report must include
an architecture map, proposed API contract, artifact layout, state/event table,
failure matrix, test matrix, exact Codex implementation file allowlist, open
Owner decisions and `SELF_CHECK`. Do not claim code was changed or tests were
run unless actually done.
