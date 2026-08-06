# ResearchJob prospective candidate preflight (2026-07-17)

**owner:** Codex  
**tier:** T1 read-only runtime/candidate inventory  
**verdict:** `PARK / NO_PAPER_ELIGIBLE_CANDIDATE`

## Current evidence

The authoritative `alpha_hive/results/signal_review/latest.json` contains one
candidate only:

- symbol: `1000BONKUSDT`
- record: `20260707_1341_utc_0001`
- mode: `HISTORICAL_REPLAY`
- quality: `BLOCK`
- blocker: `missing_contract_identity`
- current job: `RESEARCH_ASSESSMENT_READY`
- `paper_plan_capability`: `BLOCK`

No other candidate in the current signal-review directory has a quality
`PASS`/`ALLOW` package suitable for a prospective job. The existing BONK
fixture is intentionally a permanent negative fixture and cannot be reused or
overridden for Paper.

## Meaning

The evidence-import, verification and assessment state-machine path is now
working end to end. The next blocker is upstream candidate production/data
quality, not another external evidence audit. Until a fresh `PROSPECTIVE_LIVE`
candidate satisfies identity, history, derivatives and liquidity gates, MVP003
OwnerDecision and PaperPlan cannot be exercised legitimately.

## Next stage

1. Produce or identify a separate prospective candidate with quality `ALLOW`
   through the normal scan/data-quality path; do not alter the BONK fixture.
2. Create a new research job for that candidate and run the same evidence →
   verification → assessment chain.
3. Only then resolve the three Owner T3 inputs and implement/use MVP003 and a
   PaperPlan.

No new Gemini/Grok validation task is useful at this point. Their next role
starts only after a new candidate exists or after an Owner supplies the three
MVP003 governance inputs.
