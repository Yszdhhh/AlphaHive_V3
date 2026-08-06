# RESEARCHJOB-MVP-001A-FIX-03 — Codex implementation handoff

**task_id:** `RESEARCHJOB-MVP-001A-FIX-03`  
**owner:** Codex (sole repository writer)  
**UTC handoff:** 2026-07-16  
**status:** `ACCEPTED_WITH_ADVISORY_CORRECTION`  
**scope:** ResearchJob create/get durability and integrity only

## Implemented changes

Changed:

- `G:\Quant test\alpha_hive\server\research_job_repository.py`
- `G:\Quant test\AlphaHive_V3\tests\test_research_jobs.py`

The candidate now:

1. Records explicit event types for the two required initial events:
   `RESEARCH_JOB_CREATED` then `STATE_TRANSITION` to `AWAITING_EVIDENCE`.
2. Validates event type, event ID uniqueness, positive contiguous sequence,
   state continuity, list-shaped input/output hashes and the complete event
   hash chain on every GET.
3. Persists and validates deterministic byte sizes for candidate package, job
   and event artifacts in `pointers.json`.
4. Uses best-effort directory fsync barriers after index publication and final
   Job publication, while preserving the existing staging cleanup and
   cross-process idempotency path.
5. Keeps `quality_status=BLOCK` research-capable but PaperPlan-blocked and does
   not create evidence, Paper plans or provider calls.

No trigger, threshold, Paper eligibility, source, credential, scheduler,
database, Parquet or trading path was changed.

## Verification

Commands:

```text
python -m pytest -q tests/test_research_jobs.py
python -m pytest -q tests/test_research_jobs.py tests/test_deep_research_package.py tests/test_signal_review.py
python -m pytest -q
```

Results:

- ResearchJob focused: `17 passed`
- ResearchJob + deep research + signal review: `224 passed`
- Full suite: `340 passed`

The tests use temporary stores and do not modify authoritative signal-review
inputs. At the initial handoff this was a candidate pending Mimo's independent
negative/recovery audit; the acceptance below supersedes that provisional
status.

## Known limitations for audit

- Full directory-level failure injection and cross-process crash timing still
  require independent review under the exact external audit task.
- The existing prompt contract remains `v1.0.0-draft`; this handoff does not
  freeze the research prompt or activate any Paper workflow.

## External audit acceptance — 2026-07-17

Mimo delivered the exact Desktop report:

`C:\Users\10639\Desktop\AlphaHive_V3_A_DATA_HEALTH_deliverables\agent_outputs\mimo\RESEARCHJOB-MVP-001A-NEGATIVE-AUDIT-001.md`

Codex acceptance: `ACCEPTED_WITH_ADVISORY_CORRECTION`.

The report independently passes all 12 required checks and reproduces the
17/224/340 test counts. It confirms the authoritative `latest.json` hash is
unchanged. The remaining advisories are non-blocking: Windows directory fsync
is best-effort and the signal-review tree hash includes expected notification
outbox drift from test execution. These do not block the 001A create/get slice,
but outbox test hygiene should be cleaned before a future baseline freeze.
