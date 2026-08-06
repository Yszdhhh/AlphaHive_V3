# F21-PROMPT-003-FRAMEWORK-FREEZE-001 — Agy / Gemini 3.1 Pro

**task_id:** `F21-PROMPT-003-FRAMEWORK-FREEZE-001`  
**tier:** T1/T2 read-only architecture and contract audit  
**agent:** Agy / Gemini 3.1 Pro  
**repository write authority:** Codex only  
**exact Desktop output:** `C:\Users\10639\Desktop\AlphaHive_V3_A_DATA_HEALTH_deliverables\agent_outputs\antigravity\F21-PROMPT-003-FRAMEWORK-FREEZE-001.md`

## Objective

Determine whether the current direction-neutral deep-research prompt framework
is ready to be frozen as v1, and list only the smallest contract/documentation
changes still required. This is an audit and freeze recommendation, not a
request to modify the repository or activate Paper/trigger behavior.

## Required reading (in order)

1. `G:\Quant test\AGENTS.md`
2. `G:\Quant test\AlphaHive_V3\AGENTS.md`
3. `G:\Quant test\AlphaHive_V3\PROJECT_REQUIRED_READING.md`
4. `G:\Quant test\AlphaHive_V3\PROJECT_OPERATING_PLAYBOOK.md`
5. `G:\Quant test\AlphaHive_V3\agent_tasks\README.md`
6. `G:\Quant test\AlphaHive_V3\config\deep_research_contract.yaml`
7. `G:\Quant test\AlphaHive_V3\prompts\deep_research_template_v1.md`
8. `G:\Quant test\AlphaHive_V3\harness\lib\deep_research_package.py`
9. `G:\Quant test\AlphaHive_V3\reports\PROMPT_RERENDER_AUDIT.md`
10. `G:\Quant test\AlphaHive_V3\reports\F21_REVIEW_PACKAGE_20260716.md`
11. `G:\Quant test\AlphaHive_V3\config\research_orchestration_contract.yaml`

## Checks required

- Verify the rendered output has no `LONG_THESIS_STRONGER` or
  `SHORT_THESIS_STRONGER` enum and retains `no_direction_claim=true`.
- Verify historical replay cutoff, prospective-live cutoff, provider-neutral
  wording, GRAVEYARD prohibitions, `UNVERIFIED` semantics, allowlist/denylist,
  mandatory sections and structured output fields.
- Check whether `contract_version: v1.0.0-draft` and
  `status: draft` are the only reasons the framework is not freeze-ready.
- Identify any mismatch between the prompt contract, ResearchJob contract and
  `paper_execution_presets.yaml` that would cause a prompt to imply Paper
  eligibility or an execution decision.
- Confirm OI/funding quantiles remain `NOT_COMPUTED`/dormant and no trigger
  ignition is implied.

## Prohibited actions

- Do not edit `G:\Quant test\AlphaHive_V3\`, `_bus/`, tests, config or prompts.
- Do not modify thresholds, scanner logic, Paper eligibility, source paths,
  credentials, scheduler, databases, Parquet or checkpoints.
- Do not call external providers, browse for market evidence, or produce a
  directional thesis.
- Do not treat a design recommendation as Owner approval.

## Required report shape

The Desktop report must contain: `agent`, exact `task_id`, UTC timestamp,
inputs read, status (`GREEN`, `PARK` or `UNVERIFIED`), a PASS/ADVISORY/PARK
matrix, freeze recommendation, exact unresolved items, and `SELF_CHECK`.
The report must explicitly say whether the framework is **FROZEN_V1**,
**FREEZE_READY_WITH_OWNER_DOC**, or **NOT_READY**.
