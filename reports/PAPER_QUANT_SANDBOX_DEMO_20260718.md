# Paper quant sandbox local demo

**task_id:** `PAPER-QUANT-SANDBOX-DEMO-CODEX-001`  
**owner:** Codex  
**scope:** T1/T2 local-only demonstration  
**verdict:** `ACCEPTED / LOCAL_ONLY`

## What was executed

The synthetic `paper_allow.json` fixture was passed through the isolated
PaperPlan builder and then through the offline bar-by-bar simulator. No job
store, outbox, scheduler, exchange, provider, credential, or live-order path
was used.

| item | result |
|---|---|
| plan | `plan_e8ad6d3f6ab4b571b2476c362f59355d` |
| plan artifact hash | `d7cd33a75f726d032ef00cbb8a85a18725f6245a973169622388e43e8be20eea` |
| selected preset hash | `793a19f6540fb18868594d068564373766468475a17f5de6b1ec8580005ac219` |
| entry anchor / reference | `2026-07-01T00:00:00Z` / `100.00` |
| simulation | `sim_daf1533945b4006491f894554490cece` |
| fills | 1 entry + 2 take-profits |
| exit reason | `TARGETS_COMPLETE` |
| realized PnL | `1449.25` |
| initial / final equity | `100000.00` / `101449.25` |
| ledger replay | idempotent (`true`) |

## Acceptance evidence

- Focused sandbox tests: **14 passed** (including cross-binding, live/BLOCK
  rejection, tamper rejection, same-bar stop precedence, and ledger replay).
- Full repository regression: **372 passed, 15 subtests passed**.
- `no_live_order_path=true` is required by both plan construction and
  simulation; a tampered plan fails closed on its artifact hash.

This proves the local mechanics only. It is not an OwnerDecision, does not
make the BONK historical fixture eligible, and does not authorize Paper or
real trading.

