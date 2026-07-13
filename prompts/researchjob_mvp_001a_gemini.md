# RESEARCHJOB-MVP-001A — Gemini Mainline Implementation

```yaml
task_id: RESEARCHJOB-MVP-001A
expected_model_label: "Gemini 3.1 Pro (High)"
workspace_root: "G:\\Quant test"
baseline_file: "AlphaHive_V3/reports/BASELINE_20260712_RESEARCHJOB_READY.json"
```

## Scope

Implement only the persistent ResearchJob store and Create/Get API. Do not
implement evidence import, verification, assessment, Owner decision, PaperPlan,
notifications, dashboard history or automatic external Provider calls.

## Allowed paths

```text
alpha_hive/server/app.py
alpha_hive/server/research_job_routes.py
alpha_hive/server/research_job_service.py
alpha_hive/server/research_job_store.py
AlphaHive_V3/harness/lib/research_job_models.py
AlphaHive_V3/tests/test_research_job_store.py
AlphaHive_V3/tests/test_research_job_api.py
AlphaHive_V3/tests/fixtures/research_jobs/**
```

## Forbidden paths

```text
AlphaHive_V3/harness/runs/**
alpha_hive/results/signal_review/**
G:\Quant test\alpha_hive\AlphaHive_V3/**
alpha_hive/dashboard/**
```

## Requirements

1. Generate the Job ID server-side (`job_` plus UUID or ULID-compatible value).
   Do not accept a client-supplied job ID.
2. Validate `record_id` with the contract regex and reject path traversal,
   Windows reserved names and overlong values.
3. Find the record from the signal-review source of truth and freeze its package
   to `candidate_package.json` with a canonical hash.
4. Persist a Job under a configurable store root. Production root is
   `alpha_hive/results/research_jobs/{job_id}`; tests must use `TemporaryDirectory`.
5. Persist `job.json`, `candidate_package.json`, `pointers.json` and
   `events.jsonl`. No existing artifact may be overwritten.
6. Initial transition: `RESEARCH_JOB_CREATED -> AWAITING_EVIDENCE`.
7. Events require `event_id`, sequence, job ID, event type, actor type/ID,
   previous/new state, input/output hashes, UTC timestamp, previous event hash
   and event hash.
8. Use atomic durable writes for structured files and a safe append strategy for
   events. A restart must reconstruct the same Job and event sequence.
9. Capability state must reflect the frozen package: research and Owner review
   can remain allowed while Paper plan capability is blocked by a quality BLOCK.
10. Add exactly these APIs:

```text
POST /api/research/jobs
GET  /api/research/jobs/{job_id}
```

## Required tests

- server-generated ID;
- invalid/path-traversal/reserved `record_id` rejected;
- unknown record rejected;
- frozen package hash is recomputable;
- event hash chain and sequence;
- restart persistence;
- duplicate create behavior is explicit and deterministic;
- API create/get smoke test;
- test-suite and production signal-review tree hashes unchanged before/after.

## Required report

Report the exact model label, absolute changed paths, test collection/pass/fail/
skip/warning counts, API smoke results, restart result, and production baseline
before/after hashes. Do not claim completion if any requirement is missing.
