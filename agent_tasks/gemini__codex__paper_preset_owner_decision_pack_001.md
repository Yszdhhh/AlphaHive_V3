# PAPER-PRESET-OWNER-DECISION-PACK-001

**task_id:** `PAPER-PRESET-OWNER-DECISION-PACK-001`  
**agent:** Gemini external agent proxy  
**tier:** T1/T2 read-only decision-package preparation  
**repository write authority:** Codex only  
**exact Desktop output:** `C:\\Users\\10639\\Desktop\\AlphaHive_V3_A_DATA_HEALTH_deliverables\\agent_outputs\\antigravity\\PAPER-PRESET-OWNER-DECISION-PACK-001.md`

## Objective

Prepare one concise, evidence-backed Owner decision package for a possible
future promotion of `config/paper_execution_presets.yaml` from `DRAFT` to a
versioned `APPROVED` Paper-only preset. Do not promote it, change its file,
create an OwnerDecision, create a PaperPlan, or enable simulation, notification,
trigger or trading.

This package is meant to remove the remaining **configuration** blocker to a
future deterministic PaperPlan. It cannot remove the separate runtime blocker:
a fresh `PROSPECTIVE_LIVE`, quality-ALLOW job must still exist and reach
`RESEARCH_ASSESSMENT_READY`.

## Required reading

Read shared governance in the order required by
`G:\\Quant test\\AlphaHive_V3\\PROJECT_REQUIRED_READING.md`, then:

- this task;
- `G:\\Quant test\\AlphaHive_V3\\config\\paper_execution_presets.yaml`;
- `G:\\Quant test\\AlphaHive_V3\\reports\\PAPER_QUANT_SANDBOX_CODEX_HANDOFF_20260718.md`;
- `G:\\Quant test\\AlphaHive_V3\\reports\\RESEARCHJOB_MVP003_CODEX_HANDOFF_20260718.md`;
- `G:\\Quant test\\AlphaHive_V3\\reports\\RESEARCHJOB_MVP003_FINAL_AUDIT_ACCEPTANCE_20260718.md`;
- `G:\\Quant test\\AlphaHive_V3\\reports\\OWNER_DECISION_CONFIRMATION_TEMPLATE_20260718.md`;
- `G:\\Quant test\\AlphaHive_V3\\OWNER_APPROVALS.md` and
  `OWNER_DECISIONS_NEEDED.md`;
- existing `harness/lib/paper_plan_engine.py`, its tests and paper fixtures.

## Required deliverable

Give the Owner a single recommendation among: **do not approve**, **approve
unchanged with a version bump**, or **approve only after named parameter
changes**. Include:

1. the current complete preset version/status and its canonical SHA-256 using
   the same self-reference-excluding rule as `_preset_hash`;
2. a compact table of all risk, sizing, friction, stop, target, horizon,
   leverage/exposure and loss-limit values that would become binding;
3. positive and negative consequences of approval, including that it permits
   only future deterministic PaperPlan review after all other gates, never live
   trading;
4. exact proposed approval text the Owner can reply with, including approved
   version and hash, scope `PAPER_ONLY`, no trigger/no notification/no trading,
   and no retroactive effect on historical or BLOCK jobs;
5. a complete negative matrix: historical replay, BLOCK quality, no ALLOW
   capability, hash mismatch, version mismatch, mutable preset name, and
   missing per-job Owner confirmation;
6. an explicit statement that the current BONK job stays permanently
   ineligible and that no current scanner result is a Paper candidate.

## Hard boundaries

Read-only only. Do not change repo/config/tests/results, make web/provider/API
calls, create a PaperPlan, set status to APPROVED, manufacture a hash, submit
an OwnerDecision, assign direction, ignite triggers, send notifications, or
perform Paper/live trading. Write only the exact Desktop report. Include
file:line evidence, PASS/ADVISORY/PARK matrix and `SELF_CHECK`.
