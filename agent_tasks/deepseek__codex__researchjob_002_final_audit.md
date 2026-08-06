# RESEARCHJOB-MVP-002-FINAL-AUDIT-001

**task_id:** `RESEARCHJOB-MVP-002-FINAL-AUDIT-001`  
**agent:** DeepSeek external agent proxy  
**tier:** T1/T2 independent, read-only final audit  
**repository write authority:** Codex only  
**exact Desktop output:** `C:\\Users\\10639\\Desktop\\AlphaHive_V3_A_DATA_HEALTH_deliverables\\agent_outputs\\deepseek\\RESEARCHJOB-MVP-002-FINAL-AUDIT-001.md`

## Objective

Independently audit the ResearchJob MVP 002 implementation candidate. Verify
the immutable, versioned manual verification-and-assessment state path,
binding, recovery, event/pointer integrity, concurrency and non-mutation
boundaries. This is an audit only: do not modify the repository or test files.

## Required reading

Read shared governance in the order required by
`G:\\Quant test\\AlphaHive_V3\\PROJECT_REQUIRED_READING.md`, then this task,
the orchestration contract, the Gemini 002 architecture and correction reports,
the Grok 002 preflight report, and:

- `G:\\Quant test\\AlphaHive_V3\\reports\\RESEARCHJOB_002_CODEX_HANDOFF_20260717.md`
- current `G:\\Quant test\\alpha_hive\\server\\research_job_repository.py`
- current `G:\\Quant test\\alpha_hive\\server\\research_job_service.py`
- current `G:\\Quant test\\alpha_hive\\server\\research_job_routes.py`
- current `G:\\Quant test\\AlphaHive_V3\\tests\\test_research_jobs.py`

## Required checks

- Hash the three server files, the test file and `signal_review/latest.json`
  before/after. Verify only the four allowlisted implementation/test files
  changed for MVP 002.
- Run `python -m pytest tests\\test_research_jobs.py -q` and `python -m pytest -q`
  from `G:\\Quant test\\AlphaHive_V3`.
- Verify both routes use strict manual JSON input and never invoke providers.
- Prove the only accepted transition path is
  `EVIDENCE_IMPORTED -> EVIDENCE_VERIFIED -> RESEARCH_ASSESSMENT_READY`.
- Verify `vNNNN.json` allocation under job lock; artifact and pointer coverage;
  canonical evidence-set and predecessor bindings; rejection taxonomy;
  duplicate handling; tamper fail-closed; quarantine/fsync recovery and
  cross-process concurrency.
- Verify assessment stays direction-neutral and `performance_eligible=false`,
  with no quality/capability/Owner/Paper/outbox/scheduler/database/trading
  mutation.

## Hard boundaries and report

No repository, config, fixture, results, scheduler, database, outbox or
external-system writes; no provider/web/API calls; no Owner/Paper/trigger/
credential/trading action. Write only the exact Desktop output. Include header,
file:line evidence, command receipts, before/after hashes, PASS/ADVISORY/PARK
matrix, regression comparison, any true Owner decision, and `SELF_CHECK`.
