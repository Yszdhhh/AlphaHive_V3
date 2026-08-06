# Prospective candidate inventory — Codex implementation acceptance

**task_id:** `RESEARCHJOB-PROSPECTIVE-CANDIDATE-INVENTORY-CODEX-001`  
**owner:** Codex  
**tier:** T1/T2 read-only  
**verdict:** `PARK / NO_FRESH_PROSPECTIVE_SOURCE`

## Result in plain language

The system can now distinguish “a historical row exists” from “a fresh,
registered, prospective candidate is ready for a new ResearchJob.” The current
data does not satisfy the latter. The inventory therefore parks instead of
silently reusing BONK or an old replay.

## Observed state

| check | observation |
|---|---|
| newest run directory | `20260713_overnight_verification` |
| newest run candidates | 1 (`1000BONKUSDT`) |
| newest completed bar | `2026-07-07T03:00:00Z` |
| current scan freshness | stale by more than the 24-hour inventory window |
| registry authorization | missing for the newest run |
| older 7-row runs | superseded/quarantined; not prospective inputs |
| older 14/19-row runs | clean historical replays; not prospective inputs |
| inventory verdict | `PARK` |

Blockers emitted by the read-only inventory:

- `no_fresh_registry_authorized_prospective_run`
- `latest_candidate_count_below_target`
- `latest_completed_bar_stale`
- `latest_run_not_registry_clean`

## Code and tests

Added:

- `harness/lib/prospective_candidate_inventory.py`
- `scripts/08_prospective_candidate_inventory.py`
- `tests/test_prospective_candidate_inventory.py`

The inventory reads manifests, candidates, and the run registry only. It does
not write runs, ledgers, signal-review outputs, credentials, or network calls.
Focused inventory/sandbox tests passed, and the full regression is **372
passed, 15 subtests passed**.

## Next required runtime step

The next action is a real fresh data-to-scan run: ensure the refreshed klines
are present in the configured local input path, execute the normal scanner,
register the run as clean/eligible only after its integrity gates pass, and
then inspect the resulting candidates for a non-BONK prospective `ALLOW`
package. No threshold relaxation, source switch, OI/funding trigger ignition,
or Paper linkage is included in this change.

