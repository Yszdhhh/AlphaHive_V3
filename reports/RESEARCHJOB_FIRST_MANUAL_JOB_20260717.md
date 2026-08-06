# First manual ResearchJob receipt — 2026-07-17

**authorization:** Owner approved creation of one research-only, non-trading job.  
**job ID:** `job_a6f36bc3-5fd5-405a-abcd-dc4104a7529e`  
**record ID:** `20260707_1341_utc_0001` (`1000BONKUSDT`)  
**creation result:** HTTP 201  
**current state:** `AWAITING_EVIDENCE`

## Scope boundary

The selected record is the only current candidate in `signal_review/latest.json`.
It is an historical replay candidate with quality status `BLOCK` because of
`missing_contract_identity`. The job was created solely to exercise the manual
research workflow. It has `research_capability: ALLOW`,
`owner_review_capability: ALLOW`, and `paper_plan_capability: BLOCK`.

No evidence was imported; no verification, assessment, Owner decision,
PaperPlan, notification, trigger or trading action was created.

## Integrity receipt

The subsequent GET returned HTTP 200 and the same `AWAITING_EVIDENCE` state.

| File | SHA-256 |
|---|---|
| `candidate_package.json` | `e1be947478dade0704ce7bde0c66602ab4bee3447c49cb813fc14222308e565f` |
| `job.json` | `dbaa770a0ed38431321ed9af221deae94d44881bcf42c48062fa3925d417d9d1` |
| `events.jsonl` | `a17750be98f119f265884289f532a08ab5e7d9d677c9f1058854e8dd5df9f13f` |
| `pointers.json` | `e82518fc3ec9377ac6c01f654b7cca59775f29f656802eef6e5ddd5a208ab98e` |

## Next permitted action

Only a manually supplied, cutoff-safe external evidence bundle may advance
this job to `EVIDENCE_IMPORTED`. Because the candidate is `BLOCK` and
historical-only, no later action may turn it into a PaperPlan or virtual trade.
