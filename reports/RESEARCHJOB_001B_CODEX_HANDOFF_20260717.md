# ResearchJob MVP 001B Codex implementation handoff — 2026-07-17

**task_id:** `RESEARCHJOB-MVP-001B-CODEX-IMPLEMENTATION-001`  
**owner:** Codex, sole implementation writer  
**status:** `ACCEPTED_WITH_ADVISORY_CORRECTION`  
**scope:** provider-neutral manual evidence import only

## Acceptance inputs

- Agy architecture report: `ACCEPTED_WITH_ADVISORY_CORRECTION`.
- Mimo preflight audit: `ACCEPTED_WITH_ADVISORY_CORRECTION`.
- Authority: `config/research_orchestration_contract.yaml` and the accepted
  ResearchJob 001A handoff.

The implementation corrects three report-level ambiguities: the route is
`POST /api/research/jobs/{job_id}/evidence/import`; rejected attempts append
`EVIDENCE_IMPORT_REJECTED` without changing Job state; successful import uses
`EVIDENCE_IMPORTED`, not `RESEARCH_TASK_EXPORTED`.

## Changed paths

- `G:\Quant test\alpha_hive\server\research_job_repository.py`
- `G:\Quant test\alpha_hive\server\research_job_service.py`
- `G:\Quant test\alpha_hive\server\research_job_routes.py`
- `G:\Quant test\AlphaHive_V3\tests\test_research_jobs.py`
- `G:\Quant test\AlphaHive_V3\agent_tasks\gemini__codex__researchjob_001b_long_goal_review.md`
- `G:\Quant test\AlphaHive_V3\agent_tasks\mimo__codex__researchjob_001b_long_goal_verification.md`
- this handoff and the status line in the Codex task file

No contract, signal-review artifact, quality gate, Owner decision, Paper,
outbox, scheduler, database, credential, provider or trading path changed.

## Implemented behavior

1. Provider-neutral JSON import with 2 MiB, depth-32 and 1,000-artifact
   fail-closed limits.
2. Generic schema, bundle/per-artifact hash, target Job, record and cutoff
   validation. Grok-only categories and source-job IDs are not required.
3. Historical cutoff at `scan_time_utc`; prospective import requires an
   explicit Owner-decision cutoff; missing cutoff is rejected.
4. All six attempt statuses are persisted under `imports/`. Rejections remain
   non-authoritative and preserve Job state.
5. Server-derived normalized content hash and semantic duplicate key. User
   content hashes never become paths.
6. Quarantine transaction manifests, immutable evidence/attempt publication,
   atomic mutable-file replacement, per-Job cross-process lock and replayable
   recovery on the next safe GET/import.
7. Pointer hash/size coverage for all evidence and attempt artifacts, plus
   event-chain validation for accepted and same-state rejected events.
8. Tampered evidence or attempts make GET fail closed.
9. Strict JSON rejects duplicate keys, non-finite constants, malformed or
   over-deep input; quarantine orphan cleanup is scoped by owning Job so
   concurrent imports for different Jobs cannot delete one another's staging.
10. Immutable publication retries operating-system short writes and is covered
    at every transaction failure point: pre-manifest, immutable artifact,
    events, Job and pointers.

## Verification receipts

```text
python -m pytest -q tests/test_research_jobs.py
31 passed, 15 subtests passed

python -m pytest -q tests/test_research_jobs.py tests/test_deep_research_package.py tests/test_signal_review.py
238 passed, 15 subtests passed

python -m pytest -q
354 passed, 15 subtests passed

python -m py_compile <three ResearchJob server files>
PASS

git diff --check
PASS (line-ending advisories only; no whitespace error)
```

The focused suite includes true multi-process same-content import: exactly one
`201 ACCEPTED`, four `400 DUPLICATE`, one evidence artifact and five immutable
attempt records. Failure injection after quarantine/immutable publication and
before event replacement returns 500; the next GET completes the manifest and
returns a valid `EVIDENCE_IMPORTED` Job.

## Current hashes

- `research_job_repository.py`: `50500FC726DC67EAEAA50D900D98320AE180482FB28D30989F1F51274010E7A9`
- `research_job_service.py`: `AA5B40618B226AF0E6F0B58CF610E3B850851653784C8467217605ED9B1D3EF6`
- `research_job_routes.py`: `6176A09938C3585AFA415A7119501E32AB514101E0D865C17DD21039CF2BD572`
- `tests/test_research_jobs.py`: `188838BB193CD72ECAC65BFA1321A0AABEE47200011568AA3A480AC7B21A2A5C`
- authoritative `signal_review/latest.json` before and after:
  `82D1E5DD6646E970FFAF4778908709CACD55095965ABEEDB953522A639667E8D`

## External long-goal acceptance — 2026-07-17

Both required external reports were delivered at their exact Desktop paths,
with current source hashes matching the candidate above. Codex independently
checked their stated evidence against the current code and re-ran the full
unfiltered suite.

- Gemini report: `ACCEPTED_WITH_ADVISORY_CORRECTION`.
  Its contract traceability, bounds, quarantine, integrity and isolation
  findings are supported. Two rows in its state table are corrected here:
  a semantic duplicate can arise only after accepted evidence exists, so its
  pre-state is `EVIDENCE_IMPORTED`; it persists a `DUPLICATE` attempt and
  appends same-state `EVIDENCE_IMPORT_REJECTED`, rather than returning silently
  without an event.
- Mimo report: `ACCEPTED_WITH_ADVISORY_CORRECTION`.
  Its 40 mechanical checks, temporary-store discipline and before/after hashes
  are supported. Its `345` full-suite result is the deliberately filtered run
  that skipped two modules. The current unfiltered acceptance command is
  `python -m pytest -q`, which passes as `354 passed, 15 subtests passed`.

The external reviews resolve the independent-audit gate. Following this
acceptance, the contract's current-priority marker is promoted to MVP 002 and
the next-stage dispatch package is created. No commit or package publication
was performed.

## Next stage and dispatch

The next ordered slice is `RESEARCHJOB-MVP-002_VERIFICATION_AND_ASSESSMENT`
(T1/T2). It introduces immutable, versioned manual verification and
direction-neutral assessment artifacts only. It must not add automatic provider
calls, Owner decisions, Paper plans, notifications, trigger ignition,
credentials, data-source changes or trading paths.

Ready for external dispatch now, in parallel:

- Gemini architecture goal: `RESEARCHJOB-MVP-002-GOAL-ARCH-001` —
  `agent_tasks/gemini__codex__researchjob_002_goal_architecture.md` — Desktop
  output `agent_outputs/antigravity/RESEARCHJOB-MVP-002-GOAL-ARCH-001.md`.
- Mimo preflight: `RESEARCHJOB-MVP-002-PREFLIGHT-AUDIT-001` —
  `agent_tasks/mimo__codex__researchjob_002_preflight_audit.md` — Desktop
  output `agent_outputs/mimo/RESEARCHJOB-MVP-002-PREFLIGHT-AUDIT-001.md`.

Codex implementation `RESEARCHJOB-MVP-002-CODEX-IMPLEMENTATION-001` is
blocked only on acceptance of those two reports. A DeepSeek final audit is
dispatched only after the candidate implementation and its regression receipts
exist. The exact external messages are in
`agent_tasks/RESEARCHJOB_002_EXTERNAL_HANDOFF_MESSAGES_20260717.md`.

No new T3 Owner decision was created by 001B. Existing source, trigger, Paper,
credential, backfill and trading gates remain parked exactly as documented.

## SELF_CHECK

- [x] Allowed implementation paths only.
- [x] No real provider or network call.
- [x] Temporary stores used by tests.
- [x] All attempt outcomes represented.
- [x] Rejections preserve state and never create evidence.
- [x] Accepted evidence is immutable and recoverable.
- [x] Signal-review authoritative hash unchanged.
- [x] Focused, adjacent and full suites pass.
- [x] External Gemini long-goal review received and accepted with report-level correction.
- [x] External Mimo mechanical verification received and accepted with report-level correction.
