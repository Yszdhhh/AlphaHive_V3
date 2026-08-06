# Prospective lifecycle preflight correction — Codex acceptance

**Date:** 2026-07-19  
**Source report:** `C:\Users\10639\Desktop\AlphaHive_V3_A_DATA_HEALTH_deliverables\agent_outputs\antigravity\PROSPECTIVE-LIFECYCLE-PREFLIGHT-CORRECTION-001.md`  
**Source agent:** antigravity / Gemini  
**Tier:** T1/T2 read-only architecture correction  
**Codex verdict:** `ACCEPTED / DESIGN GREEN`

## Accepted correction

The correction resolves the two previously blocking lifecycle-contract
mismatches:

1. `cutoff_policy` is the downstream eligibility authority. Historical replay
   assessments must retain `performance_eligible: false`; a future
   `prospective_live` assessment must require `performance_eligible: true`.
   Existing historical jobs have no migration path and remain permanently
   ineligible for a PaperPlan.
2. A production PaperPlan builder must require `PAPER_APPROVED`, not
   `RESEARCH_ASSESSMENT_READY`. The latter is the state before the immutable,
   bound OwnerDecision; the former is the only state after an accepted
   `APPROVE_PAPER` decision.

The specified immutable bindings (`job_id`, `record_id`, candidate, evidence,
verification, assessment, OwnerDecision and preset hashes), rejection cases,
minimal implementation allowlist and test matrix are accepted as the design
baseline for a later prospective-only implementation slice.

## Boundaries retained

This is not production implementation authority. It does not create a real
ResearchJob or PaperPlan, start a Paper executor or trigger, deliver a Feishu
message, use credentials, or trade. Those paths remain `PARK` pending their
separate Owner gates.

## Runtime dependency

The current latest scanner run is still not a usable prospective input: it has
no prospective mode, no clean registry authorization, and a stale completed
bar. No production lifecycle implementation is queued until a fresh,
registry-authorized `PROSPECTIVE_LIVE` candidate exists. The report's design
does not relax those data-readiness gates.

## Next stage and dispatch

**Waiting dependency:** a fresh, registry-authorized `PROSPECTIVE_LIVE`
candidate that passes the existing data-readiness checks. There is no external
agent task to dispatch while that dependency is absent.

**Then:** Codex may prepare a narrowly scoped prospective lifecycle
implementation task using this report's allowlist and test matrix. Before any
real PaperPlan creation, a fully bound prospective job and a separate exact
per-job Owner approval are still required.

## SELF_CHECK

- [x] Original external report is preserved at its required Desktop path.
- [x] Acceptance follows the existing implementation and contract text.
- [x] No code, runtime artifact, configuration, Owner approval, or external
      system was changed by this acceptance record.
