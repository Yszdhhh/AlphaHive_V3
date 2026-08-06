# ALPHAHIVE-TURNOVER-REPAIR-EXPLAINABLE-COCKPIT-FINAL-AUDIT-001

**agent:** DeepSeek  
**tier:** T1/T2 independent read-only final audit  
**exact Desktop output:** `C:\Users\10639\Desktop\AlphaHive_V3_A_DATA_HEALTH_deliverables\agent_outputs\deepseek\ALPHAHIVE-TURNOVER-REPAIR-EXPLAINABLE-COCKPIT-FINAL-AUDIT-001.md`

## Objective

Independently audit the bounded scanner turnover repair, its offline v0001
re-scan, and the explanatory cockpit upgrade. Verify that canonical
`turnover_usd` is preserved correctly, the new run's data-ready facts are
reproducible, and the UI/API communicate research status without granting any
execution authority.

## Required reading

1. `G:\Quant test\AGENTS.md`
2. `G:\Quant test\AlphaHive_V3\AGENTS.md`
3. `G:\Quant test\AlphaHive_V3\PROJECT_REQUIRED_READING.md` and every required document
4. `G:\Quant test\AlphaHive_V3\PROJECT_OPERATING_PLAYBOOK.md`
5. This exact task file

## Required inputs

- `reports\ALPHAHIVE_TURNOVER_REPAIR_EXPLAINABLE_COCKPIT_CODEX_HANDOFF_20260718.md`
- Original Grok root-cause report at the exact Desktop path cited by that handoff
- `scripts\02_scan_anomalies.py`
- `scripts\06_build_return_tape.py`
- `scripts\07_historical_replay_sampler.py`
- `harness\lib\turnover.py`
- `tests\test_scan_anomalies.py`
- `tests\test_signal_review.py`
- `harness\canonical_price_snapshots\current.json` and v0001 manifest
- `harness\runs\20260718_canonical_turnover_fix\run_manifest.json`, `input_snapshot.csv`, `symbol_meta.csv`, `candidates.csv`
- `G:\Quant test\alpha_hive\server\signal_review_repository.py`
- `G:\Quant test\alpha_hive\dashboard\cockpit.html`, `cockpit.css`, `cockpit.js`
- `config\scan_rules.yaml`
- `G:\Quant test\alpha_hive\results\signal_review\latest.json`

## Required checks

1. Reproduce the root cause and its preventive closure: current canonical price
   schema carries `turnover_usd`; the repaired scanner, return-tape builder,
   and historical-replay normalizers retain it; the legacy `quote_volume` /
   `volume_usd` paths remain valid.
2. Verify the turnover fallback cannot convert an all-empty preferred source
   into a false `NO_VALID_BARS` result when valid `close * volume` exists.
3. Reconcile the fixed run artifacts: 57 rows, 57 valid turnover windows, 45
   liquidity passes, 12 true turnover-floor failures, zero `NO_VALID_BARS`,
   and five candidate rows. Confirm unchanged threshold values from config.
4. Verify candidate rows are described as research observations only: no
   direction, PaperPlan, Paper execution, trigger, notification or trade is
   created or authorized.
5. Inspect `GET /api/signals/cockpit`: it remains GET/read-only and adds only
   display semantics. Validate system state, path, factor cards, candidate
   explanations, plain-language per-symbol explanations and bounded run
   history reconcile to the fixed run.
6. Verify the cockpit does not visibly expose raw user-facing codes such as
   `NO_VALID_BARS`, `valid_bar_pass`, `threshold_pass` or `LIVE_DISABLED` in
   normal display, and that it clearly distinguishes research prerequisite from
   Paper approval.
7. Reproduce focused and full test commands, run whitespace/conflict checks,
   and hash `alpha_hive/results/signal_review/latest.json` before/after a
   controlled TestClient check.

## Hard boundaries

- Read-only: write only the exact Desktop report.
- Do not modify either repository, configuration, snapshots, run artifacts,
  signal-review state, scheduler, credentials or browser state.
- Do not run scanner/backfill, call a provider/network API, create a job or
  PaperPlan, enable a trigger, send a notification or trade.
- If any claimed fact cannot be reproduced, report `PARK` or `FAIL`; do not
  substitute a historical run or infer an authorization.

## Deliverable

Include agent/model, task ID, UTC timestamp, exact inspected paths and hashes,
a single verdict (`PASS_FOR_TURNOVER_REPAIR_AND_EXPLAINABLE_COCKPIT`, `PARK`,
or `FAIL`), evidence for every required check, command/count test evidence,
unresolved items, `SELF_CHECK`, and explicit boundary-mutation confirmation.
