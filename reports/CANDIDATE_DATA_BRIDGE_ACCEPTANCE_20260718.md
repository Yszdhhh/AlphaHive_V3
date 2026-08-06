# Candidate data bridge architecture acceptance — 2026-07-18

**External deliverable:** `C:\Users\10639\Desktop\AlphaHive_V3_A_DATA_HEALTH_deliverables\agent_outputs\antigravity\CANDIDATE-DATA-BRIDGE-GEMINI-GOAL-ARCH-001-CORRECTION-001.md`  
**Acceptance:** `ACCEPTED_FOR_NON-ACTIVE_ADDITIVE_HARDENING / CORRECTION_REQUIRED_FOR_ACTIVATION`

## What is accepted

The architecture's safety boundary is sound: staged validation, immutable
provenance, fail-closed rejection and atomic publication are the right shape
for a future bridge. It does not authorize a source switch, a historical
splice, a scanner change, Paper eligibility, notifications or trading.

Codex verified the currently implemented additive boundary instead of creating
a parallel bridge implementation:

- `harness/lib/canonical_data.py` maps the two local source schemas while
  retaining source and unit provenance.
- `scripts/100_dual_source_coverage.py` reads both stores only and does not
  merge or overwrite them.
- `reports/DATA_CANONICAL_COVERAGE_20260718.md` records a full-file adapter
  pass for 124 CoinGlass and 73 Binance kline files, plus all observed
  derivative files.
- The adapter now rejects non-finite OHLCV values, contradictory OHLC bounds,
  and duplicate `(symbol, timestamp_ms)` rows. These are additive integrity
  guards only; they do not fill a gap or select a source.

## Verification

- Focused canonical and coverage regression: `12 passed`.
- Full AlphaHive regression after the change: `376 passed, 15 subtests passed`.
- `git diff --check` completed without a whitespace error.

## Activation correction required

The external report must not be used as the literal implementation contract.
The verified Binance kline schema contains `quote_volume`, not
`quote_asset_volume`; the current scanner snapshot uses `timestamp`, not
`timestamp_utc`. The exact production bridge output root, immutable manifest
format, and scanner input contract therefore still require a corrected,
evidence-backed implementation specification before any activation review.

## Current factual boundary

The Binance public store is fresh through 2026-07-17 in the coverage report,
while the configured CoinGlass scanner input ends 2026-07-07. This explains
the stale one-row candidate result; it does not itself authorize treating
Binance as the scanner truth.

## Owner-only activation choices

1. Source precedence for price and each derivative dimension when the stores
   disagree.
2. The allowed missing-data policy for the 59 live symbols, 73 Binance files,
   and 124 CoinGlass files.
3. The publication conditions for any canonical snapshot, including whether
   derivatives may be absent while OHLCV is current.

Until those choices are approved, the bridge remains non-active and the
existing CoinGlass scanner path remains unchanged.
