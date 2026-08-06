# FEISHU-NOTIFICATION-PREFLIGHT-001

**task_id:** `FEISHU-NOTIFICATION-PREFLIGHT-001`  
**agent:** Gemini external agent proxy  
**tier:** T1/T2 read-only design and preflight  
**repository write authority:** Codex only  
**exact Desktop output:** `C:\\Users\\10639\\Desktop\\AlphaHive_V3_A_DATA_HEALTH_deliverables\\agent_outputs\\antigravity\\FEISHU-NOTIFICATION-PREFLIGHT-001.md`

## Objective

Prepare an implementation-ready, no-send notification path from immutable
ResearchJob/PaperPlan events to a deterministic notification outbox and future
Feishu delivery. This is design/preflight only. It must not send messages,
access Feishu, request credentials, create a bot, resolve contacts or modify
the repository.

## Required reading

Read the shared materials in the order required by
`G:\\Quant test\\AlphaHive_V3\\PROJECT_REQUIRED_READING.md`, then this task,
`config/research_orchestration_contract.yaml`,
`config/deep_research_contract.yaml`, `OWNER_APPROVALS.md`,
`OWNER_DECISIONS_NEEDED.md`, current ResearchJob server files, existing outbox
or notification code if any, and the accepted 001B/002 handoffs.

## Required coverage

- Map the current notification/outbox implementation status and exact safe
  extension points.
- Define immutable event-to-outbox inputs, notification ID/idempotency key,
  payload hash, states, atomic claim/retry/dead-letter semantics and recovery.
- Define a provider-neutral Feishu adapter boundary that keeps credential and
  recipient resolution out of artifacts and logs.
- Separate no-send T1/T2 work from T3 actions: app/bot registration,
  credential storage, recipient approval, actual delivery and delivery enable.
- Define negative, concurrency and crash-recovery tests; strict allowlist; and
  the smallest Owner decision package needed for later enablement.

## Hard boundaries and output

No repository/config/test/data/outbox write; no Feishu/web/API call; no bot,
credential, recipient, notification, Owner/Paper/trigger/trading action. Write
only the exact Desktop report, including header, architecture/state table,
file:line evidence, PASS/ADVISORY/PARK matrix, Codex worklist, test matrix,
Owner decisions and `SELF_CHECK`.
