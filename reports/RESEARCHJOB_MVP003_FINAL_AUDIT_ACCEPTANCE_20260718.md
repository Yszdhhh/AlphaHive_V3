# ResearchJob MVP003 independent-final-audit acceptance — 2026-07-18

**implementation:** `RESEARCHJOB-MVP-003-CODEX-IMPLEMENTATION-001`  
**external audit:** `RESEARCHJOB-MVP-003-FINAL-AUDIT-001`  
**auditor report:** `C:\\Users\\10639\\Desktop\\AlphaHive_V3_A_DATA_HEALTH_deliverables\\agent_outputs\\deepseek\\RESEARCHJOB-MVP-003-FINAL-AUDIT-001.md`  
**acceptance:** `ACCEPTED / GREEN`

> **2026-07-18 addendum — targeted correction pending:** a later review found
> that the service and the offline PaperPlan engine serialized a preset hash
> differently. This did not permit Paper or alter the present DRAFT block, but
> it could make a future valid decision fail compatibility. Codex corrected the
> service to use the engine's compact canonical JSON and added an equality
> regression test. The initial acceptance is retained for its seven audited
> properties; the hash-compatibility assertion is pending the narrow independent
> correction audit at
> `agent_tasks/deepseek__codex__researchjob_mvp003_preset_hash_correction_audit.md`.
> **Resolved:** `RESEARCHJOB-MVP-003-PRESET-HASH-CORRECTION-AUDIT-001` passed
> independently and is accepted in
> `reports/RESEARCHJOB_MVP003_PRESET_HASH_CORRECTION_ACCEPTANCE_20260718.md`.

## Accepted evidence

DeepSeek independently reported all seven prescribed checks as PASS: protected
file hashes unchanged before/after, 38 focused plus 388 full-project tests,
strict JSON/no external calls, complete binding and immutable artifact/tamper
coverage, constrained state transitions and rejection journaling,
historical/capability/DRAFT preset Paper blocks, and quarantine recovery with
five-process contention.

Codex independently re-read the report, re-hashed the four implementation/test
files, and checked the cited binding-context code. The report's hashes equal
the Codex handoff hashes. Its stated test receipts equal the local receipts.

## Advisory disposition

- **Rejected as a false advisory:** the report calls `assessments` at
  `research_job_repository.py:844-847` a misspelling. It is a conventional
  plural collection variable loaded from `assessment_files`, immediately read
  without reassignment, and does not shadow or duplicate another name. No
  corrective mutation is warranted.
- **Accepted as intentional design:** `_preset_hash` excluding `preset_hash`
  and `artifact_hash` prevents self-referential hashing. Any future schema
  expansion remains protected by the preset's `APPROVED` status and exact
  canonical-hash binding; the present `DRAFT` preset independently blocks
  `APPROVE_PAPER`.

## Boundary remains unchanged

This acceptance records only immutable OwnerDecision infrastructure. A
per-job chat affirmation remains procedural context rather than cryptographic
identity proof. No real OwnerDecision, PaperPlan, Paper execution, trigger,
notification, credential, source change or trading action was created or
authorized.

## Next stage

MVP003 is complete. The production PaperPlan stage has two real blockers:

1. the Owner must separately approve a concrete `paper_execution_presets.yaml`
   release and its exact hash; and
2. a fresh `PROSPECTIVE_LIVE`, quality-ALLOW ResearchJob must actually reach
   `RESEARCH_ASSESSMENT_READY`.

The historic BONK job remains permanently ineligible. Do not start MVP004
production persistence or create a PaperPlan until those two prerequisites are
genuinely met; the already accepted local sandbox remains available for
synthetic offline demonstration only.
