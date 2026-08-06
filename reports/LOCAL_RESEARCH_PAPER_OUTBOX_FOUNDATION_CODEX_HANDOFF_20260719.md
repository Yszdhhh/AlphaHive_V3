# Local research, Paper and notification foundation — Codex handoff

**Date:** 2026-07-19  
**Tier:** T1/T2 local-only infrastructure  
**Status:** independently audited local-only foundation

## Delivered boundary

This slice makes three local development boundaries executable without writing
to a production ResearchJob directory or calling an external service:

1. `harness/lib/candidate_research_job_bridge.py` generates a fail-closed
   **creation preview** for a fresh, registry-authorized prospective candidate.
   It returns only a request draft and always labels Paper capability `BLOCK`.
2. `harness/lib/local_paper_plan_ledger.py` persists an already-built synthetic
   `paper_plan_v1` into an explicitly supplied local root. It verifies the
   artifact hash, writes one immutable versioned plan through a staged/fsynced
   transaction, keeps an event hash chain, rejects a second active plan, and
   recovers a committed staging transaction.
3. `harness/lib/local_notification_outbox.py` accepts only `local:`
   destinations. It supports idempotent pending → sending → sent/dead state
   files, interrupted-send recovery and a `DRY_RUN_NO_NETWORK` processor.

The integration test composes all three boundaries with the pre-existing
deterministic PaperPlan engine and offline bar simulator. It uses only the
synthetic `paper_allow.json` fixture.

## Hard exclusions

- No `alpha_hive/results/research_jobs` write or ResearchJob API route.
- No actual PaperPlan for a real candidate; no scheduler or live bar runner.
- No Feishu, webhook, HTTP client, credential, bot, contact lookup or network.
- No trigger ignition, Paper eligibility change, direction, notification
  delivery or trading.
- The existing historical BONK fixture remains blocked.

## Verification

- Local boundary tests: `22 passed`.
- Full AlphaHive V3 regression: `406 passed, 19 subtests passed`.
- `py_compile` and `git diff --check` passed for the modified slice.
- `alpha_hive/results/signal_review/latest.json` was not changed:
  `82D1E5DD6646E970FFAF4778908709CACD55095965ABEEDB953522A639667E8D`.

## Selected hashes

| File | SHA-256 |
|---|---|
| `harness/lib/local_paper_plan_ledger.py` | `C890455C28132A5A3C1504411675E750492EFAC78540C8C3B5A42C6B874881E7` |
| `harness/lib/local_notification_outbox.py` | `63E73A27A2C646DC13E65ABFCD2AFBC2ED474B62E7464A864C320A8129F89A22` |
| `harness/lib/candidate_research_job_bridge.py` | `4221A1F155A4252A50A5AE583F3660114F739F685F48CE3DEF4F3766AD67CB29` |
| `harness/tests/test_local_paper_plan_ledger.py` | `10C924AED6B15763A98EC32841E3CDBE51E0F140AC0780EF22C07C7621351653` |
| `harness/tests/test_local_notification_outbox.py` | `07FDD637D65A4100FCC2B1CE113A0AEB9AD089FB6C7997693CA0832935D4C34F` |
| `harness/tests/test_candidate_research_job_bridge.py` | `099A88D83ABD591F76019604D5B9A86DB07EFBCBDAD1B13501782552E66BCCF0` |
| `harness/tests/test_local_research_to_paper_workflow.py` | `DAAE6B1429F422063EFA0EB590C800E983A9FCF14979DFB9F242D9F968D587AA` |

## Next stage and dispatch

DeepSeek `LOCAL-RESEARCH-PAPER-OUTBOX-FOUNDATION-FINAL-AUDIT-001` has passed
independent read-only audit. Its acceptance, including the non-blocking
external test-count correction, is recorded in
`reports/LOCAL_RESEARCH_PAPER_OUTBOX_FOUNDATION_FINAL_AUDIT_ACCEPTANCE_20260719.md`.

Waiting on a fresh, registry-authorized `PROSPECTIVE_LIVE` candidate and the
later prospective-lifecycle implementation slice:
`reports/PROSPECTIVE_LIFECYCLE_PREFLIGHT_CORRECTION_ACCEPTANCE_20260719.md`
records the accepted contract baseline. Production ResearchJob binding, actual
PaperPlan persistence, bar scheduling and any real Paper lifecycle remain
separate from this local-only slice.

Owner-only T3 gates remain: real Feishu app/credentials/recipients/delivery,
trigger ignition, Paper eligibility `ALLOW`, and any trade path.

## SELF_CHECK

- [x] Every writer takes a caller-supplied local root; no production root is a default.
- [x] Notification destinations reject every non-`local:` target.
- [x] Candidate previews cannot create a job and hard-block Paper capability.
- [x] Synthetic fixtures are clearly distinct from real candidates.
- [x] No external side effect is present in the changed modules.
