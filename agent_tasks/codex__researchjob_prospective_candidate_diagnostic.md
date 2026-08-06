# RESEARCHJOB-PROSPECTIVE-CANDIDATE-DIAGNOSTIC-001

**task_id:** `RESEARCHJOB-PROSPECTIVE-CANDIDATE-DIAGNOSTIC-001`  
**owner:** Codex  
**tier:** T1/T2 read-only candidate-pipeline diagnostic  
**exact output:** `G:\\Quant test\\AlphaHive_V3\\reports\\RESEARCHJOB_PROSPECTIVE_CANDIDATE_DIAGNOSTIC_20260717.md`

## Objective

Determine why the authoritative signal-review inventory currently contains only
the historical `1000BONKUSDT` quality-BLOCK candidate, and identify the
smallest contract-safe path to produce a separate `PROSPECTIVE_LIVE` candidate
that can be evaluated for quality ALLOW.

## Required checks

- Trace the current signal-review exporter inputs and candidate filtering;
- inspect all available candidate/package sources without refreshing or
  overwriting authoritative outputs;
- distinguish missing candidate data, quality-gate rejection, identity/history
  gaps and scheduler/runtime gaps;
- identify whether any existing symbol already has complete identity, history,
  derivatives and liquidity evidence;
- propose a Codex implementation/data-read step with exact allowlist and tests.

## Hard boundaries

Read-only. Do not alter `signal_review/latest.json`, scheduler state, credentials,
data source, quality thresholds, job store, PaperPlan, notification or trading
paths. Do not create a substitute candidate or upgrade BLOCK to ALLOW. If the
full candidate inventory is unavailable, report PARK with the missing input.
