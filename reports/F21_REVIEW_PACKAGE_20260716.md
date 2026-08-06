# F2.1 OI/funding historical-only review package

Generated: 2026-07-16 (Codex integration)

## Scope

This package records the independent review of the F2.1 historical-only OI/funding
gate. It does not authorize derivative trigger ignition, Paper `ALLOW`, source
switching, credentials, data backfill, or trading-path changes.

## Accepted evidence

| Evidence | Formal path | Status | Codex finding |
|---|---|---|---|
| Agy architecture review | `C:\Users\10639\Desktop\AlphaHive_V3_A_DATA_HEALTH_deliverables\agent_outputs\antigravity\ARC-NEXT-F21-ARCH-REVIEW-001.md` | GREEN | Historical-only, coverage boundaries, v3 semantics, no-trigger and no-ALLOW boundaries pass. |
| Agy PC preview replacement | `C:\Users\10639\Desktop\AlphaHive_V3_A_DATA_HEALTH_deliverables\agent_outputs\antigravity\ARC-NEXT-F21-PC-PREVIEW-002.md` | GREEN | Independent PC review passes cutoff, LIVE_DISABLED, coverage, unit, compatibility and T3 boundary checks. |
| Mimo post-prune runtime (superseded by scheduler verification) | `C:\Users\10639\Desktop\AlphaHive_V3_A_DATA_HEALTH_deliverables\agent_outputs\mimo\ARC-NEXT-RUNTIME-POSTPRUNE-001.md` | Historical static evidence | Retained for provenance; the current runtime verdict is in `ARC-NEXT-RUNTIME-SCHEDULER-VERIFY-001`, which confirms continuity but records partial SSL failures. |
| Sonnet PC preview (supplementary only) | `C:\Users\10639\Desktop\AlphaHive_V3_A_DATA_HEALTH_deliverables\agent_outputs\sonnet\ARC-NEXT-F21-PC-PREVIEW-001.md` | GREEN / supplementary | Preserved under its declared `agent=Sonnet` provenance; Sonnet is removed from future dispatch and is not relabeled as Gemini. |
| DeepSeek final audit | `C:\Users\10639\Desktop\AlphaHive_V3_A_DATA_HEALTH_deliverables\agent_outputs\deepseek\ARC-NEXT-F21-FINAL-AUDIT-001.md` | GREEN | Independent final audit passes F2.1 boundaries, tests and no-trigger/no-ALLOW constraints; its runtime advisory is now superseded by the later Mimo scheduler verification. |

## Codex checks

- F2.1 commits reviewed: `406f78f`, `044d4c4`.
- `derivative_use_mode` keeps real-time use `LIVE_DISABLED` and rejects scan dates
  beyond `2026-05-31T23:59:59Z`.
- Coverage thresholds remain the configured `0.60` / `0.30` boundaries.
- Funding normalization, 8h deduplication, completed-bar cutoff and unit-neutral
  OI change semantics remain contract-backed.
- OI/funding values are not appended to the candidate trigger array.
- `paper_eligibility=ALLOW` remains parked and no source, credential, direction
  or trading path was changed.
- Repository regression: `python -m pytest -q` → **340 passed**.

## Open items

1. Post-prune Hermes runtime continuity is verified, but freshness is
   `PARTIAL / TRANSIENT_TRANSPORT_FAILURE` until the next scheduled pull.
2. Commit provenance is now independently verified by Codex in
   `reports/F21_COMMIT_PROVENANCE_20260716.md`.
3. Trigger ignition, Paper `ALLOW`, source switch, credentials, data gap-fill,
   order-book and trading-path changes remain `PARK / T3`.

Status: `F2.1_FINAL_AUDIT_ACCEPTED_WITH_RUNTIME_ADVISORY`

## 2026-07-16 runtime/quantile handback correction

The earlier Mimo runtime row is superseded for continuity by
`ARC-NEXT-RUNTIME-SCHEDULER-VERIFY-001`:

| Evidence | Formal path | Status | Codex finding |
|---|---|---|---|
| Mimo post-prune scheduler verification | `C:\Users\10639\Desktop\AlphaHive_V3_A_DATA_HEALTH_deliverables\agent_outputs\mimo\ARC-NEXT-RUNTIME-SCHEDULER-VERIFY-001.md` | `ACCEPTED_WITH_ADVISORY_CORRECTION` | A new pull report exists after the prune; scheduler continuity and 8×59 checkpoint shape are verified. Latest run has 3 klines, 2 funding and 1 taker SSL failures, so freshness remains partial pending the next run. |
| Agy quantile design review | `C:\Users\10639\Desktop\AlphaHive_V3_A_DATA_HEALTH_deliverables\agent_outputs\antigravity\ARC-NEXT-F21-QUANTILE-DESIGN-001.md` | `ACCEPTED / GREEN (READ-ONLY)` | Quantile thresholds are dormant and absent from trigger construction as designed. The report is design input only; no ignition or implementation approval is granted. |

The current package status is:

`F2.1_FINAL_AUDIT_ACCEPTED; RUNTIME_PARTIAL_ADVISORY; QUANTILE_PARKED`

## Related infrastructure handback

ResearchJob 001A FIX-03 is tracked separately from the F2.1 derivative gate.
Mimo's independent negative audit is accepted with advisory; it does not
authorize evidence import, PaperPlan generation or provider automation.

The prompt framework audit is also accepted with advisory as
`FREEZE_READY_WITH_OWNER_DOC`. Its contract version/status remains a separate
Owner/Codex documentation decision.
