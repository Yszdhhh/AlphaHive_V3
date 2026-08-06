# RESEARCHJOB-MVP-003-GROK-PREFLIGHT-AUDIT-001

**task_id:** `RESEARCHJOB-MVP-003-GROK-PREFLIGHT-AUDIT-001`  
**agent:** Grok external agent proxy  
**tier:** T1 read-only prerequisite and negative-fixture audit  
**repository write authority:** Codex only  
**exact Desktop output:** `C:\\Users\\10639\\Desktop\\AlphaHive_V3_A_DATA_HEALTH_deliverables\\agent_outputs\\grok\\RESEARCHJOB-MVP-003-GROK-PREFLIGHT-AUDIT-001.md`

## Objective

Independently audit MVP003 OwnerDecision prerequisites in the accepted
ResearchJob 002 store. Map what exists, what fails closed today, and what Codex
must implement for an immutable manual OwnerDecision. This is an audit only;
do not write a decision, signature, PaperPlan or repository content.

## Required reading

Read governance in the order required by
`G:\\Quant test\\AlphaHive_V3\\PROJECT_REQUIRED_READING.md`, then this task,
`config/research_orchestration_contract.yaml`, `config/deep_research_contract.yaml`,
`OWNER_APPROVALS.md`, `OWNER_DECISIONS_NEEDED.md`, accepted 001B/002 handoffs,
the first manual-job receipt, current ResearchJob server files/tests and
Grok's accepted MVP004 PaperPlan preflight.

## Required checks

- Hash the four MVP002 implementation/test files and `signal_review/latest.json`
  before/after the audit.
- Map live job state, API, event ceiling, pointer inventory and quarantine
  extension points for `owner_decisions/vNNNN.json`.
- Audit all contract-required Owner fields and the `REJECT` / `WATCH` /
  `APPROVE_PAPER` + `LONG` / `SHORT` / `NONE` decision space.
- Prove that the current historical `BLOCK` BONK job rejects any future
  `APPROVE_PAPER` and is a permanent negative fixture.
- Specify reject/duplicate/idempotency, tamper, crash and concurrent-decision
  risks; identify only actual T3 Owner choices.
- Give a prioritized Codex worklist and temporary-store test matrix. Separate
  facts from recommendations and use PARK for missing authority.

## Hard boundaries and output

No repository/config/test/data/result/scheduler/database/outbox write; no
provider/web/API call; no signature, Owner decision, direction, PaperPlan,
notification, credential, trigger or trading action. Write only the exact
Desktop report with header, file:line evidence, PASS/ADVISORY/PARK matrix,
worklist, test matrix, Owner decisions and `SELF_CHECK`.
