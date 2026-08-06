# Candidate-data bridge preconditions — 2026-07-18

**Status:** `PREPARATION_COMPLETE / GAP_POLICY_AWAITING_OWNER_CONFIRMATION`

## Confirmed Owner boundary

- Binance is the factual/current price source.
- CoinGlass is the historical price source.
- On an overlapping price bar, Binance wins; the conflict remains in the
  manifest.
- An OHLCV snapshot may be prepared without current funding/OI, but those
  dimensions must be explicit unavailable fields and cannot activate a
  derivative trigger, Paper eligibility, notification, or trading behavior.

## Read-only bridge preflight

Using the local 59-symbol effective universe and the non-active bridge:

| Check | Result |
|---|---:|
| Latest source is Binance | 59 / 59 |
| No price source available | 0 / 59 |
| Symbols with a gap inside their latest 90-day view | 24 / 59 |
| Missing 1h bars inside those 90-day views | 94 |
| Historical gap intervals across all merged views | 27 |
| Gaps inside the latest 48 completed hours | 0 observed |

The dominant recent-window interruption is a shared four-bar interval between
`1783850400000` and `1783868400000` milliseconds UTC. This is evidence of a
past collection interruption, not permission to interpolate or alter raw data.

## Recommended Owner gap policy

1. **No interpolation and no silent fill.** Every missing interval remains in
   the immutable manifest.
2. **Freshness guard:** any missing bar in the most recent 48 completed hours
   blocks that symbol from a prospective scan.
3. **Bounded historical warning:** outside the 48-hour guard but inside the
   90-day lookback, a snapshot may publish only if each gap is at most four
   bars and the symbol has at most six missing bars in total. Its status is
   `HISTORICAL_GAP_WARNING`.
4. **Metric isolation:** a rolling metric or candidate signal whose input
   window crosses any gap is unavailable for that symbol; it is never computed
   across a discontinuity.
5. **Hard block:** a larger gap, more than six missing bars in 90 days, or any
   unverified source conflict blocks prospective use until a new clean run.

This rule matches the observed four-hour historic interruption while preserving
a strict current-signal guard. It is not active until the Owner confirms it.

## Implemented, non-active assets

- `harness/lib/candidate_data_bridge.py`: deterministic completed-bar filter,
  Binance-over-CoinGlass selection, source provenance, conflict count, gap
  enumeration and rows hash.
- `tests/test_candidate_data_bridge.py`: synthetic regression for precedence,
  conflict evidence, gap preservation and fail-closed completed-bar handling.
- `reports/OWNER_DECISION_CONFIRMATION_TEMPLATE_20260718.md`: separate
  one-time governance confirmation and future per-job approval templates.

No source path, raw database, scanner, threshold, trigger, Paper state,
notification, credential, or trading path was changed.
