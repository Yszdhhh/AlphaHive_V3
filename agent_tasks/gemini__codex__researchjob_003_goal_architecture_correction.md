# RESEARCHJOB-MVP-003-GOAL-ARCH-001-CORRECTION-001

**task_id:** `RESEARCHJOB-MVP-003-GOAL-ARCH-001-CORRECTION-001`  
**agent:** Gemini external agent proxy  
**tier:** T1/T2 read-only architecture-document correction  
**repository write authority:** Codex only  
**required source report:** `C:\\Users\\10639\\Desktop\\AlphaHive_V3_A_DATA_HEALTH_deliverables\\agent_outputs\\antigravity\\RESEARCHJOB-MVP-003-GOAL-ARCH-001.md`  
**exact Desktop output:** `C:\\Users\\10639\\Desktop\\AlphaHive_V3_A_DATA_HEALTH_deliverables\\agent_outputs\\antigravity\\RESEARCHJOB-MVP-003-GOAL-ARCH-001-CORRECTION-001.md`

## Objective

Produce a correction-only supplement to the original MVP003 architecture
report. Do not rewrite history, alter the original report or implement any
code. The correction must make the package implementation-ready while retaining
every T3 Owner boundary.

## Required reading

Read the shared materials in the order required by
`G:\\Quant test\\AlphaHive_V3\\PROJECT_REQUIRED_READING.md`, then this task,
the original source report, `config/research_orchestration_contract.yaml`,
`OWNER_DECISIONS_NEEDED.md`, `OWNER_APPROVALS.md`, current ResearchJob server
files and `AlphaHive_V3/tests/test_research_jobs.py`.

## Mandatory corrections

1. Add a formal header: agent, task_id, UTC timestamp, exact inputs, verdict
   and unresolved items.
2. Provide an explicit API/state/event table for `REJECT`, `WATCH` and
   `APPROVE_PAPER`, including invalid-state, duplicate-version and binding
   failure behavior.
3. Define the exact fail-closed pointer/GET-validation extensions required for
   `owner_decisions/vNNNN.json`, its pointer and event-chain entry.
4. Separate design facts from Owner choices. List the smallest T3 package that
   must be supplied before implementation: the authoritative confirmation-text
   source/version, allowed Owner identity/authentication context, and the
   immutable selected-preset binding policy. Do not invent any of these values.
5. State exact validation constraints for `direction`,
   `selected_preset_version` and `owner_confirmation` across each decision,
   including why the historical quality-BLOCK BONK fixture cannot use
   `APPROVE_PAPER`.
6. Give the complete temporary-store/concurrency/tamper/failure-test matrix and
   preserve the existing allowlist. Mark all Paper, notification, trigger and
   trading work PARK.

## Hard boundaries

No repository/config/test/result write; no public-web/provider/API call; no
actual Owner signature, PaperPlan, notification, trigger, credential or trading
action. Write only the exact Desktop output. If a fact cannot be determined
without an Owner choice, mark it `PARK / OWNER_DECISION_REQUIRED`, not GREEN.
