# AlphaHive V3.1.1 Phase 1 — P0 Audit Report

**Generated**: 20260707_0628_utc
**Target Run**: 20260707_0349_utc
**Anomaly Records**: 7
**Baseline Records**: 56

## P0 FAIL

(none)

## P1 WARN

### baseline zero friction

- {'holding_period_hours': np.int64(4), 'zero_friction_count': 8, 'total': 14, 'reason': 'Some baselines have friction_bps_roundtrip=0 (may indicate missing turnover data)'}
- {'holding_period_hours': np.int64(24), 'zero_friction_count': 9, 'total': 14, 'reason': 'Some baselines have friction_bps_roundtrip=0 (may indicate missing turnover data)'}
- {'holding_period_hours': np.int64(72), 'zero_friction_count': 8, 'total': 14, 'reason': 'Some baselines have friction_bps_roundtrip=0 (may indicate missing turnover data)'}
- {'holding_period_hours': np.int64(168), 'zero_friction_count': 11, 'total': 14, 'reason': 'Some baselines have friction_bps_roundtrip=0 (may indicate missing turnover data)'}

## Additional Findings

### 05 Field Mapping Status

- Status: PASS
- Mapped columns: 18

### Run Mixing Analysis

- Runs in ledger: ['20260707_0346_utc', '20260707_0349_utc']
  - 20260707_0346_utc: 7 records
  - 20260707_0349_utc: 7 records
- Symbol overlaps:
  - 20260707_0346_utc vs 20260707_0349_utc: 7 symbols (1000BONKUSDT, ESPORTSUSDT, HUSDT, LABUSDT, SKYAIUSDT...)
- Risk: Both runs coexist; scripts filter by `target_run_id`. If a script accidentally omits the filter, old run data could be processed incorrectly.

### Baseline Friction = 0 Issue

- HP=4h: 8/14 baselines have friction_bps_roundtrip=0
- HP=24h: 9/14 baselines have friction_bps_roundtrip=0
- HP=72h: 8/14 baselines have friction_bps_roundtrip=0
- HP=168h: 11/14 baselines have friction_bps_roundtrip=0
- Cause: `get_baseline_turnover()` returns None when baseline symbol not in snapshot, leading to zero friction calculation.
- Impact: Baseline net returns overstated (no friction deducted).

## Items Awaiting DS Fix

1. **Old run 0346 data**: Still has corrupt funding_cost_component values (0.666). Do not delete; exclude from DoD statistics.
2. **Baseline zero friction**: Some baselines have friction_bps_roundtrip=0 when baseline symbol not in snapshot. Consider fallback turnover source.
3. **Funding unit documentation**: raw_1h/funding_ohlc stores percent format; friction_config says rate_unit=decimal. Recommend aligning data_contracts to match reality.

## Summary

| Check | Status |
|-------|--------|
| CHECK-1: funding_rate range | PASS |
| CHECK-2: funding_cost magnitude | PASS |
| CHECK-3: benchmark frozen | PASS |
| CHECK-4: baseline A/B coverage | PASS |
| CHECK-5: AutoSkipped DoD | PASS |
| CHECK-6: Tiny Live | PASS |
| CHECK-7: hardcoded defaults | PASS |
| CHECK-8: 05 field mapping | PASS |
| CHECK-9: run mixing | WARN |
