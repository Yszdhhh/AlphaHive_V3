# PROSPECTIVE-LIFECYCLE-PREFLIGHT-CORRECTION-001

**Agent:** Gemini / antigravity  
**Tier:** T1/T2 read-only architecture correction  
**Exact Desktop output:** `C:\Users\10639\Desktop\AlphaHive_V3_A_DATA_HEALTH_deliverables\agent_outputs\antigravity\PROSPECTIVE-LIFECYCLE-PREFLIGHT-CORRECTION-001.md`

## Objective

Correct the accepted-parts-only preflight before any production lifecycle work
is considered. Do not propose an implementation that conflates the current
historical-only assessment contract with a future prospective Paper lifecycle.

## Required reading

Read the shared required-reading sequence, then this task and:

- the original Desktop report `PROSPECTIVE-LIFECYCLE-PREFLIGHT-001.md`;
- `reports\PROSPECTIVE_LIFECYCLE_PREFLIGHT_ACCEPTANCE_20260719.md`;
- `alpha_hive\server\research_job_service.py`;
- `alpha_hive\server\research_job_repository.py`;
- `harness\lib\paper_plan_engine.py`;
- `config\research_orchestration_contract.yaml`;
- `OWNER_APPROVALS.md` and `OWNER_DECISIONS_NEEDED.md`.

## Required correction

1. Prove and resolve on paper the mismatch: current assessment validation
   requires `performance_eligible is false`, while PaperPlan construction
   requires a job value of true.
2. Resolve the state mismatch: the engine expects
   `RESEARCH_ASSESSMENT_READY`, while an accepted `APPROVE_PAPER` OwnerDecision
   transitions the job to `PAPER_APPROVED`.
3. Specify a single source of truth, compatibility/migration constraints,
   exact immutable bindings, rejection cases and only the minimum tests/file
   allowlist necessary for a future prospective-only contract.
4. Mark every real PaperPlan creation, Paper execution, trigger, Feishu
   delivery, credential and trade action `PARK`; do not create a route or code.

## Hard boundaries

Read only; write only the exact Desktop report. No repository/config/result
mutation, no network/provider call, no route invocation, no ResearchJob,
evidence, OwnerDecision, PaperPlan, notification, trigger or trade action.
Use `GREEN`, `PARK`, or `FAIL`; unsupported conclusions must be PARK.
