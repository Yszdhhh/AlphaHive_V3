# ALPHAHIVE-COCKPIT-FINAL-AUDIT-001

**agent:** Grok  
**tier:** T1/T2 independent read-only final audit  
**exact Desktop output:** `C:\Users\10639\Desktop\AlphaHive_V3_A_DATA_HEALTH_deliverables\agent_outputs\grok\ALPHAHIVE-COCKPIT-FINAL-AUDIT-001.md`

## Objective

Independently audit Codex's local AlphaHive observability cockpit. Verify that
it truthfully renders the latest recorded canonical scan, explains the
screening funnel and blockers, provides only client-side exploration controls,
and makes no change to scanner inputs, thresholds, ResearchJob state, Paper,
trigger, notifications, credentials, network sources or trading.

## Required reading

1. `G:\Quant test\AGENTS.md`
2. `G:\Quant test\AlphaHive_V3\AGENTS.md`
3. `G:\Quant test\AlphaHive_V3\PROJECT_REQUIRED_READING.md` and every file it requires
4. `G:\Quant test\AlphaHive_V3\PROJECT_OPERATING_PLAYBOOK.md`
5. This task file

## Required inputs

- `reports\ALPHAHIVE_COCKPIT_CODEX_HANDOFF_20260718.md`
- `G:\Quant test\alpha_hive\server\app.py`
- `G:\Quant test\alpha_hive\server\signal_review_repository.py`
- `G:\Quant test\alpha_hive\server\signal_review_service.py`
- `G:\Quant test\alpha_hive\server\signal_review_routes.py`
- `G:\Quant test\alpha_hive\dashboard\cockpit.html`
- `G:\Quant test\alpha_hive\dashboard\cockpit.css`
- `G:\Quant test\alpha_hive\dashboard\cockpit.js`
- `tests\test_signal_review.py`
- latest recorded `harness\runs\*\run_manifest.json` and matching `candidates.csv`
- `config\scan_rules.yaml`
- `G:\Quant test\alpha_hive\results\signal_review\latest.json`
- repository diffs for both `G:\Quant test\alpha_hive` and `G:\Quant test\AlphaHive_V3`

## Required checks

1. The cockpit API chooses the latest recorded scan by its recorded timestamp,
   not folder-name accident, and reports the actual run ID, scan time,
   completed-bar cutoff, snapshot version, derivative mode and candidate count.
2. Funnel facts reconcile to the latest run's `symbol_meta` and `candidates.csv`:
   scan universe, Full history, valid metric window, liquidity-threshold pass,
   candidates and Paper-capable inputs. Confirm `Paper-capable inputs` is not
   presented as an approval.
3. Thresholds are loaded for display from `config/scan_rules.yaml`, marked
   read-only, and the browser has no threshold/scanner/Paper/trigger/notification/trading write action. Confirm the displayed gate includes the
   effective-turnover floor and minimum-valid-bars settings actually used by
   the scanner.
4. The explorer's history filter, Paper-input toggle, valid-window toggle and
   symbol search are client-side display filters only and give reconcilable
   counts. Perform at least one browser/UI or DOM interaction check.
5. The local What-if panel may recalculate only the recorded turnover gate in
   the browser. Verify its sliders and reset control do not call the backend or
   modify configuration, do not label its count as a candidate count, and when
   no valid turnover window is recorded explain that missing input cannot be
   manufactured by relaxing a slider.
6. `GET /api/signals/cockpit` is read-only and protected from malformed/missing
   recorded inputs by a clear error response rather than fabrication. No route
   other than GET is introduced for cockpit use.
7. Starting/importing the dashboard must not regenerate or replace
   `alpha_hive/results/signal_review/latest.json`; hash it before/after a
   controlled local TestClient check. Confirm no scan run, canonical snapshot,
   job state, PaperPlan, trigger, external request or credential change occurs.
8. Reproduce the focused suite and full `AlphaHive_V3` regression suite. Report
   commands and exact pass counts, and run whitespace/conflict checks on the
   touched files.

## Hard boundaries

- This is a read-only audit. Write only the exact Desktop report.
- Do not modify either repository, config, run artifacts, signal review files,
  job store, scheduler, credentials or browser state.
- Do not call network/API/provider endpoints; do not execute scanner/backfill,
  create a ResearchJob/OwnerDecision/PaperPlan, ignite a trigger, send a
  notification or trade.
- If an input is missing, inconsistent, stale without transparent display, or
  a side effect exists, return `PARK` or `FAIL`; do not infer a pass.

## Deliverable

Write only the exact Desktop output. Include the agent/model, task ID, UTC
timestamp, files and hashes inspected, a single verdict
(`PASS_FOR_ALPHAHIVE_COCKPIT`, `PARK`, or `FAIL`), evidence for every check,
test commands/counts, actual displayed scan facts, unresolved items,
`SELF_CHECK`, and an explicit boundary-mutation confirmation.
