# ResearchJob MVP003 Codex implementation handoff — 2026-07-18

**task:** `RESEARCHJOB-MVP-003-CODEX-IMPLEMENTATION-001`  
**status:** `IMPLEMENTED_PENDING_INDEPENDENT_FINAL_AUDIT`  
**scope:** immutable, manually affirmed OwnerDecision persistence only

## Authority and non-authority

The Owner confirmed the one-time governance rules recorded in
`OWNER_APPROVALS.md` item 12: the exact `owner_decision_confirmation_v1` text,
the stable non-secret Owner label, `interactive_owner_confirmation_in_Codex`,
and `immutable_exact_file_hash` preset binding. This is an implementation
authorization only. It is **not** a decision for any job and it grants no
PaperPlan generation, Paper execution, trigger ignition, notification,
credential, data-source or trading authority.

The selected authentication mechanism is procedural: the endpoint records the
declared context and immutable bindings, while an actual per-job affirmative
reply in this Codex conversation remains mandatory. It must never be presented
as cryptographic proof of the human identity.

## Implemented behavior

- Adds manual `POST /api/research/jobs/{job_id}/owner_decision` using the same
  strict JSON parser and payload bound as the evidence/report routes.
- Requires the complete immutable chain: job, record, candidate package,
  canonical evidence set, verification, assessment and assessment-event hash.
- Persists every attempt in the existing immutable attempt journal. Accepted
  decisions are published as `owner_decisions/vNNNN.json`, under the existing
  cross-process job lock, with pointer hashes/sizes and event-chain coverage.
- Accepted `REJECT`, `WATCH`, and `APPROVE_PAPER` transition only from
  `RESEARCH_ASSESSMENT_READY` to `REJECTED`, `WATCHLISTED`, and
  `PAPER_APPROVED` respectively. Invalid decisions retain the current state
  and record `OWNER_DECISION_REJECTED`.
- `APPROVE_PAPER` is fail-closed unless the job is `prospective_live`, has
  `paper_plan_capability=ALLOW`, and binds exactly to an `APPROVED` preset's
  version and canonical SHA-256. The current preset is `DRAFT`; therefore no
  presently reachable request can approve Paper.
- Directory validation, tamper fail-closed behavior, quarantine/fsync recovery
  and pointer/event validation include OwnerDecision artifacts.

## Changed paths

- `G:\\Quant test\\alpha_hive\\server\\research_job_repository.py`
- `G:\\Quant test\\alpha_hive\\server\\research_job_service.py`
- `G:\\Quant test\\alpha_hive\\server\\research_job_routes.py`
- `G:\\Quant test\\AlphaHive_V3\\tests\\test_research_jobs.py`
- `G:\\Quant test\\AlphaHive_V3\\OWNER_APPROVALS.md` (authority record only)

## Verification receipts

- Python compilation of all three ResearchJob server modules: pass.
- Focused suite from `G:\\Quant test\\AlphaHive_V3`:
  `python -m pytest -q tests\\test_research_jobs.py` — **38 passed, 15 subtests
  passed**.
- Full project regression from the same directory: `python -m pytest -q` —
  **388 passed, 15 subtests passed**.
- Both changed-tree whitespace checks passed. Existing Windows line-ending
  notices were informational only.
- New tests prove immutable `WATCH`, tamper fail-closed, rejection journaling,
  historical `APPROVE_PAPER` rejection, quarantine recovery, and five-process
  contention (exactly one accepted `WATCH`, four state conflicts).

## Post-change hashes

| Path | SHA-256 |
|---|---|
| `research_job_repository.py` | `55074636FD4CD2C077AA1441376109792FA0F0E9FC853E969F0AAF6E41844918` |
| `research_job_service.py` | `B7103EF91D48B52137F198BD50E74BE016FC8165B3684F3AB86EE41D796B13A9` |
| `research_job_routes.py` | `807BD50410E4A455F496B4DBEBBDCA75B425D4160AED56BCF620C9D57756B42E` |
| `tests/test_research_jobs.py` | `926B1552D6AA5A47ACCAAC7607CD2A33F1CB1A2659BA450F694999B2D738DC39` |
| `alpha_hive/results/signal_review/latest.json` | `82D1E5DD6646E970FFAF4778908709CACD55095965ABEEDB953522A639667E8D` |

## Next dispatch

Independent DeepSeek final audit is required before this candidate can be
accepted. Use
`agent_tasks/deepseek__codex__researchjob_003_final_audit.md`; its only valid
output is the exact Desktop path declared in that task. Do not activate Paper,
triggers, notifications or trading after the audit.

## 2026-07-18 preset-hash compatibility correction

The later Paper-preset decision-pack review found that the original service
helper used JSON's default whitespace while the deterministic offline
`paper_plan_engine` uses compact canonical JSON. That would make an otherwise
correct future OwnerDecision fail at PaperPlan construction. `_preset_hash` now
uses the engine's exact compact canonical serialization without importing the
offline harness at server runtime. A direct compatibility test was added.

- Focused regression after correction: **39 passed, 15 subtests passed**.
- Full regression after correction: **389 passed, 15 subtests passed**.
- Correct current-DRAFT hash: `3cd1211a0bd7cacd7cc6ed115dc718072ea18c256fa3641be9f674723523a290`.
- Proposed target (`preset_version: v0.1.0`, `status: APPROVED`) hash:
  `a81ad47bbb332ef26d2399c7fae1e58ce1232534406f8b140f9654dd16edb958`.

The original final audit remains valid for every other MVP003 safety property,
but this narrowly scoped correction requires the targeted independent audit
declared below before the compatibility claim is accepted.
