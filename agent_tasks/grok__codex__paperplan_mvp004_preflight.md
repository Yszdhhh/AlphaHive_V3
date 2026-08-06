# PAPERPLAN-MVP-004-PREFLIGHT-001

**task_id:** `PAPERPLAN-MVP-004-PREFLIGHT-001`  
**agent:** Grok external agent proxy  
**tier:** T1/T2 read-only architecture and prerequisite audit  
**repository write authority:** Codex only  
**exact Desktop output:** `C:\\Users\\10639\\Desktop\\AlphaHive_V3_A_DATA_HEALTH_deliverables\\agent_outputs\\grok\\PAPERPLAN-MVP-004-PREFLIGHT-001.md`

## Objective

Independently map the exact prerequisites and implementation boundary for a
future deterministic ResearchJob MVP 004 PaperPlan engine. This preflight must
not create a PaperPlan, assign a direction, change paper eligibility, activate
a trigger or perform virtual/live trading.

## Required reading

Read governance in the order required by
`G:\\Quant test\\AlphaHive_V3\\PROJECT_REQUIRED_READING.md`, then this task,
`config/research_orchestration_contract.yaml`,
`config/deep_research_contract.yaml`, `KNOWN_LIMITATIONS.md`,
`OWNER_APPROVALS.md`, `OWNER_DECISIONS_NEEDED.md`, accepted ResearchJob 001B
and 002 handoffs, current ResearchJob server files/tests, and any existing
paper-plan, virtual-results or risk-preset artifacts.

## Required coverage

- Map current implementation versus contract paths `owner_decisions/vNNNN.json`
  and `paper_plans/vNNNN.json`; prove what is absent or reusable.
- Define the only valid prerequisite chain:
  quality/paper eligibility -> immutable evidence -> verification -> assessment
  -> signed Owner decision -> deterministic paper plan -> first complete-bar
  entry anchor after approval.
- Treat the current `1000BONKUSDT` historical `BLOCK` ResearchJob as an
  explicit negative fixture: it must never become Paper-eligible.
- Specify immutable PaperPlan schema/bindings, risk-preset versioning,
  direction and entry/stop/target constraints, idempotency, tamper checks,
  rejection taxonomy, crash recovery and concurrent publication behavior.
- Separate the deterministic no-send PaperPlan engine from later simulation,
  notification and Feishu delivery.
- Provide a temporary-store test matrix, exact Codex allowlist, staged
  implementation sequence, and the smallest true Owner/T3 decision package.

## Hard boundaries and output

No repository/config/test/data/result/scheduler/database/outbox write; no
provider/web/API call; no PaperPlan, Owner decision, direction, trigger,
notification, credential or trading action. Write only the exact Desktop report
with header, file:line evidence, architecture/state table, PASS/ADVISORY/PARK
matrix, Codex worklist, test matrix, Owner decisions and `SELF_CHECK`.
