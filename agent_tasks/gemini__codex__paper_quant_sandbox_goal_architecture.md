# PAPER-QUANT-SANDBOX-GEMINI-GOAL-ARCH-001

**task_id:** `PAPER-QUANT-SANDBOX-GEMINI-GOAL-ARCH-001`  
**agent:** Gemini external agent proxy, long-thread goal mode  
**tier:** T1/T2 read-only architecture for isolated dry-run core  
**repository write authority:** Codex only  
**exact Desktop output:** `C:\\Users\\10639\\Desktop\\AlphaHive_V3_A_DATA_HEALTH_deliverables\\agent_outputs\\antigravity\\PAPER-QUANT-SANDBOX-GEMINI-GOAL-ARCH-001.md`

## Objective

Design an implementation-ready, isolated sandbox for the missing visible core
features: structured research-job prompt export, deterministic PaperPlan
materialization for a future eligible job, and a pure paper/quant execution
simulator. This is not an authorization to create a real PaperPlan or order.

## Required reading

Read the shared materials in the order required by
`G:\\Quant test\\AlphaHive_V3\\PROJECT_REQUIRED_READING.md`, then this task,
`config/deep_research_contract.yaml`,
`config/research_orchestration_contract.yaml`,
`config/paper_execution_presets.yaml`,
`harness/lib/deep_research_package.py`,
`harness/lib/signal_review_exporter.py`, current ResearchJob server files and
the relevant tests.

## Required design coverage

1. Show the current structured-prompt path (`deep_research_package` and
   `render_research_prompt`) and define the smallest local runner/export
   interface that emits an immutable provider-neutral package without automatic
   provider calls.
2. Define a deterministic PaperPlan schema and binding to an eligible
   prospective job, OwnerDecision, approved preset version/hash and first
   complete-bar entry anchor. Historical/BLOCK jobs must fail closed.
3. Define a pure offline execution simulator: bar ingestion, order intents,
   deterministic fill/slippage/fee model, position/risk limits, stop/time exits,
   PnL, event ledger, replay/idempotency and crash recovery. It must have no
   exchange/API/order/credential dependency.
4. Define the interface boundary between PaperPlan, simulator and any future
   quant execution adapter. Real trading, trigger ignition, notification and
   live data-source changes remain PARK.
5. Provide synthetic ALLOW and permanent-BONK BLOCK fixtures, failure and
   concurrency matrix, exact Codex file allowlist, and a staged acceptance plan
   that visibly demonstrates these features without needing a real candidate.
6. Separate facts, recommendations and Owner decisions. Mark the confirmation
   text, Owner identity/authentication and immutable preset binding as
   `PARK / OWNER_DECISION_REQUIRED`.

## Hard boundaries

Do not modify repository/config/tests/results, create PaperPlan files, submit
OwnerDecision, call providers/exchanges, send notifications, ignite triggers or
place orders. Write only the exact Desktop report. The output is an architecture
package for later Codex implementation of an isolated dry-run slice.
