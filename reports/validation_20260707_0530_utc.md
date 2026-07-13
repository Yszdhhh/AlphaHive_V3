# AlphaHive V3.1.1 Phase 1 — P0 Audit Report

**Generated**: 20260707_0530_utc
**Target Run**: 20260707_0349_utc
**Anomaly Records**: 7
**Baseline Records**: 56 (7 candidates × 4 holding periods × 2 baseline types)

---

## P0 FAIL

### CHECK-1: funding_rate_8h range [1e-5, 1e-2]

**PASS** — After applying percentage→decimal preprocessing (same heuristic as 04_calc_friction.py: `if abs(rate) > 0.001: rate /= 100`), all funding rates fall within [1e-5, 1e-2]:

| record_id | symbol | raw | decimal | abs(decimal) |
|-----------|--------|-----|---------|--------------|
| ...0003 | HUSDT | -0.221988 | -0.002220 | 0.002220 |
| ...0002 | ESPORTSUSDT | 0.038114 | 0.000381 | 0.000381 |
| ...0007 | UBUSDT | 0.005 | 0.000050 | 0.000050 |
| ...0006 | SPCXUSDT | 0.008106 | 0.000081 | 0.000081 |
| ...0005 | SKYAIUSDT | 0.005 | 0.000050 | 0.000050 |
| ...0004 | LABUSDT | -0.026635 | -0.000266 | 0.000266 |
| ...0001 | 1000BONKUSDT | 0.002102 | 0.000021 | 0.000021 |

**CAUTION**: The preprocessing heuristic (`abs(rate) > 0.001 → /100`) assumes all raw values are percentages. If any value is already in decimal format and happens to be > 0.001, it would be incorrectly divided. Current data appears consistent with percentage format, but this is a fragile assumption.

### CHECK-2: funding_cost_component magnitude

**PASS** — All funding_cost_component values are small decimals (max ~0.047 for 168h holding). No values near 10%+ magnitude.

Sample values from anomaly ledger:
- 0349_0003: funding_cost_component = 0.0 (AutoSkipped, direction_sign=0)
- Baselines: range from ~0.00001 to ~0.047 (reasonable for 4h–168h holding)

### CHECK-3: benchmark_frozen_in_snapshot

**PASS** — run_manifest.json confirms:
```json
"benchmark_frozen_in_snapshot": true,
"benchmark_symbol": "BTCUSDT"
```

### CHECK-4: baseline A/B coverage per holding period

**PASS** — All 7 candidates have exactly 2 baselines (candidate_pool_random + full_pool_random) for each of the 4 holding periods (4h, 24h, 72h, 168h). Total: 7 × 4 × 2 = 56 baseline records. No gaps.

### CHECK-5: AutoSkipped not counted in DoD

**PASS (structural)** — All 7 anomaly records for run 0349 have `decision=AutoSkipped` and `direction_sign=0`. The `dir_excess_ret_*` columns are all empty (05_update_returns.py has not been run yet), so no AutoSkipped record currently has non-zero returns. When 05 runs, the `calc_dir_excess()` function returns 0.0 when `direction_sign == 0`, which is correct.

**NOTE**: Since ALL 7 records in this run are AutoSkipped, completed_4h/completed_24h DoD would be 0 — no human directional decisions exist yet.

### CHECK-6: Tiny Live = 0

**PASS** — No records have `decision=Tiny Live`. All decisions are `AutoSkipped`.

### CHECK-7: Hardcoded defaults in 04/05

**P1 WARN** — Found in 04_calc_friction.py:
- **Line 298**: `holding_hours=24` hardcoded when calling `calc_funding_cost()` for anomaly records. This means ALL anomaly funding costs are computed assuming 24h holding, regardless of actual holding period.
  - Impact: For 4h holdings, funding cost is overstated (~6×). For 72h/168h holdings, funding cost is understated (~3×/7×).
  - Baselines correctly use `holding_period_hours` from the ledger.

05_update_returns.py: No hardcoded defaults found. All values read from CSV/ledger.

### CHECK-8: 05 field mapping completeness

**PASS** — All 18 required field mappings are present in 05_update_returns.py:
- entry_price_ref → ENTRY_COL
- exit_price_ref_4h/24h/72h/7d → EXIT_COLS[4/24/72/168]
- btc_entry_price → BTC_ENTRY_COL
- btc_exit_price_4h/24h/72h/7d → BTC_EXIT_COLS[4/24/72/168]
- dir_excess_ret_4h/24h/72h/7d → DIR_EXCESS_COLS[4/24/72/168]
- dir_excess_ret_net_4h/24h/72h/7d → DIR_NET_COLS[4/24/72/168]

Script logic is correct: entry = first complete K-line open after scan_time, exit = close at N hours, BTC prices at same timestamps.

### CHECK-9: Run mixing in ledger

**P1 WARN** — Both runs coexist in the same CSV files:
- Anomaly_Ledger.csv: 20260707_0346 (7 records) + 20260707_0349 (7 records) = 14 total
- Baseline_Ledger.csv: 20260707_0346 (14 records) + 20260707_0349 (56 records) = 70 total

Scripts 04 and 05 correctly filter by `target_run_id = "20260707_0349_utc"`, so old run data is not processed. However:
- Risk: If a future script change accidentally drops the run_id filter, old run data could be processed incorrectly.
- The 0346 run records have different friction values (51.0 bps) and all have empty price/return fields.

---

## P1 WARN

### Baseline zero friction

For several holding periods, a significant fraction of baselines have `friction_bps_roundtrip = 0`:
- 4h: 4/14 baselines have friction=0
- 24h: 4/14 baselines have friction=0
- 72h: 6/14 baselines have friction=0
- 168h: 6/14 baselines have friction=0

**Root cause**: `get_baseline_turnover()` in 04_calc_friction.py returns None when the baseline symbol is not found in `input_snapshot.csv`, causing `turnover_usd=0` and `roundtrip_bps=0`. This means baseline net returns will be overstated (no friction deducted).

### 05_update_returns.py not yet executed

All price_ref and return columns are empty for run 0349:
- entry_price_ref: empty for all 7 anomaly + 56 baseline records
- exit_price_ref_*: empty
- btc_entry_price/btc_exit_price_*: empty
- dir_excess_ret_*: empty
- dir_excess_ret_net_*: empty

The script needs to be run to populate these fields.

---

## Items Awaiting DS Fix

1. **Run 05_update_returns.py**: Populate all price_ref and return columns for run 0349.
2. **Fix 04 hardcoded holding_hours=24**: Anomaly funding cost should use actual holding period from the ledger or config, not fixed 24h.
3. **Fix baseline zero friction**: `get_baseline_turnover()` needs a fallback when baseline symbol isn't in snapshot (e.g., use the parent candidate's turnover, or a universe-wide median).
4. **Consider archiving old run 0346**: Clean separation between runs reduces risk of accidental cross-run processing.
5. **Validate funding unit assumption**: Confirm that raw_1h/funding_ohlc data is truly in percentage format (not decimal). The preprocessing heuristic is fragile.

---

## Summary

| Check | Status | Details |
|-------|--------|---------|
| CHECK-1: funding_rate range | PASS | All rates in [1e-5, 1e-2] after /100 preprocessing |
| CHECK-2: funding_cost magnitude | PASS | Max ~0.047, no extreme values |
| CHECK-3: benchmark frozen | PASS | benchmark_frozen_in_snapshot=true |
| CHECK-4: baseline A/B coverage | PASS | 56 baselines = 7 candidates × 4 HP × 2 types |
| CHECK-5: AutoSkipped DoD | PASS | All sign=0, no returns populated yet |
| CHECK-6: Tiny Live | PASS | Zero Tiny Live records |
| CHECK-7: hardcoded defaults | WARN | 04 uses holding_hours=24 for anomalies |
| CHECK-8: 05 field mapping | PASS | All 18 columns mapped correctly |
| CHECK-9: run mixing | WARN | 0346 + 0349 coexist; scripts filter correctly |

**Overall**: No P0 FAIL. Two P1 WARN items require attention before production use.
