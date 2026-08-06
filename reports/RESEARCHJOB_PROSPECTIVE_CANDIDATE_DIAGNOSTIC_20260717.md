# ResearchJob prospective candidate diagnostic (2026-07-17)

**task:** `RESEARCHJOB-PROSPECTIVE-CANDIDATE-DIAGNOSTIC-001`  
**owner:** Codex  
**tier:** T1/T2 read-only  
**verdict:** `PARK / NO_PROSPECTIVE_ALLOW_INPUT`

## Findings

1. The authoritative `signal_review/latest.json` contains one candidate only:
   `1000BONKUSDT`, with `quality_status=BLOCK`,
   `mode=HISTORICAL_REPLAY`, and `missing_contract_identity` as the blocker.
2. The latest available run directory,
   `harness/runs/20260713_overnight_verification`, has only one row in
   `candidates.csv`, also `1000BONKUSDT`. Earlier runs contain 7–19 rows, but
   they are historical/replay snapshots and are not a current prospective
   candidate source.
3. `harness/lib/signal_review_exporter.py` correctly exports every row it
   receives and delegates quality/paper decisions to
   `harness/lib/deep_research_package.py`; it does not itself create a
   prospective candidate or upgrade a BLOCK row.
4. The current pipeline therefore has no fresh prospective candidate package
   with complete identity, history, derivatives and liquidity evidence. Using
   an older replay row would violate the cutoff and prospective-live contract.

## Conclusion

The bottleneck is upstream candidate production/data readiness, not the
ResearchJob evidence state machine. The research-only BONK path is now complete
through `RESEARCH_ASSESSMENT_READY`, but it is a permanent negative fixture.
No OwnerDecision, PaperPlan or execution test should be attached to it.

## Smallest next Codex slice

Add or repair a read-only prospective candidate inventory/scan input that
produces a real `PROSPECTIVE_LIVE` package without changing quality thresholds,
credentials, data-source precedence or trading paths. Acceptance must show at
least one symbol with complete identity/history/derivatives/liquidity evidence
and quality `ALLOW`; otherwise retain `PARK` and report the missing gate.

This diagnostic did not refresh or overwrite signal-review outputs and did not
modify the job store.
