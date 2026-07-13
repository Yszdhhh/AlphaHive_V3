# ResearchJob MVP 001A — FIX-02 Acceptance Record

Date: 2026-07-13  
Status: **REJECTED — Gemini repair required; do not dispatch Claude or Mimo**

## Scope authority

The authoritative 001A API and event boundary are:

```text
POST /api/research/jobs
GET  /api/research/jobs/{job_id}
```

There is no list endpoint in 001A. The initial lifecycle is expressed by two
contiguous, hash-linked events:

```text
RESEARCH_JOB_CREATED -> AWAITING_EVIDENCE
```

The job is still research-capable when its source candidate is quality BLOCK,
but its Paper capability remains blocked.

## Independent acceptance result

Score: **43 / 100**

Accepted partial work:

- server-generated `job_` identifier;
- normalized candidate-package hash;
- partial file-hash binding;
- BLOCK capability propagation;
- a real cross-process test attempt;
- staging/index/recovery implementation attempt;
- authoritative `latest.json` remains unchanged from the frozen baseline.

## Blocking failures

1. **API contract inversion.** The implementation makes `/api/research-jobs`
   the primary route and hides the required `/api/research/jobs` as an alias.
   It must be reversed. It also retains/adds a list endpoint that is outside
   001A.
2. **Event-boundary violation.** The implementation/report claims a single
   initial event. 001A requires two consecutive events representing
   `RESEARCH_JOB_CREATED` then `AWAITING_EVIDENCE`.
3. **Insufficient event validation.** The directory validator does not require
   and validate required event fields including `event_id`, actor information,
   input/output hashes, and valid previous/new states. Removing such fields can
   remain undetected.
4. **Tests codify the wrong contract.** Focused tests assert one event and the
   wrong primary route/list behavior. A reported focused `18 passed` result is
   not acceptance evidence for 001A.
5. **Durability and recovery remain incomplete.** Index writes do not fsync;
   exceptional publish paths can leave an index; recovery for a corrupt final
   Job is not strict enough.

## Required next action

Gemini 3.1 Pro High must receive one bounded FIX-03 task covering only the
five blocking failures above. No Claude review and no Mimo testing begins until
Codex verifies the corrected implementation and full test result.

## Verification discipline

Do not claim the full suite is green from the focused `18 passed` run. The next
acceptance must report the exact full-suite collected/passed/failed/skipped
counts, inspect the actual API routes, and exercise crash/recovery tests in a
temporary output directory.
