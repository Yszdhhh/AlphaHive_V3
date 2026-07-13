# RESEARCHJOB-MVP-001A-FIX-01 — Gemini Mainline Repair

```yaml
task_id: RESEARCHJOB-MVP-001A-FIX-01
expected_model_label: "Gemini 3.1 Pro (High)"
workspace_root: "G:\\Quant test"
stage: "RESEARCHJOB-MVP-001A"
mode: "repair only; no next-stage work"
```

## Gate and authority

This repair is the only authorized implementation task now. Do not implement
001B evidence import, verification, assessment, Owner decision, PaperPlan,
notifications, dashboard history, automatic providers, exchange connectivity,
or any real trading.

Read before editing:

```text
G:\Quant test\AlphaHive_V3\reports\NEXT_STAGE_HANDOFF_20260712.md
G:\Quant test\AlphaHive_V3\reports\AGENT_SYNC_STATUS_20260712.md
G:\Quant test\AlphaHive_V3\reports\BASELINE_20260712_RESEARCHJOB_READY.json
G:\Quant test\AlphaHive_V3\config\research_orchestration_contract.yaml
G:\Quant test\AlphaHive_V3\prompts\researchjob_mvp_001a_gemini.md
```

The current implementation is in the real main workspace, principally:

```text
G:\Quant test\alpha_hive\server\research_job_repository.py
G:\Quant test\alpha_hive\server\research_job_service.py
G:\Quant test\alpha_hive\server\research_job_routes.py
G:\Quant test\AlphaHive_V3\tests\test_research_jobs.py
```

Do not audit or edit the legacy nested duplicate
`G:\Quant test\alpha_hive\AlphaHive_V3`.

## Baseline protection

Before and after work, record SHA-256 for:

```text
G:\Quant test\alpha_hive\results\signal_review\latest.json
G:\Quant test\alpha_hive\results\signal_review tree
```

Do not write to either `AlphaHive_V3/harness/runs/**` or
`alpha_hive/results/signal_review/**`. Tests must use a temporary ResearchJob
store. Preserve the frozen baseline hashes:

```text
latest.json: 82d1e5dd6646e970ffaf4778908709cacd55095965abeedb953522a639667e8d
signal_review tree: 4e8d478f90cb95406eb3f7b524dce90dbbc6beb271ff2a95e5ed2dfc5ac109ed
```

## Defects to repair

The existing code has useful partial protections, but it is not yet contract
conformant. Repair all items below as one bounded 001A change.

1. Route surface and identifiers
   - Provide exactly `POST /api/research/jobs` and `GET /api/research/jobs/{job_id}`
     as the supported 001A ResearchJob API. Do not retain an undocumented list
     endpoint as part of this slice. A compatibility alias is allowed only if it
     cannot weaken validation, but tests and documentation must target the
     contract paths.
   - Generate a server-side path-safe ID in the form `job_` plus a UUID/ULID
     compatible value. Never accept a client-supplied ID.
   - Use one shared validator for job IDs and record IDs. Reject separators,
     traversal, malformed/overlong values, and all Windows reserved-device-name
     forms (case-insensitive; including names with trailing dot/space or an
     extension where such input could otherwise reach a filesystem path).

2. Canonical frozen package and cross-artifact integrity
   - Freeze a canonical JSON representation of the source candidate into
     `candidate_package.json`; calculate `package_hash` from those exact
     canonical bytes, not from an unverified source field.
   - Persist artifact hashes/size (or equally deterministic integrity bindings)
     in `pointers.json` so a reader can verify `job.json`,
     `candidate_package.json`, and `events.jsonl` before reconstructing a Job.
   - On GET, reject a missing, malformed, inconsistent, or tampered artifact:
     hash mismatches, job/path ID mismatch, record/package hash mismatch,
     candidate record mismatch, malformed pointers, and invalid event ledger.
     Return no partially reconstructed Job.
   - Ensure capability state is derived only from the frozen package. A
     `quality_status=BLOCK` remains eligible for ResearchJob creation and has
     research/Owner-review capability allowed while PaperPlan capability is
     blocked. Do not create any PaperPlan.

3. Complete append-only event ledger
   - Persist the initial transition as deterministic append-only events that
     encode both required states: `RESEARCH_JOB_CREATED` then
     `AWAITING_EVIDENCE` (an explicit creation event followed by a state
     transition is acceptable).
   - Every event must include: `event_id`, positive contiguous `sequence`,
     `job_id`, `event_type`, actor type and actor ID, `previous_state`,
     `new_state`, input hash(es), output hash(es), UTC timestamp,
     `previous_event_hash`, and `event_hash`.
   - Define the exact canonical event-hash preimage (exclude only the
     self-hash), and validate every required field, sequence, state continuity,
     predecessor link, event hash, and final pointer. A single-event ledger is
     not a substitute for the required initial state transition.

4. Atomicity, durability, and cross-process idempotency
   - Creation must be directory-level atomic: no observer may see a final
     `{job_id}` directory until every required artifact has been fully written
     and locally validated. On any injected write/rename/fsync failure, clean
     only the operation's staging area and leave no final partial Job.
   - Use durable structured-file writes (flush + fsync before final atomic
     publication; safely handle platform-specific directory/fsync behavior).
   - Make semantic idempotency atomic across independent processes, not only
     threads in one process. Concurrent creates for identical
     `(record_id, canonical package_hash)` must yield exactly one Job
     directory; one request returns `201`, all replays return `200` with an
     explicit `idempotent_replay: true` and the same Job. Do not let a race
     overwrite an existing final directory.
   - Keep failure reporting deterministic and do not silently treat corrupt
     Jobs as valid idempotent matches.

## Tests required

Update/add focused tests under `AlphaHive_V3/tests/` (temporary store only) for:

- contract create/get paths, server-generated `job_` ID, and no client ID;
- invalid record and job IDs, including the complete Windows reserved-name
  cases relevant to accepted syntax;
- unknown record;
- recomputable canonical frozen-package hash and package immutability;
- required two-step initial event sequence and complete hash-chain validation;
- restart persistence;
- GET refusal for independent tampering of every persisted artifact and each
  ledger-link/sequence/state inconsistency;
- directory-level failure injection (write, fsync, validation, publish) with no
  partial final directory or leaked staging directory;
- cross-process concurrent same-key create (not merely ThreadPoolExecutor),
  with one created result and explicit 200 replays;
- `quality_status=BLOCK` can create a ResearchJob but cannot gain PaperPlan
  capability;
- no production signal-review file/tree change before versus after the full
  suite.

Remove or replace tests that normalize non-contract behavior such as a bare
UUID job ID, incomplete one-event ledger, or the unsupported list surface.

## Allowed and forbidden paths

You may modify only files necessary for the repair in:

```text
G:\Quant test\alpha_hive\server\app.py
G:\Quant test\alpha_hive\server\research_job_repository.py
G:\Quant test\alpha_hive\server\research_job_service.py
G:\Quant test\alpha_hive\server\research_job_routes.py
G:\Quant test\AlphaHive_V3\harness\lib\research_job_models.py
G:\Quant test\AlphaHive_V3\tests\test_research_jobs.py
G:\Quant test\AlphaHive_V3\tests\test_research_job_*.py
G:\Quant test\AlphaHive_V3\tests\fixtures\research_jobs\**
```

Do not modify:

```text
G:\Quant test\AlphaHive_V3\harness\runs\**
G:\Quant test\alpha_hive\results\signal_review\**
G:\Quant test\alpha_hive\AlphaHive_V3\**
G:\Quant test\alpha_hive\dashboard\**
```

## Delivery report (required)

Do not claim acceptance. Report the exact model label, absolute changed paths,
test command and environment, collected/passed/failed/skipped/warning counts,
API smoke results for create/new/replay/get, restart result, concurrent-process
result, failure-injection result, and production baseline hashes before/after.
State any limitation precisely. Wait for Codex actual acceptance; do not create
Claude or Mimo tasks.
