# RESEARCHJOB-MVP-003-PRESET-HASH-CORRECTION-AUDIT-001

**task_id:** `RESEARCHJOB-MVP-003-PRESET-HASH-CORRECTION-AUDIT-001`  
**agent:** DeepSeek external agent proxy  
**tier:** T1/T2 narrow independent correction audit  
**repository write authority:** Codex only  
**exact Desktop output:** `C:\\Users\\10639\\Desktop\\AlphaHive_V3_A_DATA_HEALTH_deliverables\\agent_outputs\\deepseek\\RESEARCHJOB-MVP-003-PRESET-HASH-CORRECTION-AUDIT-001.md`

## Objective

Read-only audit only. Verify the correction that makes the ResearchJob
OwnerDecision preset hash exactly equal to the deterministic offline
PaperPlan-engine preset hash. Do not modify any file or submit any request.

## Required reading

Read shared governance in the required order, then this task and:

- `reports/RESEARCHJOB_MVP003_CODEX_HANDOFF_20260718.md`;
- `reports/RESEARCHJOB_MVP003_FINAL_AUDIT_ACCEPTANCE_20260718.md`;
- `config/paper_execution_presets.yaml`;
- `harness/lib/paper_plan_engine.py`;
- `G:\\Quant test\\alpha_hive\\server\\research_job_service.py`;
- `tests/test_research_jobs.py`.

## Required checks

1. Recompute the current DRAFT preset hash independently using both functions;
   both must equal
   `3cd1211a0bd7cacd7cc6ed115dc718072ea18c256fa3641be9f674723523a290`.
2. In memory only, set `preset_version: v0.1.0` and `status: APPROVED`; both
   functions must equal
   `a81ad47bbb332ef26d2399c7fae1e58ce1232534406f8b140f9654dd16edb958`.
   Do not write this target configuration.
3. Confirm self-reference fields are excluded consistently and canonical JSON
   matches exactly (sort keys, UTF-8, no ASCII escaping, compact separators,
   `default=str`).
4. Run `python -m pytest -q tests\\test_research_jobs.py` and `python -m pytest -q`
   from `G:\\Quant test\\AlphaHive_V3`; verify the direct compatibility test.
5. Hash the corrected service and test files before/after; search the changed
   slice for PaperPlan creation, configuration mutation, provider/network,
   notification, trigger and trading calls. There must be none.

## Hard boundaries and report

Write only the exact Desktop report. Include command receipts, before/after
hashes, PASS/ADVISORY/PARK matrix, line evidence and `SELF_CHECK`. Explicitly
state that the preset remains DRAFT and this correction grants no Paper,
trigger, notification or trading authority.
