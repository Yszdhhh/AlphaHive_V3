# RESEARCHJOB-MVP-001B-CODEX-IMPLEMENTATION-001 — Codex internal task

**task_id:** `RESEARCHJOB-MVP-001B-CODEX-IMPLEMENTATION-001`  
**owner:** Codex (sole repository writer)  
**status:** `ACCEPTED_WITH_ADVISORY_CORRECTION`

## Objective

Implement only the accepted 001B evidence-import quarantine slice after the
Gemini goal report and Mimo preflight report are available and reconciled.

## Hard scope

- Evidence import endpoint and temporary quarantine.
- Import-attempt statuses from `research_orchestration_contract.yaml`.
- Provider-neutral schema/hash/cutoff/record binding.
- Immutable evidence publication and duplicate handling.
- Temporary-store tests for rejection, crash/recovery and concurrency.

## Explicit exclusions

No verification/assessment, Owner decision, PaperPlan, notification delivery,
automatic provider, web/API call, source/credential change, trigger ignition,
Paper `ALLOW` or trading path.

## Acceptance gate

Do not start implementation until Codex has read and reconciled:

- Gemini `RESEARCHJOB-MVP-001B-GOAL-ARCH-001` report;
- Mimo `RESEARCHJOB-MVP-001B-PREFLIGHT-AUDIT-001` report;
- `config/research_orchestration_contract.yaml`;
- the accepted ResearchJob 001A handoff.

The final Codex report must list changed paths, full test counts, API smoke
results, quarantine/recovery evidence and baseline hashes before/after.
