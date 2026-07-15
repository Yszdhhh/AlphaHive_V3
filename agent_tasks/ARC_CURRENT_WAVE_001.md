# ARC current wave 001

**Status:** active dispatch index, 2026-07-15 (Asia/Shanghai).  This index is not a task an agent may self-select.

## Verified progress

| Area | State | Evidence |
|---|---|---|
| M-B1 / M-B2 / M-B3 | PACKAGED | commits `07e10d3`, `9319ef1`, `e372d68`; M-B3 independent preview passed. |
| M-A1 | PACKAGED | commit `d1d127c`; pure contract-safe Binance mappings only. |
| M-C1 | PACKAGED | commit `7af79be`; non-overwriting package helper. |
| M-C2 | PACKAGED_FINAL_AUDIT_PASSED | package `C:\Users\10639\Desktop\AlphaHive_V3_C_M-C2_20260715_deliverables`; DeepSeek `ARC-C2-FINAL-AUDIT-001` passed. |
| M-A2 | TIME_BLOCKED | 90-day validated-history requirement is not yet met. |
| Binance public data | ACTIVE | Hermes hourly pull is enabled; current runtime health must be measured from the latest evidence, not this row. |

## Parallel work

| Task | Assignee | Tier | Purpose | Output |
|---|---|---|---|---|
| `ARC-A-HEALTH-001` | Mimo | T1 read-only | Reconcile live Binance runtime health and coverage. | `agent_tasks/mimo__codex__arc_a_health.md` |
| `ARC-A-MAP-AUDIT-001` | antigravity | T1 read-only | Independently audit contract-safe Binance mapping boundaries. | `agent_tasks/antigravity__codex__arc_a_mapping_audit.md` |
| `ARC-C2-FINAL-AUDIT-001` | DeepSeek V4 | T1 read-only | Independently audit the final M-C2 package after Codex packaging. | `agent_tasks/deepseek__codex__arc_c2_final_audit.md` |
| `ARC-A-HEALTH-003` | Mimo | T1 read-only | Reconcile the latest non-green Binance runtime and identify transport/checkpoint causes. | `agent_tasks/mimo__codex__arc_a_health_runtime_003.md` |
| `ARC-DATA-CANONICAL-RESEARCH-001` | antigravity / Gemini 3.1 Pro | T1 read-only | Independently review a safe additive CoinGlass/Binance canonical integration boundary. | `agent_tasks/antigravity__codex__arc_data_canonical_research.md` |
| `ARC-DATA-CANONICAL-FINAL-AUDIT-001` | DeepSeek V4 | T1 read-only | Final independent audit of the additive canonical adapters and runtime reliability hardening. | `agent_tasks/deepseek__codex__arc_data_canonical_final_audit.md` |

M-C2 packaging and final audit are complete. The next wave is limited to runtime health reconciliation and an additive dual-source integration design; no task may change a trigger, paper status, data source/credential, trading path, or the Hermes schedule without the applicable Owner approval.

## 2026-07-15 acceptance update

- Latest Hermes pull is `ok`: 59/59 effective symbols are fresh across klines, funding, OI and taker; all four engines reported zero failures in `pull_report_20260715_090640.md`.
- `ARC-DATA-CANONICAL-RESEARCH-001` is accepted for additive design only; physical canonical merge, contract source switch, splice policy and recent-source precedence remain `PARK / Owner decision`.
- `ARC-A-HEALTH-003` was reported by Mimo as complete, but its required Desktop Markdown artifact is not present at the exact output path. Treat as `SUMMARY_ONLY / FORMAL_ARTIFACT_MISSING` until corrected.
- Codex acceptance evidence is recorded in `reports/DATA_CANONICAL_RECON_ACCEPTANCE_20260715.md`.
