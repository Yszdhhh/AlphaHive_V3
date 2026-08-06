# ResearchJob first manual evidence — Grok acceptance (2026-07-17)

**task:** `RESEARCHJOB-FIRST-MANUAL-EVIDENCE-GROK-001`  
**formal external deliverable:** `C:\Users\10639\Desktop\AlphaHive_V3_A_DATA_HEALTH_deliverables\agent_outputs\grok\RESEARCHJOB-FIRST-MANUAL-EVIDENCE-GROK-001.json`  
**Codex acceptance:** `ACCEPTED / GREEN`  
**scope:** external public-source research artifact only; no import or job-state mutation performed.

## Acceptance evidence

- The exact JSON deliverable exists and has the required
  `agent_artifact_bundle_v1` schema, target `job_id`, target `record_id`,
  `performance_eligible: false`, and four artifacts tagged
  `UNVERIFIED_EXTERNAL_EVIDENCE`.
- Codex re-ran the production validation functions against the authoritative
  job: schema errors `[]`, hash errors `[]`, binding errors `[]`, cutoff errors
  `[]`. The bundle hash is
  `e038af4591f65f2fc6766c573955122ae2f416ef6e9531d4f3b7ffabb7bf3d5a`.
- The authoritative job remains `AWAITING_EVIDENCE`, with record
  `20260707_1341_utc_0001`, historical cutoff
  `2026-07-07T13:41:16.355313+00:00`, and `paper_plan_capability: BLOCK`.
  Its stored `package_hash` equals the bundle `input_fingerprint`:
  `e1be947478dade0704ce7bde0c66602ab4bee3447c49cb813fc14222308e565f`.
- A fresh public, no-credential replay reached all four cited direct pages and
  reproduced their reported pre-cutoff publication metadata: CoinDesk
  `2026-07-07T05:40:58.280Z`; Decrypt `2026-07-06T20:56:52Z`;
  Cointelegraph `2026-07-06T20:55:11.110Z`; BitcoinFoundation.org
  `2026-07-07T07:32:28+00:00`.
- Regression: `python -m pytest -q tests/test_research_jobs.py` returned
  `35 passed, 15 subtests passed`.

## Retained boundaries and advisory

This acceptance verifies importability and cutoff safety; it does not promote
the four public-news claims beyond `UNVERIFIED_EXTERNAL_EVIDENCE`. The
Cointelegraph page has a post-cutoff `updatedAt`; acceptance relies only on its
separately recorded, pre-cutoff `publishedAt` and preserves that distinction.

No repository, configuration, job store, scheduler, database, outbox,
credential, notification, PaperPlan, trigger or trading path was changed by
this acceptance. Existing unrelated dirty-worktree entries are not attributed
to Grok.

## Next stage and dispatch

1. **Ready after explicit Owner confirmation — `RESEARCHJOB-EVIDENCE-IMPORT-001` (T1/T2, Codex only):** submit this exact accepted bundle once to the existing
   evidence-import endpoint and verify the immutable receipt, event chain and
   state transition to `EVIDENCE_IMPORTED`. This is the first real job-store
   mutation and is not performed by this read-only acceptance.
2. **After a successful import — verification and assessment preparation (T1/T2):** Gemini may independently design/review the evidence-verification and
   assessment payload against the immutable imported evidence, while Codex
   remains the only writer. It must not make an Owner decision or produce a
   PaperPlan.
3. **Still PARK / Owner-only (T3):** MVP003 OwnerDecision, any
   `APPROVE_PAPER`, a PaperPlan, notification delivery, trigger ignition,
   credential/source changes and all trading. This `1000BONKUSDT` historical
   quality-BLOCK fixture is permanently excluded from Paper regardless of
   research progression.
