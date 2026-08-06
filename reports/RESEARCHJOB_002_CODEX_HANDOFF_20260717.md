# ResearchJob MVP 002 Codex implementation handoff — 2026-07-17

**task:** `RESEARCHJOB-MVP-002-CODEX-IMPLEMENTATION-001`  
**status:** `ACCEPTED_AFTER_DEEPSEEK_FINAL_AUDIT`  
**scope:** immutable, manually imported verification and assessment only

## Accepted inputs

- Gemini correction: `RESEARCHJOB-MVP-002-GOAL-ARCH-001-CORRECTION-001`
  (`ACCEPTED`): versioned `vNNNN.json`, binding taxonomy and predecessor rules.
- Grok preflight: `RESEARCHJOB-MVP-002-GROK-PREFLIGHT-AUDIT-001`
  (`ACCEPTED`): 001B baseline, safe temporary-store fixtures and extension map.
- No new Owner/T3 decision was created.

## Implemented behavior

- Adds manual-only `POST /api/research/jobs/{job_id}/verification` and
  `POST /api/research/jobs/{job_id}/assessment`.
- Persists accepted reports immutably as `verification/v0001.json` and
  `assessment/v0001.json`; version allocation scans the artifact directory
  under the existing per-job lock.
- Binds reports to job ID, record ID, candidate-package hash, canonical sorted
  evidence-set hash and the accepted predecessor event. Assessment additionally
  binds the verification artifact hash and `EVIDENCE_VERIFIED` event hash.
- Uses `REJECTED_SCHEMA`, `REJECTED_RECORD_MISMATCH`, `REJECTED_BINDING` and
  `DUPLICATE` as fail-closed outcomes. Attempts reuse the existing `imports/`
  journal with an explicit `attempt_kind`; accepted artifacts stay in their
  contract directories.
- Extends pointer coverage, immutable inventory validation, event-chain
  validation, quarantine manifest recovery and job-lock concurrency handling.
- Assessment requires `performance_eligible=false` and rejects directional or
  Owner/Paper action content. No capability, quality, Owner, Paper, outbox,
  provider, scheduler, credential, source or trading path changes were made.

## Changed paths

- `G:\\Quant test\\alpha_hive\\server\\research_job_repository.py`
- `G:\\Quant test\\alpha_hive\\server\\research_job_service.py`
- `G:\\Quant test\\alpha_hive\\server\\research_job_routes.py`
- `G:\\Quant test\\AlphaHive_V3\\tests\\test_research_jobs.py`

## Verification receipts

- Syntax: `python -m py_compile` on all three ResearchJob server files: pass.
- Focused suite: `python -m pytest AlphaHive_V3\\tests\\test_research_jobs.py -q`:
  **35 passed, 15 subtests passed**.
- Formal project regression from `G:\\Quant test\\AlphaHive_V3`:
  `python -m pytest -q`: **358 passed, 15 subtests passed**.
- The workspace-top-level pytest collection is intentionally not a project
  oracle: it includes unrelated `AO_SANDBOX`, archived and optional-dependency
  suites that fail collection. The formal project-root command above is green.
- `signal_review/latest.json` remained unchanged:
  `82D1E5DD6646E970FFAF4778908709CACD55095965ABEEDB953522A639667E8D`.

## Post-change hashes

| Path | SHA-256 |
|---|---|
| `research_job_repository.py` | `E8461CBC5266C7D36306B8B8A5F556296F7D667ABD53ED8383CEF0A2B812B1C2` |
| `research_job_service.py` | `4C815F6F7408EB0CB728A8C677E65EBDEF617B3446311960F479B8CBEF44A7AF` |
| `research_job_routes.py` | `A9826A47E4C21650C9286557FC98937DD3528F3B52746C845D11CE0508934453` |
| `tests/test_research_jobs.py` | `69EEDC880D1193EE69C4838D9C598C3D17A19FE20B30973D5B0C8D1DD34F8C0D` |

## Focused MVP 002 evidence

Temporary-store tests prove the valid two-stage state path, `v0001` immutable
layout and pointer coverage; missing/wrong bindings, invalid state and
directional assessment rejection; duplicate handling; tamper fail-closed;
crash recovery after the quarantine manifest; and five-process concurrent
verification with exactly one accepted artifact.

## Next dispatch

DeepSeek `RESEARCHJOB-MVP-002-FINAL-AUDIT-001` is accepted `GREEN` (18/18
PASS; 35 focused and 358 full-project tests). Do not advance to provider
automation, PaperPlan, notification, trigger or trading. The only next
workflow state is the T3/Owner-controlled decision gate and it must wait for
approval.
