# ResearchJob MVP003 Gemini architecture acceptance (2026-07-17)

**task:** `RESEARCHJOB-MVP-003-GOAL-ARCH-001`  
**formal external report:** `C:\\Users\\10639\\Desktop\\AlphaHive_V3_A_DATA_HEALTH_deliverables\\agent_outputs\\antigravity\\RESEARCHJOB-MVP-003-GOAL-ARCH-001.md`  
**Codex acceptance:** `ACCEPTED_WITH_ADVISORY_CORRECTION`

## Accepted core

The report correctly keeps MVP003 as architecture only; defines the intended
manual OwnerDecision endpoint and versioned immutable store; binds decisions to
the candidate, evidence, verification, assessment and predecessor-event hashes;
and preserves the hard rule that a historical quality-BLOCK job such as the
current BONK fixture can never receive `APPROVE_PAPER`. Its quarantine, lock,
fsync, event-chain and pointer direction is consistent with the accepted
MVP001B/002 pattern.

## Required correction before implementation planning is considered complete

The required formal header is missing. More materially, the report does not
provide the requested API/state/event table or a concrete Owner-decision list
for the confirmation-text authority, Owner identity/authentication context and
immutable selected-preset binding policy. These values are not safe to infer.
It must also state the exact GET/pointer fail-closed validation extension.

The correction task is
`agent_tasks/gemini__codex__researchjob_003_goal_architecture_correction.md`.
MVP003 implementation itself remains PARK until a job reaches
`RESEARCH_ASSESSMENT_READY` and the Owner supplies the listed T3 package.
