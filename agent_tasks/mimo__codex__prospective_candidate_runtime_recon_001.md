# PROSPECTIVE-CANDIDATE-RUNTIME-RECON-001

**Agent:** Mimo  
**Tier:** T1 read-only runtime reconciliation  
**Exact Desktop output:** `C:\Users\10639\Desktop\AlphaHive_V3_A_DATA_HEALTH_deliverables\agent_outputs\mimo\PROSPECTIVE-CANDIDATE-RUNTIME-RECON-001.md`

## Objective

Determine from existing local artifacts only whether a current fresh,
registry-authorized `PROSPECTIVE_LIVE` candidate is available for a future
ResearchJob create request. This is a readiness report, not a job creation.

## Required reading

Read the shared required-reading sequence, then this exact task file, plus:

- `harness\lib\prospective_candidate_inventory.py`
- `harness\lib\candidate_research_job_bridge.py`
- `harness\runs\` current manifests, candidate files and input snapshots
- all available run registry/quality artifacts
- `alpha_hive\results\signal_review\latest.json`
- `OWNER_DECISIONS_NEEDED.md` and `OWNER_APPROVALS.md`

## Required checks

1. Select the latest run by recorded `scan_time_utc`, not folder naming.
2. Verify run mode, no-lookahead attestation, registry status and judgement
   authorization, completed-bar age, candidate count, each candidate record
   identity and quality status.
3. Run the read-only inventory/preview logic against copied or in-memory data
   only; do not create a ResearchJob or alter a run artifact.
4. Report one verdict: `READY_FOR_CREATE_PREVIEW`, `PARK`, or `FAIL`; list
   every blocker and distinguish data freshness from Owner/T3 gates.
5. Hash authoritative files before/after the check and confirm no mutation.

## Hard boundaries

Read only; write only the exact Desktop report. No scanner/backfill/pull,
provider/network call, route invocation, job/evidence/OwnerDecision/PaperPlan
creation, notification, trigger, credential or trading action. Missing or
ambiguous evidence is PARK.
