# Canonical price scanner activation — Codex handoff

**Status:** `CODEX_CANDIDATE_PENDING_INDEPENDENT_FINAL_AUDIT`  
**Owner authority:** `OWNER_APPROVALS.md` entries 9–11

## Activated scope

- Published immutable local canonical price snapshot `v0001` under
  `harness/canonical_price_snapshots/`.
- Atomically wrote the validated `current.json` pointer.
- Changed the active scanner's price input from direct CoinGlass kline files
  to the hash-checked canonical pointer.
- Enforced the Owner-confirmed gap policy and prevented a 24-hour return or
  volatility window from crossing a price gap.
- Limited the active universe to 56 non-disabled candidate symbols plus the
  BTC benchmark; the publication itself contains 59 effective symbols,
  including reference benchmarks.

## Exact runtime evidence

| Item | Value |
|---|---|
| Pointer version | `v0001` |
| Pointer manifest SHA-256 | `d8d727bd95e67fd9e4474231fff3b907d9641cb22e7f323dc95dbcf76520c83f` |
| Published symbols | 59 |
| Activation run | `20260718_canonical_activation` |
| Recheck run | `20260718_canonical_activation_recheck` |
| Canonical price inputs in each scan | 57 |
| Snapshot rows in each scan | 123,120 |
| Candidates | 0 |
| Latest completed price bar | `2026-07-18T02:00:00+00:00` |

Zero candidates is a valid no-trigger outcome. It is not a data-source failure
and creates no ResearchJob, PaperPlan, notification or trading action.

## Verification

- Focused canonical snapshot, bridge and scanner regression: `29 passed`.
- Full project regression: `385 passed, 15 subtests passed`.
- `git diff --check`: passed.

## Explicit exclusions

Raw Binance and CoinGlass stores are unchanged. Funding/OI remain sourced only
for existing inventory evidence and are live-disabled for prospective metrics.
No derivative-source switch, historical backfill, trigger ignition, Paper
eligibility, OwnerDecision for a job, notification, credential, network call,
or trading behavior was added.

## Next stage and dispatch

**Ready now:** independent DeepSeek final audit.

- Task: `CANONICAL-PRICE-SCANNER-ACTIVATION-FINAL-AUDIT-001`
- Task file:
  `agent_tasks/deepseek__codex__canonical_price_scanner_activation_final_audit_001.md`
- Exact Desktop output:
  `C:\Users\10639\Desktop\AlphaHive_V3_A_DATA_HEALTH_deliverables\agent_outputs\deepseek\CANONICAL-PRICE-SCANNER-ACTIVATION-FINAL-AUDIT-001.md`

After an accepted audit, the next productive runtime condition is a fresh
quality-ALLOW candidate. Paper, triggers, notification and trading remain
separate Owner gates.
