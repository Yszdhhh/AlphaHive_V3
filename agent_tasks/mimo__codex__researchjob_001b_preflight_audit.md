# RESEARCHJOB-MVP-001B-PREFLIGHT-AUDIT-001 — Mimo

**task_id:** `RESEARCHJOB-MVP-001B-PREFLIGHT-AUDIT-001`  
**agent:** Mimo  
**tier:** T1 read-only contract and implementation preflight  
**repository write authority:** Codex only  
**exact Desktop output:** `C:\Users\10639\Desktop\AlphaHive_V3_A_DATA_HEALTH_deliverables\agent_outputs\mimo\RESEARCHJOB-MVP-001B-PREFLIGHT-AUDIT-001.md`

## Objective

Independently inspect the current 001B evidence-import prerequisites and report
what Codex must implement. This is a bounded audit, not an implementation task.
It may run in parallel with Gemini's goal-mode architecture package, but it
must not duplicate or rewrite Gemini's report.

## Required reading (in order)

1. `G:\Quant test\AGENTS.md`
2. `G:\Quant test\AlphaHive_V3\AGENTS.md`
3. `G:\Quant test\AlphaHive_V3\PROJECT_REQUIRED_READING.md`
4. `G:\Quant test\AlphaHive_V3\PROJECT_OPERATING_PLAYBOOK.md`
5. `G:\Quant test\AlphaHive_V3\agent_tasks\README.md`
6. `G:\Quant test\AlphaHive_V3\config\research_orchestration_contract.yaml`
7. `G:\Quant test\AlphaHive_V3\reports\NEXT_STAGE_HANDOFF_20260712.md`
8. `G:\Quant test\AlphaHive_V3\harness\lib\external_evidence_normalizer.py`
9. `G:\Quant test\AlphaHive_V3\harness\lib\external_evidence_schema_validator.py`
10. `G:\Quant test\AlphaHive_V3\tests\test_grok_regression.py`
11. `G:\Quant test\AlphaHive_V3\reports\RESEARCHJOB_001A_FIX03_CODEX_HANDOFF_20260716.md`

## Checks

- Locate the current provider-neutral evidence schema and normalizer entrypoint.
- Map required fields, artifact hashes, cutoff fields and record/job binding.
- Check whether an evidence-import route/store already exists; do not infer
  completion from fixtures or documentation alone.
- Identify missing quarantine, import-attempt, duplicate and immutable-publish
  protections.
- Propose focused negative cases for schema/hash/cutoff/record mismatch,
  malformed files, path traversal, duplicate imports, concurrent imports and
  crash recovery.
- Confirm that no rejected evidence can mutate quality gates, Owner decisions,
  PaperPlan capability or signal-review authoritative data.

## Prohibited actions

- Do not edit repository, fixtures, tests, database, Parquet, scheduler,
  credentials or `_bus/`.
- Do not call external providers, fetch data, import evidence or create a
  PaperPlan.
- Do not claim 001B is implemented; report `UNVERIFIED` if code is absent.

## Required report shape

Include agent, exact task_id, UTC timestamp, inputs, file/line evidence,
PASS/ADVISORY/PARK matrix, prioritized Codex worklist, unresolved Owner items
and SELF_CHECK. Use only the exact Desktop output path above.
