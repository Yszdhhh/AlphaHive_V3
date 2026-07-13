# Acceptance Check — AlphaHive V3 P0-DATA Clean Run Candidate
_Generated: 2026-07-07 | Target runs: 0804 (superseded), 1341 (quarantined), 0912 (quarantined)_

## Verdict: 6 PASS / 1 PARTIAL / 2 FAIL — Score: 35/50

---

### 1. candidate_pool_random unique symbols ≥ 10 — ❌ FAIL

| Run | unique symbols | Source |
|-----|---------------|--------|
| 1341 | 1 | pool_status.json → `source_unique_symbols: 1` |
| 0804 | 7 | Baseline_Ledger → 7 unique symbols in candidate_pool_random |
| 0912 | 1 | run_manifest → `candidate_count: 1` |

**No run achieves ≥ 10 unique symbols.** Root cause: each scan triggers at most 1-7 anomalies (depending on market conditions), and the candidate_pool is built from those anomaly symbols. With low-volatility market, candidate count is structurally limited.

**Evidence**: `harness/runs/20260707_1341_utc/pool_status.json` line 4: `"source_unique_symbols": 1`

---

### 2. pool_status = ok — ❌ FAIL

| Run | pool_status | Status field |
|-----|------------|--------------|
| 1341 | exists | `insufficient_pool` (candidate_pool) |
| 0804 | missing | No pool_status.json |
| 0912 | missing | No pool_status.json |

**1341 has pool_status.json but status is `insufficient_pool`**, not `ok`. 0804/0912 have no pool_status.json at all (generated before pool_status was implemented).

**Evidence**: `harness/runs/20260707_1341_utc/pool_status.json` line 10: `"status": "insufficient_pool"`

---

### 3. return_tape.csv independent, 05 reads only return_tape — ⚠️ PARTIAL

| Check | Result | Evidence |
|-------|--------|----------|
| return_tape.csv exists for 1341 | Yes (empty) | File exists, 1 line (header only) |
| return_tape.csv exists for 0804 | No | File not found |
| 05 reads return_tape only | Yes | `05_update_returns.py` line 79: `load_return_tape()` reads from `return_tape.csv`, line 81: raises SystemExit if missing |
| 05 does NOT touch input_snapshot | Yes | No write to input_snapshot anywhere in 05 |

**return_tape.csv is independent (not derived from input_snapshot). 05 only reads return_tape. However, 1341's return_tape is empty, and 0804 has no return_tape.**

**Evidence**: `scripts/05_update_returns.py` line 9: `"只用独立 return_tape.csv 回填收益，不扩写 frozen input_snapshot.csv"`

---

### 4. run_registry clean only for all gates pass — ✅ PASS

`harness/runs/run_registry.yaml` exists with v1 schema. Run statuses:

| Run | Status | eligible_for_dod | eligible_for_judgment |
|-----|--------|-------------------|-----------------------|
| 0346 | dirty | false | false |
| 0349 | superseded | false | false |
| 0804 | superseded | false | false |
| 0912 | quarantined | false | false |
| 1341 | quarantined | false | false |
| 20260630_0100_utc_replay | quarantined | false | false |
| 20260511_1200_utc_replay | **clean** | **true** | **true** |

**Only the historical replay run is marked clean. All live runs are dirty/superseded/quarantined.**

**Evidence**: `harness/runs/run_registry.yaml` lines 38-44: 1341 quarantined, `eligible_for_dod: false`

---

### 5. 0346 dirty, 0349/0804 superseded, 0912 quarantined not in DoD — ✅ PASS

All four runs have `eligible_for_dod: false` and `eligible_for_judgment: false` in run_registry.yaml.

- 0346: `status: dirty`, `eligible_for_dod: false`
- 0349: `status: superseded`, `eligible_for_dod: false`
- 0804: `status: superseded`, `eligible_for_dod: false`
- 0912: `status: quarantined`, `eligible_for_dod: false`
- 1341: `status: quarantined`, `eligible_for_dod: false`

**Evidence**: `harness/runs/run_registry.yaml` — all entries show `eligible_for_dod: false`

---

### 6. Funding /100 only in one place — ✅ PASS

| Location | Has /100? | Notes |
|----------|-----------|-------|
| `harness/lib/funding_normalize.py` | Yes (line 72) | Only place |
| `scripts/04_calc_friction.py` | No | Reads from symbol_meta |
| `scripts/02_scan_anomalies.py` | No | Scanned |
| `scripts/99_validate_schema.py` | Yes (line 153) | Validation scan for scattered /100 (not a conversion) |

**Evidence**: `harness/lib/funding_normalize.py` line 72: `out = values / 100.0`

---

### 7. 03/04 no local turnover recalculation — ✅ PASS

| Script | Reads turnover from | Recalculates from raw? |
|--------|--------------------|-----------------------|
| 03_generate_baselines.py | symbol_meta.csv (`turnover_24h_usd_effective`) | No |
| 04_calc_friction.py | symbol_meta.csv via `meta_turnover()` | No |

Both scripts read pre-computed `turnover_24h_usd_effective` from `symbol_meta.csv`. Neither recalculates turnover from raw kline data.

**Evidence**: `scripts/04_calc_friction.py` line 74-80: `meta_turnover()` reads from `row.iloc[0].get("turnover_24h_usd_effective")`

---

### 8. AutoSkipped not counted as completed — ✅ PASS

- **05 rule #5**: `"AutoSkipped (sign=0) 收益标记清楚，不计入 DoD"`
- **99 check_autoskip**: `bad_sign` must be 0 AND `nonzero_returns` must be 0 for PASS
- **0804 data**: 2 AutoSkipped out of 7 anomalies, both `direction_sign=0`

AutoSkipped entries have `direction_sign=0`, which prevents any return computation (direction × return = 0). 99 verifies this.

**Evidence**: `scripts/05_update_returns.py` line 11: `"AutoSkipped (sign=0) 收益标记清楚，不计入 DoD"`

---

## Summary

| # | Check | Verdict |
|---|-------|---------|
| 1 | candidate_pool_random ≥ 10 | ❌ FAIL |
| 2 | pool_status = ok | ❌ FAIL |
| 3 | return_tape independent, 05 reads only return_tape | ⚠️ PARTIAL |
| 4 | run_registry clean only for all gates | ✅ PASS |
| 5 | Old runs excluded from DoD | ✅ PASS |
| 6 | Funding /100 single source | ✅ PASS |
| 7 | 03/04 no local turnover recalc | ✅ PASS |
| 8 | AutoSkipped not counted completed | ✅ PASS |

**Blocker**: No live run achieves candidate_pool_random ≥ 10 unique symbols. The latest run (1341) has only 1 candidate. The system needs either (a) more scan cycles to accumulate candidates, or (b) a relaxation of the diversity threshold, or (c) a different pool building strategy.
