# HERMES-POSTFIX-VERIFY-001

**task_id:** `HERMES-POSTFIX-VERIFY-001`  
**agent:** Grok external agent proxy  
**tier:** T1 read-only runtime verification  
**repository write authority:** Codex only  
**exact Desktop output:** `C:\\Users\\10639\\Desktop\\AlphaHive_V3_A_DATA_HEALTH_deliverables\\agent_outputs\\grok\\HERMES-POSTFIX-VERIFY-001.md`

## Objective

Independently verify the Owner-reported Hermes repair using only current local
runtime artifacts. Determine whether the latest post-fix pull proves recovery
from the previously recorded six SSL transport failures. This task must not
trigger a pull, modify the scheduler, alter data, or access external systems.

## Required reading

Read the shared materials in the order required by
`G:\\Quant test\\AlphaHive_V3\\PROJECT_REQUIRED_READING.md`, then read this
task, `OWNER_APPROVALS.md`, `OWNER_DECISIONS_NEEDED.md`,
`reports/HERMES_POSTPRUNE_RUNTIME_20260716.md`,
`reports/HERMES_SCHEDULER_STALL_20260716.md`, current Hermes pull reports and
checkpoints, and scheduler state available locally.

## Required checks

- Find the latest post-fix pull receipt and establish its UTC time.
- Verify scheduler enabled state and future `next_run_at` without changing it.
- For the 59-symbol effective universe, report each engine's success/failure
  count and any stale dimensions; explicitly check klines, funding, OI and
  taker buy/sell.
- Determine whether prior SSL failures are absent, recurring or unverifiable.
- Hash only relevant read artifacts before/after and prove no mutation.
- Return exactly one verdict: `RECOVERED`, `PARTIAL`, `UNVERIFIED` or `PARK`.

## Hard boundaries and output

No repository/config/data/checkpoint/scheduler/database/outbox write; no pull
trigger; no provider/web/API call; no credentials, Owner/Paper/trigger/trading
action. Write only the exact Desktop report. Include header, paths/timestamps,
before/after hashes, engine matrix, verdict rationale, PASS/ADVISORY/PARK
matrix, any true Owner decision, and `SELF_CHECK`.
