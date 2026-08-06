# RESEARCHJOB-FIRST-MANUAL-EVIDENCE-001

**task_id:** `RESEARCHJOB-FIRST-MANUAL-EVIDENCE-001`  
**agent:** Gemini external agent proxy  
**tier:** T1/T2 manually operated public-source research; no trading  
**repository write authority:** Codex only  
**exact evidence output:** `C:\\Users\\10639\\Desktop\\AlphaHive_V3_A_DATA_HEALTH_deliverables\\agent_outputs\\antigravity\\RESEARCHJOB-FIRST-MANUAL-EVIDENCE-001.json`  
**exact PARK report output (only if no admissible evidence exists):** `C:\\Users\\10639\\Desktop\\AlphaHive_V3_A_DATA_HEALTH_deliverables\\agent_outputs\\antigravity\\RESEARCHJOB-FIRST-MANUAL-EVIDENCE-001-PARK.md`

## Owner-authorized objective

Manually research public, no-credential sources for the existing research-only
job below and produce a provider-neutral evidence-import bundle. Public web
reading is authorized only for this task. Do not use private sources, API keys,
automation, repository writes, notifications, Paper plans or trading.

## Immutable job facts

- `job_id`: `job_a6f36bc3-5fd5-405a-abcd-dc4104a7529e`
- `record_id`: `20260707_1341_utc_0001`
- symbol: `1000BONKUSDT`
- mode: `HISTORICAL_REPLAY`
- external-information cutoff: `2026-07-07T13:41:16.355313+00:00`
- current state: `AWAITING_EVIDENCE`
- purpose: research evidence only; this job is quality `BLOCK` and cannot
  become a PaperPlan or virtual trade.

## Required reading

Read the shared materials in the order required by
`G:\\Quant test\\AlphaHive_V3\\PROJECT_REQUIRED_READING.md`, then read this
task, `config/research_orchestration_contract.yaml`,
`config/deep_research_contract.yaml`,
`reports/RESEARCHJOB_FIRST_MANUAL_JOB_20260717.md`, current
`alpha_hive/server/research_job_service.py`, and
`AlphaHive_V3/tests/test_research_jobs.py`.

## Evidence rules

1. Use only publicly accessible, no-credential source pages. Record the direct
   URL and a verifiable publication time for every claim.
2. Every source publication time must be at or before the immutable cutoff.
   Do not use later commentary, outcomes, performance or hindsight.
3. Keep claims factual, direction-neutral and explicitly
   `UNVERIFIED_EXTERNAL_EVIDENCE`; do not infer a LONG/SHORT conclusion.
4. The JSON bundle must exactly satisfy the current `agent_artifact_bundle_v1`
   validator and its hash rules. Recompute every artifact `artifact_hash` and
   the top-level `artifact_hash` exactly as the repository test helper does.
5. Include only evidence for this exact job/record. Set
   `performance_eligible: false`. Do not include a content-hash pathname.
6. If no admissible source can be proven cutoff-safe, do not write a JSON
   bundle. Write the exact PARK Markdown report instead, explaining each
   rejected source and the missing evidence.

## Hard boundaries

Do not modify any repository, configuration, results, job store, test, data,
scheduler, database, outbox, credential or external account. Do not import the
bundle. Do not send a message or make any Paper/Owner/trigger/trading decision.
Write only one of the exact Desktop outputs above. In the completion message,
return the chosen output path, status, source count, cutoff evidence and PARK
items.
