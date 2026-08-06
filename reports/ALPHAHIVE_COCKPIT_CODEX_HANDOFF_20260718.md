# AlphaHive Cockpit — Codex Handoff (2026-07-18)

## Scope

T1/T2 local observability upgrade only. It adds a read-only cockpit for the
latest recorded canonical scan; it does not activate Paper, triggers,
notifications, external delivery or trading.

## Delivered surface

- Local URL: `http://127.0.0.1:8000/app/cockpit.html`
- Read-only API: `GET /api/signals/cockpit`
- Display: scan freshness, canonical snapshot, derivative mode, screening
  funnel, configured factor thresholds, blocker breakdown, and client-side
  symbol filters. The local What-if panel can re-evaluate only the recorded
  effective-turnover gate with browser-local sliders; it never writes config,
  reruns a scan or labels the result as a candidate count.

## Source of truth and current displayed facts

The API reads the latest recorded run by `scan_time_utc` from the manifest,
then reads that run's `symbol_meta` and `candidates.csv`. It displays the
scanner configuration from `config/scan_rules.yaml` without mutation.

At handoff, the newest recorded run is
`20260718_canonical_activation_recheck`: 57 scanned symbols, 29 with Full
history, 0 valid metric windows, 0 liquidity-threshold passes and 0 candidates.
The immediate blocker is `NO_VALID_BARS` for all 57 rows. Derivative use remains
`LIVE_DISABLED`; 29 `eligible_for_paper=Yes` rows are labelled as input
eligibility, not a Paper approval.

The current effective-turnover data availability is `0 / 57`. Accordingly the
What-if panel reports that changing its $10,000,000 / 18-bar defaults cannot
manufacture an input window or candidate; it will calculate its limited local
gate only after a future recorded scan contains measured turnover.

## Files changed by this slice

- `G:\Quant test\alpha_hive\server\app.py`
- `G:\Quant test\alpha_hive\server\signal_review_repository.py`
- `G:\Quant test\alpha_hive\server\signal_review_service.py`
- `G:\Quant test\alpha_hive\server\signal_review_routes.py`
- `G:\Quant test\alpha_hive\dashboard\cockpit.html`
- `G:\Quant test\alpha_hive\dashboard\cockpit.css`
- `G:\Quant test\alpha_hive\dashboard\cockpit.js`
- `G:\Quant test\AlphaHive_V3\tests\test_signal_review.py`

`app.py` no longer attaches the legacy startup exporter as FastAPI lifespan;
starting the web service therefore does not rewrite the authoritative signal
review snapshot.

## Verification

- Focused tests (`python -m pytest -q tests/test_signal_review.py`): `63 passed`.
- Full suite: `391 passed, 15 subtests passed`.
- Python compilation passed for all four changed server modules.
- Browser verification loaded the cockpit at its local URL and showed the above
  facts. Changing the history filter to `Full` changed the displayed count from
  `57 / 57` to `29 / 57` without any backend write.
- The What-if sliders update their displayed $10,000,000 / 18-bar values in the
  browser. At $0 / 0 they still truthfully report `0 / 57` usable windows,
  without any API write.
- A FastAPI TestClient GET check left
  `alpha_hive/results/signal_review/latest.json` unchanged:
  `82D1E5DD6646E970FFAF4778908709CACD55095965ABEEDB953522A639667E8D`.

## Non-goals / parked authority

- Threshold editing and scanner reruns remain outside this UI and require their
  own approved change process.
- The cockpit does not authorize or create ResearchJob decisions, PaperPlans,
  Paper execution, trigger ignition, notification delivery or trading.

## SELF_CHECK

- [x] Current state comes from recorded local run artifacts, not fake data.
- [x] UI interaction is read-only and client-side.
- [x] Startup does not regenerate the signal-review snapshot.
- [x] No T3 capability was added.
- [x] Focused and full regression suites pass.
