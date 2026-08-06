# RESEARCHJOB-MVP-003-GOAL-ARCH-001

**task_id:** `RESEARCHJOB-MVP-003-GOAL-ARCH-001`  
**agent:** Gemini external agent proxy, long-thread goal mode  
**tier:** T1/T2 read-only architecture and acceptance design  
**repository write authority:** Codex only  
**exact Desktop output:** `C:\\Users\\10639\\Desktop\\AlphaHive_V3_A_DATA_HEALTH_deliverables\\agent_outputs\\antigravity\\RESEARCHJOB-MVP-003-GOAL-ARCH-001.md`

## Long-thread objective

Produce an implementation-ready, Owner-safe architecture and acceptance package
for ResearchJob MVP 003: an immutable, manual OwnerDecision artifact that
follows `RESEARCH_ASSESSMENT_READY` and may yield only `REJECT`, `WATCH` or
`APPROVE_PAPER`. This is design only: no signature, Owner decision, PaperPlan,
notification or trading action may be created.

## Required reading

Read shared materials in the exact order required by
`G:\\Quant test\\AlphaHive_V3\\PROJECT_REQUIRED_READING.md`, then this task,
`config/research_orchestration_contract.yaml`,
`config/deep_research_contract.yaml`, `OWNER_APPROVALS.md`,
`OWNER_DECISIONS_NEEDED.md`, the accepted 001B/002 handoffs, the 002 acceptance
record, the first manual job receipt, current ResearchJob server files/tests,
and Grok's `PAPERPLAN-MVP-004-PREFLIGHT-001` report.

## Required design coverage

1. Define the exact manual OwnerDecision API, response semantics and immutable
   `owner_decisions/vNNNN.json` layout.
2. Bind decision to job/record, candidate package, evidence set, verification,
   assessment and predecessor event hashes; define canonical hash rules and
   fail-closed missing-data behavior.
3. Define state/events for `REJECT`, `WATCH` and `APPROVE_PAPER`; prove only
   the latter can precede a PaperPlan and it must still be separately gated.
4. Define a confirmation-text version, owner-confirmation shape and a strict
   boundary proving an agent cannot sign or synthesize the decision.
5. Define capability and eligibility checks: historical or `BLOCK` jobs,
   including the existing BONK negative fixture, must reject `APPROVE_PAPER`.
6. Preserve the 001B/002 lock, quarantine, fsync/recovery, immutable pointer,
   event-chain, tamper and concurrency guarantees.
7. Provide test/failure matrix, temporary-store strategy, exact Codex allowlist
   and the smallest Owner decision package required only for later implementation.

## Hard boundaries

No repository/config/test/result write; no provider/web/API call; no actual
Owner signature, PaperPlan, notification, trigger, credential or trading
action. Write only the exact Desktop report. Include header, architecture map,
API/state table, schema/binding rules, failure matrix, test matrix, Codex
allowlist, Owner decision list and `SELF_CHECK`. Use `PARK` rather than guessing
where a true Owner choice is missing.
