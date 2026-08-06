# ResearchJob MVP003 preset-hash correction acceptance — 2026-07-18

**correction audit:** `RESEARCHJOB-MVP-003-PRESET-HASH-CORRECTION-AUDIT-001`  
**external report:** `C:\\Users\\10639\\Desktop\\AlphaHive_V3_A_DATA_HEALTH_deliverables\\agent_outputs\\deepseek\\RESEARCHJOB-MVP-003-PRESET-HASH-CORRECTION-AUDIT-001.md`  
**acceptance:** `ACCEPTED / GREEN`

## Accepted correction

The OwnerDecision service and the deterministic offline PaperPlan engine now
use the identical compact canonical JSON preset hash: sorted keys, UTF-8,
`ensure_ascii=False`, compact `(',', ':')` separators, `default=str`, and
exclusion of `preset_hash`/`artifact_hash` self-reference fields.

Independent DeepSeek audit and Codex recomputation both prove:

- current `v0.1.0-draft / DRAFT` hash:
  `3cd1211a0bd7cacd7cc6ed115dc718072ea18c256fa3641be9f674723523a290`;
- in-memory proposed `v0.1.0 / APPROVED` hash:
  `a81ad47bbb332ef26d2399c7fae1e58ce1232534406f8b140f9654dd16edb958`;
- focused regression: 39 passed, 15 subtests; full regression: 389 passed,
  15 subtests; and
- no preset write, OwnerDecision, PaperPlan, trigger, notification or trading
  side effect.

The original Gemini decision text is superseded. Its correction report is
accepted as the valid proposed Owner approval package.

## Remaining Owner decision

The configuration gate remains open only until the Owner explicitly approves
the exact proposed target version/hash. Approval would authorize Codex to
perform the narrow configuration promotion and nothing else. It would not
create a PaperPlan or bypass the remaining runtime gate: a fresh,
`PROSPECTIVE_LIVE`, quality-ALLOW ResearchJob must still reach
`RESEARCH_ASSESSMENT_READY`.
