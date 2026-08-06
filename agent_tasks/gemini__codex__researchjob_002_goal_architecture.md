# RESEARCHJOB-MVP-002-GOAL-ARCH-001

**task_id:** `RESEARCHJOB-MVP-002-GOAL-ARCH-001`  
**agent:** Gemini external agent proxy, long-thread goal mode  
**tier:** T1/T2 read-only architecture and acceptance design  
**repository write authority:** Codex only  
**exact Desktop output:** `C:\Users\10639\Desktop\AlphaHive_V3_A_DATA_HEALTH_deliverables\agent_outputs\antigravity\RESEARCHJOB-MVP-002-GOAL-ARCH-001.md`

## Long-thread goal

Produce an implementation-ready architecture and acceptance package for
ResearchJob MVP 002: immutable, versioned `EvidenceVerificationReport` and
direction-neutral `ResearchAssessment` artifacts. Continue until every
definition-of-done item is evidenced or explicitly `PARK`; do not modify any
repository tree.

## Required reading

Read the shared materials in the exact order required by
`G:\Quant test\AlphaHive_V3\PROJECT_REQUIRED_READING.md`, then read:

1. this task file;
2. `G:\Quant test\AlphaHive_V3\config\research_orchestration_contract.yaml`;
3. `G:\Quant test\AlphaHive_V3\reports\RESEARCHJOB_001B_CODEX_HANDOFF_20260717.md`;
4. the accepted Gemini/Mimo 001B reports at their Desktop paths;
5. current `G:\Quant test\alpha_hive\server\research_job_*.py`;
6. current `G:\Quant test\AlphaHive_V3\tests\test_research_jobs.py`.

## Required design coverage

1. Define exact manual-import API boundary/boundaries and response semantics.
2. Specify schemas, canonical hash semantics and versioned immutable layouts
   for `verification/vNNNN.json` and `assessment/vNNNN.json`.
3. Bind every artifact to `job_id`, `record_id`, candidate-package hash,
   ordered evidence-set hash and predecessor artifact hash. Missing data must
   fail closed and never default to zero.
4. Define deterministic state/event transitions only:
   `EVIDENCE_IMPORTED -> EVIDENCE_VERIFIED -> RESEARCH_ASSESSMENT_READY`.
   Determine reject/duplicate/idempotency semantics without adding automatic
   provider behavior.
5. Preserve 001B guarantees: quarantine, atomic publication, fsync/recovery,
   event chain, pointers, immutability, path safety and concurrency control.
6. Ensure verification can report source/cutoff/duplication/prompt-injection
   findings without fetching sources or promoting evidence to trading truth.
7. Ensure assessment is direction-neutral, `performance_eligible=false`, has
   no PaperPlan/Owner-decision content and cannot change quality gates or
   capabilities.
8. Provide a focused test/failure matrix, temporary-store strategy, exact
   Codex file allowlist and explicit Owner decisions (or `None`).

## Hard exclusions

No repository edit, external provider/API/web call, source verification fetch,
credential, trigger, Paper `ALLOW`, Owner signature, notification, scheduler,
database or trading operation. The Desktop report is the only output.

## Required report shape

Header: agent, task ID, UTC, status, inputs and unresolved items. Include an
architecture map, API/state table, artifact schemas/layout, hash-binding rules,
failure/concurrency matrix, test matrix, Codex allowlist, Owner decision list
and `SELF_CHECK`.
