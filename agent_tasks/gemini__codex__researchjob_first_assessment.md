# RESEARCHJOB-FIRST-ASSESSMENT-GEMINI-001

**task_id:** `RESEARCHJOB-FIRST-ASSESSMENT-GEMINI-001`  
**agent:** Gemini external agent proxy  
**tier:** T1/T2 read-only direction-neutral assessment candidate  
**repository write authority:** Codex only  
**hard dependency:** target job must be `EVIDENCE_VERIFIED`  
**exact candidate output:** `C:\\Users\\10639\\Desktop\\AlphaHive_V3_A_DATA_HEALTH_deliverables\\agent_outputs\\antigravity\\RESEARCHJOB-FIRST-ASSESSMENT-GEMINI-001.json`  
**exact PARK output:** `C:\\Users\\10639\\Desktop\\AlphaHive_V3_A_DATA_HEALTH_deliverables\\agent_outputs\\antigravity\\RESEARCHJOB-FIRST-ASSESSMENT-GEMINI-001-PARK.md`

## Objective

Read the already accepted evidence and verification for
`job_a6f36bc3-5fd5-405a-abcd-dc4104a7529e` and produce one candidate
`research_job_assessment_v1` artifact. This is a research synthesis only. It
must preserve uncertainty, remain direction-neutral and must not create an
OwnerDecision or PaperPlan.

## Required reading

Read the shared materials in the order required by
`G:\\Quant test\\AlphaHive_V3\\PROJECT_REQUIRED_READING.md`, then this task,
the accepted evidence-import handoff, the accepted Gemini verification
correction output, current `config/research_orchestration_contract.yaml`,
`config/deep_research_contract.yaml`, current ResearchJob server files and
`AlphaHive_V3/tests/test_research_jobs.py`.

## Live binding requirements

At execution time verify the target job is exactly `EVIDENCE_VERIFIED` and read
the live binding context. Bind the candidate exactly to:

- job: `job_a6f36bc3-5fd5-405a-abcd-dc4104a7529e`
- record: `20260707_1341_utc_0001`
- candidate package: `e1be947478dade0704ce7bde0c66602ab4bee3447c49cb813fc14222308e565f`
- evidence set: `fd2fb78820ffdfee2eb90bea3fa4369698814be0bbfa67402023f6dc013f4425`
- verification hash: `8e164d7dbf828e082827bf796bce0f4909cfea699c314261c3b7621865359882`
- predecessor hash: the live `EVIDENCE_VERIFIED` event hash, not a guessed value.

## Assessment rules

1. Include `schema_version: research_job_assessment_v1`, all required binding
   fields, `synthesis_findings`, `performance_eligible: false` and an
   `artifact_hash` calculated with the production `_schema_canonical_json`
   rule: `json.dumps(value, sort_keys=True, ensure_ascii=False, default=str)`
   with default separators.
2. Summarize only factual, uncertainty-preserving findings. The imported
   public news remains `UNVERIFIED_EXTERNAL_EVIDENCE`; it does not repair
   contract identity or establish performance.
3. Do not include directional or execution terms in `synthesis_findings`:
   `LONG`, `SHORT`, `BUY`, `SELL`, `PAPER_PLAN`, `OWNER_DECISION`, `ENTRY`,
   `EXIT`. Do not include credentials or instructions to act.
4. Explicitly preserve that the historical replay is qualitative-only, the
   current quality is `BLOCK`, and `paper_plan_capability` remains `BLOCK`.

## Hard boundaries

Do not modify any repository, configuration, results, job store, test, data,
scheduler, database, outbox, credential or external account. Do not submit the
candidate. Do not create OwnerDecision, PaperPlan, notification, trigger or
trading activity. If the state or bindings differ, write only the exact PARK
output and state the observed values.
