# AlphaHive Cloud Audit Brief

## Product and safety position

AlphaHive is a local crypto abnormal-signal research system. It does not place
live trades. The product goal is:

```text
deterministic abnormal scan
-> explainable review dashboard and deep-research prompt
-> manually operated external research
-> verified evidence and owner decision
-> paper-only plan and discipline tracking
-> later notification outbox / Feishu
```

External LLM/X material is always provider-neutral, manually imported and
tagged `UNVERIFIED_EXTERNAL_EVIDENCE`. It cannot mutate quality gates, Owner
decisions or Paper plans directly.

## Current accepted baseline

- Signal Review dashboard/API and deterministic quality gates exist.
- Quality gates fail closed; the latest real candidate is
  `1000BONKUSDT`, quality `BLOCK`, because of
  `missing_contract_identity`.
- A quality BLOCK still permits research and owner review, but blocks a Paper
  plan.
- Historical Grok output is only a frozen fixture; no automatic provider API is
  active.
- Pre-ResearchJob frozen baseline: 284 collected / 284 passed, with one
  non-blocking Starlette/httpx deprecation warning.

## ResearchJob 001A objective

001A is only an immutable, file-backed ResearchJob creation/read vertical
slice. It excludes evidence import, verification, assessment, Owner decision,
Paper Plan, Feishu, automatic LLM calls and trading.

Required storage under `alpha_hive/results/research_jobs/{job_id}/`:

```text
job.json
candidate_package.json
events.jsonl
pointers.json
```

Required public endpoints:

```text
POST /api/research/jobs
GET  /api/research/jobs/{job_id}
```

No list endpoint is in this slice.

The server generates `job_` IDs. `record_id` must be path-safe and reject
Windows-reserved names. Same `(record_id, canonical_package_hash)` must be
idempotent under concurrent requests. Creation requires staging, atomic
publication, durable/recoverable idempotency indexing, and no readable
half-created Job.

The initial state is `AWAITING_EVIDENCE`, represented by exactly two
hash-linked events:

```text
RESEARCH_JOB_CREATED -> AWAITING_EVIDENCE
```

Each event must have a valid ID, sequence, actor, input/output hashes,
previous/new states, previous-event hash and event hash. GET must reject a
missing, corrupt or internally inconsistent Job.

## Current implementation status

ResearchJob FIX-02 is **not accepted** (43/100). It has partial useful work
(server ID, package hash, staging/index attempt, cross-process test attempt),
but has these P0/P1 blockers:

1. API paths are reversed: `/api/research-jobs` is wrongly primary instead of
   `/api/research/jobs`; an out-of-scope list endpoint remains.
2. The implementation incorrectly uses one initial event instead of two.
3. Event validation does not require all mandatory event fields.
4. Focused tests encode those wrong expectations, so `18 passed` is not proof
   of compliance.
5. Index fsync, exceptional cleanup and corrupt-final-Job recovery are not yet
   sufficient.

## Audit request

Review the architecture and these exact questions. Do not propose live trading
or automatic LLM execution.

1. Is the two-event initial lifecycle and event hash-chain validation complete
   enough for a file-backed MVP?
2. Is the proposed staging/index/recovery protocol crash-safe and idempotent
   under concurrent process creation? Identify all remaining crash windows.
3. Are API boundaries, state boundaries and out-of-scope features respected?
4. Which minimal tests prove corruption detection, recovery and non-pollution
   of real result directories?
5. Identify any security issue in path validation, Windows filename behavior,
   JSON canonicalization, hash semantics or client-controlled input.

Return findings classified P0/P1/P2 with the smallest viable remediation. Do
not write code and do not broaden the scope beyond ResearchJob 001A.
