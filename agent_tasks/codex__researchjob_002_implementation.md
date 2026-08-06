# RESEARCHJOB-MVP-002-CODEX-IMPLEMENTATION-001

**task_id:** `RESEARCHJOB-MVP-002-CODEX-IMPLEMENTATION-001`  
**owner:** Codex, sole repository writer  
**status:** `ACCEPTED_AFTER_DEEPSEEK_FINAL_AUDIT`  
**tier:** T1/T2 implementation

## Objective

After accepting the Gemini architecture and Mimo preflight reports, implement
only the MVP 002 verification-and-assessment slice: immutable versioned
artifacts, manual import boundaries, strict hash/state binding, atomic recovery
and temporary-store tests.

## Preconditions

Do not start until the following formal reports exist and are reconciled:

- `RESEARCHJOB-MVP-002-GOAL-ARCH-001`;
- `RESEARCHJOB-MVP-002-PREFLIGHT-AUDIT-001`;
- accepted 001B handoff;
- current research orchestration contract.

## Hard scope and exclusions

No automatic provider/source fetch, Owner decision, PaperPlan, notification,
trigger, credential, source-path, scheduler, database or trading change. Only
the route/service/repository files strictly required by the accepted design and
`tests/test_research_jobs.py` may change. The final handoff must state changed
paths, all test counts, baseline hashes, version/recovery receipts and the next
stage with dispatch state.
