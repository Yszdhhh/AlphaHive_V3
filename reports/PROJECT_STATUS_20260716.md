# AlphaHive V3 — external review status pack

**Snapshot date:** 2026-07-16 (Asia/Shanghai)
**Repository:** `G:\Quant test\AlphaHive_V3`
**Branch:** `master`
**Working tree:** clean
**Remote relation:** `master` is 6 commits ahead of `origin/master`; no remote push is included in this package.

## Executive status

| Area | Status | Evidence |
|---|---|---|
| M-B1 / M-B2 / M-B3 | Packaged | Existing milestone commits and independent M-B3 preview |
| M-A1 mapping | Packaged | Pure contract-safe Binance mappings; no source switch |
| M-C1 | Packaged | Non-overwriting package helper |
| M-C2 offline cockpit | Final audit passed | DeepSeek `ARC-C2-FINAL-AUDIT-001`: `PASS_FOR-M-C2_FINAL_AUDIT` |
| Binance runtime | Healthy | Mimo `ARC-A-HEALTH-003`: 59/59 effective symbols fresh on all four dimensions, current fail counters zero |
| Additive canonical adapters | Final audit passed | DeepSeek `ARC-DATA-CANONICAL-FINAL-AUDIT-001`: `PASS_FOR-DATA-CANONICAL-ADAPTER` |
| Historical Binance archive research | Parked | DeepSeek `ARC-DATA-HISTORY-FINAL-AUDIT-001`: `PARK` |
| M-A2 validated-history gate | Time-blocked | Full-universe historical coverage is not yet proven |

## Current data architecture

- `coinglass_db` remains the historical/reference store used by the current scanner paths.
- `binance_free_db` is the live public Binance store operated by Hermes hourly pull.
- `harness/lib/canonical_data.py` and `scripts/100_dual_source_coverage.py` are additive/read-only adapters and coverage tooling only.
- No physical `canonical_db` merge has been executed.
- No `config/data_contracts.yaml` source-path switch has been executed.
- No trigger, threshold, Paper eligibility, credential, or trading-path change has been executed.

## Runtime evidence

- Effective live universe: 59 symbols, including benchmark symbols for reference.
- Latest accepted runtime snapshot: all Klines, funding, OI and taker dimensions were fresh for 59/59 symbols; all four engines exited successfully; current failure counters were zero; runtime hashes matched the manifest.
- The earlier degraded run contained SSL EOF/read-timeout errors and recovered on later scheduled runs. This is classified as transient transport degradation, not a deterministic code defect.
- Checkpoint retains historical entries beyond the active universe. This is cosmetic and not a functional blocker.
- The monthly health job expression `0 0 1 * *` means the first day of each month and is valid; it has not run yet. The prior claim that it used day 0 was a report wording error.

## Historical-data audit result

DeepSeek independently verified object-level evidence for:

- BTCUSDT metrics beginning 2020-09-01;
- BTCUSDT 1h Klines beginning around 2020-01;
- CRC64NVME checksum metadata.

It also verified that ETHUSDT, DOGEUSDT and SOLUSDT metrics begin at 2021-12-01 in the audited samples. The remaining effective-universe symbols have not been individually enumerated. Therefore `2020-09-01` cannot be used as a global full-universe cutoff.

## Active blockers / Owner decisions

1. Choose historical cutoff policy: symbol/dimension-specific dates, or a conservative global date.
2. Authorize a read-only/object-list verification of every effective symbol before any backfill.
3. Authorize creation of an isolated canonical database and a mechanical S3 backfill, if desired.
4. Authorize any `data_contracts.yaml` path switch and confirm recent-source precedence/splice behavior.
5. Keep F2.1 OI/funding trigger ignition, Paper linkage, credentials, and trading-path changes parked as T3 decisions.

## Safe work that can continue without approval

- Independent external review of this package;
- Symbol-by-symbol S3 coverage matrix generation without downloading/backfilling;
- Hermes runtime monitoring and report reconciliation;
- Tests and read-only schema/coverage checks;
- Documentation and provenance cleanup.

## Package boundary

This package intentionally excludes raw databases, Parquet stores, credentials, `.env` material, Hermes state, and the `.git` directory. It contains source/config/tests, audit reports, task specifications, and runtime evidence needed for external review.
