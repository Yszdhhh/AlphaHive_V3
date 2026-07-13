# AlphaHive V3.1.1 Phase 1 — P0 Audit Report

**Generated**: 20260707_0729_utc
**Target Run**: 20260707_0349_utc
**Anomaly Records**: 7
**Baseline Records**: 56

## P0 FAIL

(none)

## P1 WARN

(none)

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

## Items Awaiting DS Fix

1. **Old run 0346 data**: Still has corrupt funding_cost_component values (0.666). Do not delete; exclude from DoD statistics.
2. **Funding unit P1 架构债**: raw_1h/funding_ohlc stores percent format; friction_config says rate_unit=decimal. preprocess_funding_rate() does runtime /100 conversion — fragile. Recommend aligning data_contracts to match reality.

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
| CHECK-10: baseline friction | PASS |
