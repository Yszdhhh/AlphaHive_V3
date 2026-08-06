# ResearchJob MVP 002 verification and assessment — dispatch plan

**created:** 2026-07-17  
**predecessor:** `RESEARCHJOB-MVP-001B-CODEX-IMPLEMENTATION-001` accepted  
**active slice:** `RESEARCHJOB-MVP-002_VERIFICATION_AND_ASSESSMENT`

## Scope and boundary

Implement immutable, versioned verification and assessment artifacts that bind
to the accepted candidate package and evidence set. This is a T1/T2 engineering
slice. It is not authorization for automatic provider calls, external web/API
access, Owner decisions, Paper plans, notifications, trigger ignition,
credentials, data-source changes, threshold changes or trading.

## Ordered work

| Order | Task ID | Owner | Tier | Task file | Exact Desktop output | Dispatch condition |
|---|---|---|---|---|---|---|
| A | `RESEARCHJOB-MVP-002-GOAL-ARCH-001` | Gemini / antigravity | T1/T2 read-only | `gemini__codex__researchjob_002_goal_architecture.md` | `agent_outputs/antigravity/RESEARCHJOB-MVP-002-GOAL-ARCH-001.md` | Dispatch now |
| B | `RESEARCHJOB-MVP-002-GROK-PREFLIGHT-AUDIT-001` | Grok | T1 read-only | `grok__codex__researchjob_002_preflight_audit.md` | `agent_outputs/grok/RESEARCHJOB-MVP-002-GROK-PREFLIGHT-AUDIT-001.md` | Replaces unavailable Mimo task; dispatch now |
| C | `RESEARCHJOB-MVP-002-CODEX-IMPLEMENTATION-001` | Codex | T1/T2 writer | `codex__researchjob_002_implementation.md` | Codex handoff in `reports/` | Only after Gemini architecture plus correction, and B, are accepted |
| D | `RESEARCHJOB-MVP-002-FINAL-AUDIT-001` | DeepSeek V4 | T1/T2 read-only | To be created with the implementation handoff | Exact Desktop path set with candidate | Only after C regression receipts exist |

## Acceptance outcome required from this stage

Only evidence that is already imported and immutable may be referenced.
Verification must be versioned and immutable; assessment must bind to a
specific verification artifact and remain direction-neutral. The accepted Job
state sequence is limited to:

```text
EVIDENCE_IMPORTED -> EVIDENCE_VERIFIED -> RESEARCH_ASSESSMENT_READY
```

Any invalid transition, missing binding, hash mismatch, stale/corrupt evidence,
or concurrent publication race must fail closed. Owner review and every later
state remain outside this stage.
