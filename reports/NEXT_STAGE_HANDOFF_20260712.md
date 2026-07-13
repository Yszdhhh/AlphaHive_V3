# AlphaHive Next-Stage Handoff

Date: 2026-07-12 (superseded by 2026-07-13 acceptance update)  
Workspace: `G:\Quant test`  
Stage: `RESEARCHJOB-MVP-001A_FIX02_REJECTED`

> Read `RESEARCHJOB_001A_FIX02_ACCEPTANCE_20260713.md` before using this
> handoff. ResearchJob code now exists but is not accepted. The only next
> action is Gemini FIX-03; do not dispatch Claude or Mimo.

## 1. Product position

AlphaHive is currently a **Signal Review + External Evidence Contract Baseline**.
It has deterministic screening quality gates and a provider-neutral external
evidence contract. It is not yet a full Research Orchestration System: there is
no persistent ResearchJob, decision ledger, PaperPlan workflow or notification
delivery.

External models are manually operated research executors. They do not own local
state and no Gemini, Claude or other Provider API is called automatically.

## 2. Frozen acceptance baseline

Read `BASELINE_20260712_RESEARCHJOB_READY.json` before any implementation.

```text
tests_collected: 284
tests_passed: 284
tests_failed: 0
tests_skipped: 0
latest_json_sha256: 82d1e5dd6646e970ffaf4778908709cacd55095965abeedb953522a639667e8d
```

The baseline records one non-blocking Starlette/httpx deprecation warning.
Tests must not modify authoritative run inputs or production signal-review
results.

## 3. Latest real signal state

```text
run_id: 20260707_1341_utc
record_id: 20260707_1341_utc_0001
symbol: 1000BONKUSDT
quality_status: BLOCK
blocker: missing_contract_identity
paper_eligibility: REVIEW_REQUIRED
paper_reason_codes: DERIVATIVES_WARN
```

This is correct fail-closed behavior. It means:

```text
research_capability: ALLOW
owner_review_capability: ALLOW
paper_plan_capability: BLOCK
```

Do not fabricate `contract_identity` or any other market field to make the
candidate pass.

## 4. Current runtime surface

```powershell
cd "G:\Quant test\alpha_hive"
python -m uvicorn server.app:app --host 127.0.0.1 --port 8000
```

Dashboard: `http://127.0.0.1:8000/app/review.html`

Current signal APIs:

```text
GET  /api/signals/health
GET  /api/signals
GET  /api/signals/{record_id}
GET  /api/signals/{record_id}/prompt
POST /api/signals/export
```

ResearchJob code exists but its current implementation is not accepted. The
authoritative 001A route contract remains `/api/research/jobs`; do not treat a
different alias or a list endpoint as accepted behavior.

## 5. Architecture and evidence rules

```text
ResearchTaskEnvelope
  -> manual external execution (Gemini / Claude / future Provider)
  -> provider-neutral JSON
  -> local deterministic validation
  -> immutable ResearchJob store
```

- Historical Grok output is a frozen fixture, not an active Provider.
- `MIMO-EXT-008` is an accepted external-evidence contract fixture.
- All imported external evidence remains `UNVERIFIED_EXTERNAL_EVIDENCE` until a
  later verification stage.
- Quality `BLOCK` is stronger than Paper `REVIEW_REQUIRED`.
- Imported content must never mutate quality gates, Owner decisions or Paper
  plans.

## 6. Important files

```text
AlphaHive_V3/config/research_orchestration_contract.yaml
AlphaHive_V3/reports/BASELINE_20260712_RESEARCHJOB_READY.json
AlphaHive_V3/harness/lib/deep_research_package.py
AlphaHive_V3/harness/lib/signal_review_exporter.py
AlphaHive_V3/harness/lib/external_evidence_normalizer.py
AlphaHive_V3/harness/lib/external_evidence_schema_validator.py
alpha_hive/server/app.py
alpha_hive/server/signal_review_routes.py
alpha_hive/results/signal_review/latest.json
alpha_hive/results/research_jobs/MIMO-EXT-008/mimo_ext_008_bundle.json
```

Never use the legacy nested duplicate:

```text
G:\Quant test\alpha_hive\AlphaHive_V3
```

## 7. Next implementation: RESEARCHJOB-MVP-001A only

The active implementation slice is store and Create/Get only. Do not combine it
with evidence import, verification, Owner decision, PaperPlan, Feishu or
automatic Providers.

Required behavior:

1. Server generates a path-safe `job_` identifier; the client never chooses it.
2. `POST /api/research/jobs` accepts a validated `record_id`, freezes the
   candidate package and persists its hash.
3. Initial Job state is `RESEARCH_JOB_CREATED`, then `AWAITING_EVIDENCE`.
4. Store immutable `job.json`, `candidate_package.json`, `pointers.json` and
   hash-linked `events.jsonl` under `alpha_hive/results/research_jobs/{job_id}`.
5. Every event records sequence, previous/new state, actor, input/output hashes,
   previous event hash and event hash.
6. Writes are atomic and restart-safe. Tests use a temporary store.
7. `GET /api/research/jobs/{job_id}` reconstructs the persisted Job after a
   process restart.
8. No evidence import endpoint in this slice.
9. No write to `AlphaHive_V3/harness/runs/**` or
   `alpha_hive/results/signal_review/**` during tests.

Required APIs:

```text
POST /api/research/jobs
GET  /api/research/jobs/{job_id}
```

## 8. Future slices, in order

```text
001B  evidence import quarantine, validation and immutable evidence records
002   verification and assessment versioned artifacts
003   Owner decision with full input-hash binding and invalidation
004   deterministic PaperPlan engine
005   state-directory outbox and Hermes/Feishu delivery
```

For `001B`, bad files are import-attempt outcomes (`REJECTED_SCHEMA`,
`REJECTED_HASH`, `REJECTED_CUTOFF`, `REJECTED_RECORD_MISMATCH`, `DUPLICATE`),
not automatic terminal Job states. The Job remains `AWAITING_EVIDENCE` after a
rejected manual import.

## 9. Agent deployment

```text
Gemini 3.1 Pro High = maker for one bounded vertical slice
Claude Sonnet/Opus 4.6 = read-only reviewer after maker tests pass
Codex = architecture and final acceptance
Mimo = fixtures, negative cases and low-risk helpers
```

Do not let Gemini and Claude edit the same worktree concurrently. Record the
exact model label used in every delivery report.

Task prompts:

```text
AlphaHive_V3/prompts/researchjob_mvp_001a_gemini.md
AlphaHive_V3/prompts/researchjob_mvp_001a_mimo.md
AlphaHive_V3/prompts/researchjob_mvp_001a_claude_review.md
```

## 10. New-conversation starter

```text
Read these files first:
G:\Quant test\AlphaHive_V3\reports\NEXT_STAGE_HANDOFF_20260712.md
G:\Quant test\AlphaHive_V3\reports\BASELINE_20260712_RESEARCHJOB_READY.json
G:\Quant test\AlphaHive_V3\config\research_orchestration_contract.yaml

Use G:\Quant test as the only workspace. Continue RESEARCHJOB-MVP-001A only.
Before changing code, verify the baseline test pass count and latest.json hash.
Do not edit harness/runs, do not add automatic Providers, do not implement
evidence import, Owner decisions, PaperPlan or notifications in this slice.
```
