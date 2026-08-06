# ResearchJob evidence import 001 handoff (2026-07-17)

**task:** `RESEARCHJOB-EVIDENCE-IMPORT-001`  
**owner:** Codex  
**authorization:** Owner instruction to execute the recommended sequence  
**input:** `C:\\Users\\10639\\Desktop\\AlphaHive_V3_A_DATA_HEALTH_deliverables\\agent_outputs\\grok\\RESEARCHJOB-FIRST-MANUAL-EVIDENCE-GROK-001.json`  
**target job:** `job_a6f36bc3-5fd5-405a-abcd-dc4104a7529e`  
**result:** `ACCEPTED`

## Receipt

- `import_id`: `imp_9200a15a-5686-4937-a212-c335694ecf44`
- `event_id`: `evt_aee73a88-6212-42b0-b09a-c60ee617757f`
- submitted: `2026-07-17T13:59:33.845992+00:00`
- bundle hash: `e038af4591f65f2fc6766c573955122ae2f416ef6e9531d4f3b7ffabb7bf3d5a`
- raw body hash: `026211f2defff5a2a0deef1dc3593b20646681dff4e54cd3f58119883dc75c86`
- content hash: `12df2624ab542dca5cde776ddf2ef374ca6409117cad147a7265e97796c1c9b0`
- artifacts accepted: `4`
- schema/hash/record/cutoff checks: all `true`; error codes: `[]`

## State and integrity verification

- state transition: `AWAITING_EVIDENCE -> EVIDENCE_IMPORTED`
- evidence: `evidence/12df2624ab542dca5cde776ddf2ef374ca6409117cad147a7265e97796c1c9b0.json`
- import receipt: `imports/imp_9200a15a-5686-4937-a212-c335694ecf44.json`
- event chain sequence is intact through sequence 3; the new event's
  `previous_event_hash` equals the prior `AWAITING_EVIDENCE` event hash.
- `pointers.json` now points to the evidence/import files and the new latest
  event hash; quarantine is empty.
- Pre-existing target files changed only as the authorized job-state/event/
  pointer update. New files are limited to the immutable evidence and import
  receipt. `alpha_hive/results/signal_review/latest.json` SHA-256 remained
  unchanged (`82D1E5DD6646E970FFAF4778908709CACD55095965ABEEDB953522A639667E8D`,
  case-insensitive comparison).
- Regression: `python -m pytest -q tests/test_research_jobs.py` returned
  `35 passed, 15 subtests passed`.

## Retained limits

This import advances research evidence only. The job remains historical,
quality `BLOCK`, `performance_eligible=false` and `paper_plan_capability=BLOCK`;
it cannot become `PAPER_APPROVED` or a virtual trade.

## Next stage and dispatch

Dispatch Gemini's independent read-only verification task now:
`agent_tasks/gemini__codex__researchjob_first_evidence_verification.md`.
Expected output is
`C:\\Users\\10639\\Desktop\\AlphaHive_V3_A_DATA_HEALTH_deliverables\\agent_outputs\\antigravity\\RESEARCHJOB-FIRST-EVIDENCE-VERIFICATION-GEMINI-001.json`
or the exact PARK file in that directory. Gemini must not submit the report;
Codex will accept it and, only if valid, submit the candidate verification
artifact. Assessment remains sequential after verification.
