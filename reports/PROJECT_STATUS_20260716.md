# AlphaHive V3 — external review status pack

**Snapshot date:** 2026-07-16 (Asia/Shanghai)
**Repository:** `G:\Quant test\AlphaHive_V3`
**Branch:** `master`
**Working tree:** Codex ARC-NEXT closure changes present; not committed in this handoff
**Remote relation:** `master` is 6 commits ahead of `origin/master`; no remote push is included in this package.

## Executive status

| Area | Status | Evidence |
|---|---|---|
| M-B1 / M-B2 / M-B3 | Packaged | Existing milestone commits and independent M-B3 preview |
| M-A1 mapping | Packaged | Pure contract-safe Binance mappings; no source switch |
| M-C1 | Packaged | Non-overwriting package helper |
| M-C2 offline cockpit | Final audit previously reported passed; Desktop artifact gap | The prior accepted DeepSeek verdict was `PASS_FOR-M-C2_FINAL_AUDIT`, but the original Desktop final-audit Markdown is not present in the current Desktop scan. Source/tests/cockpit outputs remain available. |
| Binance runtime | Post-prune continuity verified / partial transient failures | Mimo `ARC-NEXT-RUNTIME-SCHEDULER-VERIFY-001`: new report after prune, scheduler scheduled, checkpoint 8×59; latest run has SSL failures (klines 3, funding 2, taker 1) and needs next-run recovery check |
| Additive canonical adapters | Final audit passed | DeepSeek `ARC-DATA-CANONICAL-FINAL-AUDIT-001`: `PASS_FOR-DATA-CANONICAL-ADAPTER` |
| ARC-NEXT N1/N2/N3/N4/N5 | Codex closure complete | Full-file coverage, read-only funding overlap, liquidity-limit wording, 73→59 checkpoint prune, and v3 contract paths are recorded in the current reports and task index |
| F2.1 historical-only derivative gate | Final audit accepted with runtime advisory | DeepSeek `ARC-NEXT-F21-FINAL-AUDIT-001` is GREEN for code/safety boundaries; runtime continuity is verified, with partial SSL freshness advisory |
| Historical Binance archive research | Parked | DeepSeek `ARC-DATA-HISTORY-FINAL-AUDIT-001`: `PARK` |
| M-A2 validated-history gate | Time-blocked | Full-universe historical coverage is not yet proven |

## Current data architecture

- `coinglass_db` remains the historical/reference store used by the current scanner paths.
- `binance_free_db` is the live public Binance store operated by Hermes hourly pull.
- `harness/lib/canonical_data.py` and `scripts/100_dual_source_coverage.py` are additive/read-only adapters and coverage tooling only; the latter now validates every discovered file, not a head sample.
- No physical `canonical_db` merge has been executed.
- `config/data_contracts.yaml` now documents the observed CoinGlass `_ohlc` directories as v3; no scanner source switch to Binance has been executed.
- No trigger, threshold, Paper eligibility, credential, or trading-path change has been executed.

## Runtime evidence

- Effective live universe: 59 symbols, including benchmark symbols for reference.
- Latest pre-prune accepted runtime snapshot: all Klines, funding, OI and taker dimensions were fresh for 59/59 symbols; all four engines exited successfully; current failure counters were zero; runtime hashes matched the manifest.
- Post-prune Hermes continuity is verified by `pull_report_20260716_090607.md`; the job is enabled/scheduled and `next_run_at` is in the future. The run has partial SSL failures, so this remains a freshness advisory until the next pull.
- The earlier degraded run contained SSL EOF/read-timeout errors and recovered on later scheduled runs. This is classified as transient transport degradation, not a deterministic code defect.
- Checkpoint was pruned from 73 to the 59-symbol effective universe after a verified backup; raw parquet files were retained and not deleted.
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
4. Confirm any future scanner source precedence/splice behavior; the current v3 path correction did not switch the scanner to Binance.
5. Keep F2.1 OI/funding trigger ignition, Paper linkage, credentials, and trading-path changes parked as T3 decisions.
6. Observe the next Hermes pull and resolve or explicitly accept the remaining SSL freshness advisory; scheduler continuity itself is now validated.

## Safe work that can continue without approval

- Independent external review of this package;
- Symbol-by-symbol S3 coverage matrix generation without downloading/backfilling;
- Hermes runtime monitoring and report reconciliation;
- Tests and read-only schema/coverage checks;
- Documentation and provenance cleanup.

## Package boundary

This package intentionally excludes raw databases, Parquet stores, credentials, `.env` material, Hermes state, and the `.git` directory. It contains source/config/tests, audit reports, task specifications, and runtime evidence needed for external review.

## Evidence caveat for external reviewers

The M-C2 final-audit verdict is retained as a previously accepted project status, but its original Desktop report was not found during the 2026-07-16 consolidation scan. Reviewers should treat the source diff, offline cockpit output, and current repository tests as primary evidence and mark the missing historical report as a provenance gap rather than infer its contents.

## 2026-07-16 runtime status correction

Mimo subsequently located `pull_report_20260716_090607.md`, generated at
`2026-07-16T09:06:07Z`, after the checkpoint prune at `2026-07-16T06:37:22Z`.
Hermes is enabled and scheduled with a future next run, and all eight
checkpoint partitions contain 59 keys. The run is nevertheless classified
`PARTIAL / TRANSIENT_TRANSPORT_FAILURE`: klines had 3 SSL failures, funding 2,
OI 0, and taker 1. Runtime continuity is therefore verified, while full
freshness awaits the next scheduled pull. Evidence is recorded in
`reports/HERMES_POSTPRUNE_RUNTIME_20260716.md`.

## 2026-07-16 ResearchJob and quantitative calibration update

Codex has started the infrastructure track without waiting for additional
market data. The ResearchJob 001A FIX-03 candidate is implemented in the
`alpha_hive/server` service and passes the full repository suite (`340 passed`);
it remains `CODEX_CANDIDATE_PENDING_EXTERNAL_AUDIT` until Mimo performs the
independent negative/recovery review. Agy has a separate prompt-framework
freeze audit task and may not write the repository.

Codex also generated `reports/Q_CALIBRATION_001_BASELINE_20260716.md` from four
clean historical replay artifacts (61 candidate rows). This is a
direction-neutral calibration and data-quality baseline only. It does not
create a Paper Plan, assign direction, activate OI/funding triggers or change
Paper eligibility.

## 2026-07-17 external handback update

Mimo's `RESEARCHJOB-MVP-001A-NEGATIVE-AUDIT-001` independently passed all 12
FIX-03 checks and reproduced the 17/224/340 test counts. ResearchJob 001A is
accepted for its create/get slice with a non-blocking advisory for best-effort
Windows directory fsync and notification-outbox tree-hash drift.

Agy's `F21-PROMPT-003-FRAMEWORK-FREEZE-001` passed the direction-neutrality,
cutoff, denylist, GRAVEYARD and dormant OI/funding checks. The prompt framework
is `FREEZE_READY_WITH_OWNER_DOC`; the contract remains draft until the explicit
Owner/Codex version/status decision is recorded.

## 2026-07-19 prospective lifecycle status

The local-only candidate-preview, synthetic PaperPlan ledger and local dry-run
Outbox foundation have passed independent audit. They remain intentionally
disconnected from production ResearchJobs, real PaperPlans and real delivery.

Gemini's prospective lifecycle correction is accepted as design evidence:
historical replay requires `performance_eligible: false`; a future
`prospective_live` path must require true, and a PaperPlan builder must require
`PAPER_APPROVED` after an immutable OwnerDecision rather than the preceding
`RESEARCH_ASSESSMENT_READY` state. Existing historical jobs have no migration
path and remain Paper-ineligible.

No production lifecycle work is currently active. The latest scan has five
research observations but is not a usable prospective source because its mode
is absent, it is not cleanly registered, and its completed bar is stale. A
fresh, registry-authorized `PROSPECTIVE_LIVE` input is the next technical
dependency; a separately bound per-job Owner approval would still be required
before any real PaperPlan. Feishu delivery, trigger ignition and all trading
paths remain parked.
