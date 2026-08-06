# OwnerDecision confirmation template

**Status:** `TEMPLATE_ONLY / NOT_AN_OWNER_DECISION`  
**Purpose:** collect the three governance inputs required before the future
OwnerDecision implementation slice can be activated. This document cannot
approve a job, generate a PaperPlan, enable delivery, ignite a trigger, or
place an order.

## Part A — one-time governance confirmation

Copy the block below, replace only the bracketed values, and send it as the
Owner's explicit confirmation.

```text
OWNER_DECISION_GOVERNANCE_V1

owner_id: [stable non-secret owner label]
authentication_context: [how this Owner confirmation is authenticated]

confirmation_text_version: owner_decision_confirmation_v1
confirmation_text:
  I confirm that a future, separately identified prospective ResearchJob may
  enter the deterministic PaperPlan review path only after all bound evidence,
  verification, assessment, eligibility, and risk checks have passed. This is
  not permission for live trading, trigger ignition, external notification, or
  any action for a historical-replay or BLOCK-quality job.

preset_binding_policy: immutable_exact_file_hash
preset_source: config/paper_execution_presets.yaml
preset_selection_rule: decision must name one existing preset_version and its
  SHA-256 hash computed from the canonical preset object; a mismatch rejects
  the decision.

I confirm the above governance policy: [OWNER_NAME_OR_LABEL]
confirmation_date_utc: [YYYY-MM-DDTHH:MM:SSZ]
```

### Recommended values

- `owner_id`: a stable, non-secret label such as `local_owner_10639`; do not
  use an API key, email password, or access token.
- `authentication_context`: `interactive_owner_confirmation_in_Codex` is a
  sensible local-first starting point. A later stronger mechanism can replace
  it only through a versioned policy change.
- `preset_binding_policy`: keep `immutable_exact_file_hash`; never bind merely
  to a mutable preset name.

## Part B — future per-job Paper approval

This block is intentionally unusable until a fresh `PROSPECTIVE_LIVE`, quality
`ALLOW` job reaches `RESEARCH_ASSESSMENT_READY`. It must never be used for the
historical `1000BONKUSDT` fixture.

```text
OWNER_DECISION_FOR_ONE_JOB_V1

decision: APPROVE_PAPER
job_id: [job id]
record_id: [record id]
candidate_package_hash: [64-char SHA-256]
evidence_set_hash: [64-char SHA-256]
verification_hash: [64-char SHA-256]
assessment_hash: [64-char SHA-256]
predecessor_hash: [assessment event hash]

selected_preset_version: [existing preset version]
selected_preset_hash: [canonical SHA-256 of that preset]
direction: [Owner-specified direction, if the approved future contract requires it]
owner_id: [must equal Part A]
authentication_context: [must satisfy Part A]
confirmation_text_version: owner_decision_confirmation_v1
confirmation_text: [must exactly equal Part A]
decision_time_utc: [YYYY-MM-DDTHH:MM:SSZ]

I approve only this bound prospective Paper review: [OWNER_NAME_OR_LABEL]
```

## Hard rejections

- Missing, stale, substituted, or mismatched hashes.
- A historical-replay, `BLOCK`, or non-`ALLOW` job.
- A mutable preset name without the exact hash.
- An agent-generated signature, inferred direction, or copied confirmation
  text without the Owner's explicit confirmation.
- Any interpretation that this document allows live trading, delivery,
  credentials, trigger ignition, or source switching.
