# Agent Synchronization Status

Date: 2026-07-12 (superseded by 2026-07-13 acceptance update)  
Status: RESEARCHJOB_MVP_001A_FIX02_REJECTED

> Current authoritative status is recorded in
> `RESEARCHJOB_001A_FIX02_ACCEPTANCE_20260713.md`. ResearchJob 001A has partial
> implementation but is not accepted. Gemini must complete a bounded FIX-03;
> Claude and Mimo must not be dispatched yet.

## Current baseline

AlphaHive currently implements the signal-review and external-evidence contract
baseline. It is not yet a complete ResearchJob orchestration system and it does
not place live trades.

Independent acceptance evidence:

- `284` tests collected and `284` passed in `AlphaHive_V3/tests`;
- latest real run: `20260707_1341_utc`;
- latest candidate: `1000BONKUSDT`;
- aggregate quality status: `BLOCK`;
- identity blocker: `missing_contract_identity`;
- Paper eligibility: `REVIEW_REQUIRED` because derivatives data is incomplete;
- accepted external artifact: `MIMO-EXT-008`, containing 35 artifacts across
  ThemeDiscoveryReport, ExternalResearchEvidence, CaseStudyReport and
  RedTeamReport.

## Accepted implementation

1. Manifest status and mode are explicit and fail closed.
2. Snapshot, symbol metadata and return-tape hashes are verified when declared.
3. Quality evaluation is split into integrity, identity, history, derivatives,
   liquidity and Paper-eligibility gates.
4. Paper eligibility uses `ALLOW | REVIEW_REQUIRED | BLOCK` with reason codes.
5. Last-bar turnover, 24-hour turnover and valid-bar counts are separated.
6. Research output labels are direction-neutral.
7. Human checks are structured objects.
8. Content hash, artifact hash and input fingerprint have separate semantics.
9. External-evidence normalization is provider-neutral, deterministic when given
   an explicit observation time, and tags imported evidence as
   `UNVERIFIED_EXTERNAL_EVIDENCE`.
10. Tests use isolated output directories and must not modify authoritative run
    inputs.

## Current development roles

- Codex: architecture, task contracts, independent acceptance and merge decisions.
- Anti-Gravity with Gemini 3.1 Pro High: primary mainline code executor.
- Mimo: bounded infrastructure tasks, external-evidence normalization, validators
  and fixtures.
- Grok: no longer an active dependency. The existing Grok artifact is retained as
  a frozen external-intelligence fixture only.
- DeepSeek: not used for current work.

## Current runtime surface

Start command:

```powershell
cd "G:\Quant test\alpha_hive"
python -m uvicorn server.app:app --host 127.0.0.1 --port 8000
```

Dashboard:

```text
http://127.0.0.1:8000/app/review.html
```

Implemented signal APIs:

```text
GET  /api/signals/health
GET  /api/signals
GET  /api/signals/{record_id}
GET  /api/signals/{record_id}/prompt
POST /api/signals/export
```

## Not yet implemented

- file-backed ResearchJob store and append-only event ledger;
- manual evidence-import API using the accepted evidence validator;
- EvidenceVerificationReport persistence;
- ResearchAssessment import and validation;
- Owner decision persistence;
- deterministic PaperPlan creation from an approved Owner decision;
- state-directory notification outbox and Hermes/Feishu delivery;
- persistent browser drafts and cross-run research history.

## Current acceptance rule

No Agent report is accepted from text alone. Acceptance requires checking the
actual absolute paths, the final persisted artifact, the main test collection,
and side effects on authoritative inputs and production result directories.

The next implementation gate is the ResearchJob MVP described in
`NEXT_STAGE_HANDOFF_20260712.md`.

## Deployment adjustment

ResearchJob will be delivered as vertical slices. The active slice is
`RESEARCHJOB-MVP-001A`: store, server-generated job ID, frozen candidate
package, append-only hash-linked events, atomic persistence and Create/Get API.
It explicitly excludes evidence import, Owner decisions, PaperPlan, Feishu and
automatic Provider calls. Invalid future evidence imports are import-attempt
outcomes, not automatic terminal Job states.
