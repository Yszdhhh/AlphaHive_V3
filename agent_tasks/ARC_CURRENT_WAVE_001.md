# ARC current wave 001

**Status:** active dispatch index, 2026-07-15 (Asia/Shanghai).  This index is not a task an agent may self-select.

## Verified progress

| Area | State | Evidence |
|---|---|---|
| M-B1 / M-B2 / M-B3 | PACKAGED | commits `07e10d3`, `9319ef1`, `e372d68`; M-B3 independent preview passed. |
| M-A1 | PACKAGED | commit `d1d127c`; pure contract-safe Binance mappings only. |
| M-C1 | PACKAGED | commit `7af79be`; non-overwriting package helper. |
| M-C2 | PENDING_INDEPENDENT_REVIEW | commit `8567cb4`; static local renderer and regression exist, but no independent review/package yet. |
| M-A2 | TIME_BLOCKED | 90-day validated-history requirement is not yet met. |
| Binance public data | ACTIVE | Hermes hourly pull is enabled; current runtime health must be measured from the latest evidence, not this row. |

## Parallel work

| Task | Assignee | Tier | Purpose | Output |
|---|---|---|---|---|
| `ARC-A-HEALTH-001` | Mimo | T1 read-only | Reconcile live Binance runtime health and coverage. | `agent_tasks/mimo__codex__arc_a_health.md` |
| `ARC-A-MAP-AUDIT-001` | antigravity | T1 read-only | Independently audit contract-safe Binance mapping boundaries. | `agent_tasks/antigravity__codex__arc_a_mapping_audit.md` |
| `ARC-C-PREVIEW-001` | DeepSeek V4 | T1 read-only | Independently pre-review M-C2 for offline/safe packaging. | `agent_tasks/deepseek__codex__arc_c_cockpit_preview.md` |

Codex will not start M-C2 packaging until the preview raw report is received and accepted.  No task in this wave may change a trigger, paper status, data source/credential, trading path, or the Hermes schedule.
