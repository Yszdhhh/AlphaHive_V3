# Prospective lifecycle preflight — partial acceptance and correction

**Codex acceptance:** `CORRECTION_REQUIRED`  
**Original report:** `C:\Users\10639\Desktop\AlphaHive_V3_A_DATA_HEALTH_deliverables\agent_outputs\antigravity\PROSPECTIVE-LIFECYCLE-PREFLIGHT-001.md`

## Accepted parts

The report correctly maps the immutable artifact sequence, identifies the
local-only modules that may be reused for testing, excludes real Feishu and
trading, and identifies the production repository/service/routes as the
likely integration boundary.

## Blocking architecture correction

The report incorrectly states that the current assessment stage requires
`performance_eligible: true`. Current
`alpha_hive/server/research_job_service.py` explicitly rejects every
assessment whose `performance_eligible` is not **false**, while
`harness/lib/paper_plan_engine.py` rejects every job whose corresponding value
is not **true**. It also requires `RESEARCH_ASSESSMENT_READY`, while a valid
Owner approval transitions the job to `PAPER_APPROVED`.

This is a real contract mismatch. No production PaperPlan endpoint, state
transition or implementation task may be accepted from the original preflight
until the corrected proposal distinguishes a future prospective assessment
contract from the current historical-only assessment contract and preserves all
T3 locks.

## Next stage and dispatch

Ready now: `PROSPECTIVE-LIFECYCLE-PREFLIGHT-CORRECTION-001`, Gemini, T1/T2
read-only. It must resolve the two contract mismatches and return a revised
minimal allowlist and tests. It does not authorize implementation.
