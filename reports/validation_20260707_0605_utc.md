# AlphaHive V3.1.1 Phase 1 — P0 Audit Report

**Auditor**: 99_validate_schema.py (P0 audit agent)
**Timestamp**: 2026-07-07T06:05 UTC
**Target run**: 20260707_0349_utc
**Scope**: Ledger integrity, script correctness, schema compliance

---

## P0 FAIL (5 distinct issues)

### FAIL-1: 05_update_returns.py → Baseline_Ledger column mismatch (CRITICAL)

**Root cause**: `05_update_returns.py` defines column mappings with period suffixes:

```python
EXIT_COLS = {4: "exit_price_ref_4h", 24: "exit_price_ref_24h", ...}
BTC_EXIT_COLS = {4: "btc_exit_price_4h", ...}
DIR_EXCESS_COLS = {4: "dir_excess_ret_4h", ...}
DIR_NET_COLS = {4: "dir_excess_ret_net_4h", ...}
```

But `Baseline_Ledger.csv` has **no period-suffixed columns**. Its schema defines:
- `exit_price_ref` (no suffix)
- `btc_entry_price` / `btc_exit_price` (no suffix)
- `dir_excess_ret` / `dir_excess_ret_net` (no suffix)

**Impact**: When 05 iterates `for col, val in update.items()` and checks `if col in baseline_original.columns`, every period-suffixed key is NOT in the DataFrame → silently skipped. Result: **all 56 baseline records have empty price/return columns** — entry_price_ref, exit_price_ref, btc_entry_price, btc_exit_price, dir_excess_ret, dir_excess_ret_net remain NaN.

The 20260707_0349_utc baseline ledger currently shows all these columns empty, confirming the failure.

**Severity**: P0 — baselines are structurally incomplete; cannot compute any baseline return for DoD comparison.

**Fix required (DS)**: Either (a) update `baseline_ledger_schema.yaml` to include period-suffixed columns and have 03 write them, OR (b) rewrite 05's baseline mapping to use the non-suffixed column names. Option (b) is cleaner since each baseline has one `holding_period_hours` and stores one return value.

---

### FAIL-2: 04_calc_friction.py hardcodes holding_hours=24 for anomalies

**Location**: `04_calc_friction.py:296`

```python
funding_cost = calc_funding_cost(
    funding_rate_8h=funding_rate_8h,
    holding_hours=24,  # ← HARDCODED
    direction_sign=direction_sign,
    config=config
)
```

The anomaly record may have different holding periods (4h, 72h, 168h), but the friction calculation always assumes 24h.

**Impact**: For a 4h holding period, funding cost is overestimated by 6×. For 168h (7d), it's underestimated by 7×. Currently all 0349 candidates have `is_top_candidate=true` (no manual decision yet), so this hasn't affected any completed DoD calculation, but it will cause incorrect net returns once decisions are made.

**Severity**: P0 — incorrect funding cost for any non-24h holding period.

**Fix required (DS)**: Add a `holding_period_hours` column to Anomaly_Ledger or derive it from the candidate's intended holding period. Use that value instead of hardcoded 24.

---

### FAIL-3: Old run 20260707_0346_utc has extreme funding_cost_component values

**Records affected** (all from run 0346, NOT 0349):

| record_id | symbol | funding_cost_component |
|---|---|---|
| 20260707_0346_utc_0003_baseline_A | ESPORTSUSDT | -0.665964 |
| 20260707_0346_utc_0003_baseline_B | LABUSDT | 0.665964 |
| 20260707_0346_utc_0002_baseline_A | UBUSDT | -0.114342 |
| 20260707_0346_utc_0002_baseline_B | LTCUSDT | -0.114342 |
| 20260707_0346_utc_0004_baseline_A | SPCXUSDT | -0.079905 |
| 20260707_0346_utc_0004_baseline_B | INTCUSDT | -0.079905 |

A funding_cost_component of 0.666 means 66.6% of notional — physically impossible for 8h funding. This confirms the old 0346 run used an earlier, buggy friction calculation (likely the `/100` unit error mentioned in historical notes).

**Severity**: P0 for the old run data. The current 0349 run shows reasonable values (max ~0.002), so the fix was applied. But old 0346 records remain in the ledger with corrupt values.

**Action**: Do NOT delete old records (per constraints). Flag them as `notes: "pre-fix corrupt funding_cost"` or similar. Ensure 06_weekly_review.py excludes 0346 from DoD statistics.

---

### FAIL-4: Baseline_Ledger entry_price_ref is required by schema but structurally unfillable

**Schema**: `baseline_ledger_schema.yaml` line 17:
```yaml
entry_price_ref: {type: float, required: true, min: 0}
```

**Current state**: All 56 baseline records for run 0349 have `entry_price_ref` = empty.

**Why**: 03_generate_baselines.py never writes entry_price_ref (by design — it's left for 05). But 05's mapping tries to write to period-suffixed column names that don't exist in Baseline_Ledger, so the fill never happens.

**Severity**: P0 — schema says required, but the pipeline has no working code path to populate it.

**Fix required (DS)**: Same as FAIL-1. Once 05's baseline mapping is corrected, entry_price_ref will be filled.

---

### FAIL-5: Baseline_Ledger btc_entry_price is required by schema but structurally unfillable

Same root cause as FAIL-4. The schema requires `btc_entry_price` (line 19), but 05 cannot fill it because the column mapping uses period-suffixed names.

**Severity**: P0.

---

## P1 WARN (3 issues)

### WARN-1: Old run 20260707_0346_utc mixed in ledger

Both Anomaly_Ledger and Baseline_Ledger contain records from two different runs:
- `20260707_0346_utc` (7 anomaly + 14 baseline records)
- `20260707_0349_utc` (7 anomaly + 56 baseline records)

**Risk**: 04/05 filter by `target_run` so processing is isolated. However, any future reporting script (06_weekly_review.py) or manual CSV inspection that doesn't filter by run_id will include stale 0346 data in aggregate statistics.

**Action**: Ensure all downstream scripts filter by run_id. Do not delete old records.

### WARN-2: Anomaly_Ledger direction column value "AutoSkipped" is non-standard

The schema allows `direction` in `[Long, Short, Neutral, "", AutoSkipped]`. The value "AutoSkipped" appears in the direction column for AutoSkipped records, which is technically allowed but semantically odd — AutoSkipped is a decision, not a direction. The `direction` column should arguably be "Neutral" with `decision=AutoSkipped`.

**Severity**: Low — not a data integrity issue, but inconsistent with the schema's stated semantics.

### WARN-3: 04_calc_friction.py applies preprocess_funding_rate to ledger values

The script divides funding_rate_8h by 100 when `abs(rate) > 0.001`. This is a runtime conversion that assumes the ledger stores percentages. If the data pipeline ever changes to store decimals directly, this would silently halve all funding rates. The conversion should be documented in the data contract and validated once, not applied on every run.

**Severity**: Low — currently correct, but fragile.

---

## Items Awaiting DS Fix

These are structural issues that require Data Science (DS) to redesign before the pipeline can produce complete baselines:

1. **Baseline_Ledger schema vs 05 column mapping** (FAIL-1/4/5): The fundamental mismatch between what 03 creates (non-suffixed columns) and what 05 writes (period-suffixed columns). Recommend DS choose one schema and align both scripts.

2. **04 hardcoded holding_hours=24** (FAIL-2): DS should add holding_period_hours to Anomaly_Ledger or derive it from the candidate's intended holding periods.

3. **Old 0346 run data flagging** (FAIL-3): DS should add a `data_quality_note` column or equivalent to flag pre-fix records without deleting them.

---

## Checks That PASSED

| Check | Status | Detail |
|---|---|---|
| 1. funding_rate_8h abs [1e-5, 1e-2] | PASS | All 0349 candidates after /100 preprocessing: max abs = 0.00222 (HUSDT) |
| 3. benchmark_frozen_in_snapshot | PASS | run_manifest.json shows `true` |
| 4. baseline A/B per candidate per holding_period | PASS | All 7 candidates × 4 periods × 2 types = 56 baselines present |
| 5. AutoSkipped not in DoD | PASS | AutoSkipped records have direction_sign=0 |
| 6. Tiny Live forbidden | PASS | No Tiny Live decisions found |
| 7. 05 no hardcoded cost/turnover defaults | PASS (for 05) | 05 loads friction from anomaly record; no magic numbers for costs |
| 9. No ccxt/API key/order code | PASS | No forbidden code patterns in 04 or 05 |

---

## Summary

| Severity | Count | Key Issue |
|---|---|---|
| P0 FAIL | 5 | 05→Baseline column mismatch (structural), 04 hardcoded holding_hours, old run corrupt values |
| P1 WARN | 3 | Run mixing, direction column semantics, funding preprocessing fragility |
| PASSED | 7 | funding rate range, benchmark frozen, baseline pairs, AutoSkipped exclusion, no Tiny Live, no API keys |

**Overall verdict**: FAIL. The pipeline cannot produce complete baseline returns due to the 05→Baseline_Ledger column mismatch. This must be fixed before any meaningful DoD comparison can be computed.
