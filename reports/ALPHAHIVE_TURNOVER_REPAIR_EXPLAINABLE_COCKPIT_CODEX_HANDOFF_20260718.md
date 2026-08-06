# AlphaHive turnover repair and explainable cockpit — Codex handoff

Date: 2026-07-18  
Tier: T1/T2 bounded repair and read-only observability upgrade

## Scope

This slice repairs the scanner's published-canonical `turnover_usd` mapping,
adds a defensive calculated-turnover fallback, runs the existing immutable
price snapshot through a new offline scan, and upgrades the local cockpit into
an explanatory system-status view. It does not change any scan threshold,
data source, credentials, Paper state, trigger authority, notification path or
trading path.

## Root-cause acceptance

Grok's original read-only report is accepted as `GREEN`:

`C:\Users\10639\Desktop\AlphaHive_V3_A_DATA_HEALTH_deliverables\agent_outputs\grok\ALPHAHIVE-DATA-READINESS-ROOT-CAUSE-001.md`

Direct source review confirmed its finding: the scanner normalizer did not
retain published `turnover_usd`, then wrote an empty replacement column. The
turnover calculator selected that empty column and every symbol became
`NO_VALID_BARS` despite valid canonical inputs.

## Implemented repair

- `scripts/02_scan_anomalies.py`: `normalize_kline()` now retains an existing
  non-empty `turnover_usd`; legacy `quote_volume` and `volume_usd` are used
  only when it is absent or empty.
- `harness/lib/turnover.py`: per-row source precedence falls through to the
  next valid turnover source and ultimately `close * volume` if an otherwise
  selected field is blank/non-positive.
- `scripts/06_build_return_tape.py` and
  `scripts/07_historical_replay_sampler.py`: use the same canonical-first
  turnover mapping. This prevents a later return-tape build or historical
  replay from losing already-published `turnover_usd`.
- `tests/test_scan_anomalies.py`: covers canonical `turnover_usd`, legacy
  `quote_volume`, the empty-column fallback, and both downstream normalizers.

## Offline re-scan evidence

The scanner was run once against the already-published local v0001 snapshot:

`python scripts/02_scan_anomalies.py --run_id 20260718_canonical_turnover_fix`

It made no network request or configuration change. The new run records:

| Fact | Result |
|---|---:|
| scan universe | 57 |
| valid 24-hour turnover windows | 57 |
| liquidity-floor passes | 45 |
| below the unchanged USD 10m floor | 12 |
| `NO_VALID_BARS` | 0 |
| research-queue anomalies | 5 |
| derivative real-time use | `LIVE_DISABLED` |

The five anomalies are factual research observations only. They create no
direction, ResearchJob, OwnerDecision, PaperPlan, Paper execution, trigger,
notification or trade.

## Explainable cockpit upgrade

`GET /api/signals/cockpit` now supplies a presentation layer in addition to
traceable machine fields: a system conclusion, state path, factor cards,
plain-language per-symbol explanations, factor observations for each current
research-queue anomaly, and a bounded recent-run history. The browser page
uses those semantics to show the data/decision chain rather than raw internal
codes. It labels future research prerequisites explicitly as not being a
Paper approval.

The page remains compatible with an already-running older local server: it
derives a safe plain-language fallback from the old read-only payload. The full
candidate-factor explanation appears after the local server loads the updated
repository code.

## Verification

- Focused repair, cockpit and canonical tests: `89 passed, 4 subtests passed`.
- Full `AlphaHive_V3` regression: `396 passed, 19 subtests passed`.
- Python compilation and JavaScript syntax checks pass.
- A live local browser check against the updated service rendered the status
  path, four sequential funnel stages, five factor cards, five candidate
  explanation cards, Chinese threshold labels, and no exposed raw status
  codes. The history filter changed the universe from `57 / 57` to `29 / 57`.
- `alpha_hive/results/signal_review/latest.json` stayed unchanged:
  `82D1E5DD6646E970FFAF4778908709CACD55095965ABEEDB953522A639667E8D`.

## Selected hashes

| Item | SHA-256 |
|---|---|
| `scripts/02_scan_anomalies.py` | `2D6DDABD3581406A19507D7119A912CE15A59B4464359B1A82C92FA6A6AD66FF` |
| `scripts/06_build_return_tape.py` | `8AC4E4F837A189FC86A1F9027D866147230210931921E8B6482BBF514EA29FD2` |
| `scripts/07_historical_replay_sampler.py` | `D77F14D90974B8FE282D42852E4F18B177B65A6F95BCDD49090A869D62C03107` |
| `harness/lib/turnover.py` | `863F5AD2D03A97270A210EA76A63E2136739D004BB5DF98B59554696F145FE5D` |
| `tests/test_scan_anomalies.py` | `7146D4E802A47CE02CBB583B0E26C5B7C164B69226B059BA600869670484A9B8` |
| `server/signal_review_repository.py` | `8FFB57048EF32106DC9D5F44099D020C51E0C4E6CAF5EF653016EDF119755B3D` |
| `dashboard/cockpit.js` | `6BFDA06917E6F470054731C2ECD8AD1F004E0B7AFFDC987C45E7225F46908B45` |
| fixed run manifest | `01B57F003C8AD5472CAC979C11B2CFB3A39B5192C2641D21C9F466772808B20D` |
| fixed run symbol metadata | `2083548E58728454343D8BFA4F0755CCC7E0F29C5BA9C6887430ED5D9AD76C14` |
| fixed run candidate artifact | `79C79DD4AC3F14BDE1B1FD53AE360602F1441F744903B4C5D8F20192550B18DD` |

## Hard exclusions

No threshold change, source switch, historical backfill, derivative activation,
trigger ignition, Paper `ALLOW`, Paper execution, notification delivery,
credential use or real trading is included.

## SELF_CHECK

- [x] The repair preserves canonical fact data rather than changing a rule.
- [x] The offline run uses the existing immutable local v0001 snapshot only.
- [x] The cockpit explains current state without creating an authorization.
- [x] Legacy signal-review state was not regenerated.
- [x] Focused and full regressions pass.

## Next stage and dispatch

Ready now: `ALPHAHIVE-TURNOVER-REPAIR-EXPLAINABLE-COCKPIT-FINAL-AUDIT-001`,
T1/T2 independent read-only final audit. Its exact task file and Desktop
output path are given in the dedicated dispatch file below. No Owner/T3 gate
is needed for that audit. A separate local-service restart is required before
the existing port 8000 process can load the updated API module; this is an
operational refresh, not a policy or data decision.
