# RESEARCHJOB-MVP-003-FINAL-AUDIT-001

**task_id:** `RESEARCHJOB-MVP-003-FINAL-AUDIT-001`  
**agent:** DeepSeek external agent proxy  
**tier:** T1/T2 independent, read-only final audit  
**repository write authority:** Codex only  
**exact Desktop output:** `C:\\Users\\10639\\Desktop\\AlphaHive_V3_A_DATA_HEALTH_deliverables\\agent_outputs\\deepseek\\RESEARCHJOB-MVP-003-FINAL-AUDIT-001.md`

## Objective

Independently audit the ResearchJob MVP003 OwnerDecision implementation
candidate. This is an audit only. Do not modify code, tests, config, results,
scheduler, database, outbox, credentials, or any external system.

## Required reading

Read shared governance in the order required by
`G:\\Quant test\\AlphaHive_V3\\PROJECT_REQUIRED_READING.md`, then this task and:

- `G:\\Quant test\\AlphaHive_V3\\reports\\RESEARCHJOB_MVP003_CODEX_HANDOFF_20260718.md`
- `G:\\Quant test\\AlphaHive_V3\\reports\\OWNER_DECISION_CONFIRMATION_TEMPLATE_20260718.md`
- `G:\\Quant test\\AlphaHive_V3\\OWNER_APPROVALS.md`
- `G:\\Quant test\\AlphaHive_V3\\config\\paper_execution_presets.yaml`
- `G:\\Quant test\\alpha_hive\\server\\research_job_repository.py`
- `G:\\Quant test\\alpha_hive\\server\\research_job_service.py`
- `G:\\Quant test\\alpha_hive\\server\\research_job_routes.py`
- `G:\\Quant test\\AlphaHive_V3\\tests\\test_research_jobs.py`

## Required checks

1. Hash the three server files, test file and
   `G:\\Quant test\\alpha_hive\\results\\signal_review\\latest.json` before and
   after. Verify MVP003 changes stay inside its five-path allowlist in the
   handoff; distinguish pre-existing workspace changes from this slice.
2. Run from `G:\\Quant test\\AlphaHive_V3`:
   `python -m pytest -q tests\\test_research_jobs.py` and `python -m pytest -q`.
3. Inspect strict JSON handling, payload size/depth behavior and no provider,
   web/API, notification, PaperPlan, scheduler, database, credential or
   trading call introduced by this route.
4. Prove accepted decisions require exact hashes for job, record, candidate,
   evidence set, verification, assessment and predecessor assessment event;
   prove immutable `owner_decisions/vNNNN.json`, pointers and file-hash/tamper
   coverage fail closed.
5. Prove the state machine allows only `RESEARCH_ASSESSMENT_READY` to
   `REJECTED`, `WATCHLISTED`, or `PAPER_APPROVED` based on `REJECT`, `WATCH`,
   or `APPROVE_PAPER`; rejected attempts must preserve state and remain
   journaled/evented.
6. Prove `APPROVE_PAPER` is blocked for historical replay, BLOCK/non-ALLOW
   capability, and the present `DRAFT` preset configuration. Confirm this
   implementation neither creates a PaperPlan nor makes an actual Owner
   decision. Specifically report that chat confirmation is procedural context,
   not cryptographic identity proof.
7. Verify quarantine/fsync recovery and cross-process contention. Check the
   provided tests and code path: one accepted OwnerDecision only, no duplicate
   immutable artifact or state transition.

## Hard boundaries and report

Do not write anywhere except the exact Desktop report. Do not call external
services. Do not submit any OwnerDecision or change a job state. Include a
header, commands/hashes, line-level evidence, PASS/ADVISORY/PARK matrix,
before/after mutation proof, any genuine defect, regressions, and `SELF_CHECK`.
Do not claim manual Codex-chat confirmation is cryptographic authentication.
