# RESEARCHJOB-FIRST-ASSESSMENT-GEMINI-001-CORRECTION-001

**task_id:** `RESEARCHJOB-FIRST-ASSESSMENT-GEMINI-001-CORRECTION-001`  
**agent:** Gemini external agent proxy  
**tier:** T1/T2 read-only assessment wording correction  
**repository write authority:** Codex only  
**source candidate:** `C:\\Users\\10639\\Desktop\\AlphaHive_V3_A_DATA_HEALTH_deliverables\\agent_outputs\\antigravity\\RESEARCHJOB-FIRST-ASSESSMENT-GEMINI-001.json`  
**exact corrected output:** `C:\\Users\\10639\\Desktop\\AlphaHive_V3_A_DATA_HEALTH_deliverables\\agent_outputs\\antigravity\\RESEARCHJOB-FIRST-ASSESSMENT-GEMINI-001-CORRECTION-001.json`  
**fallback PARK output:** `C:\\Users\\10639\\Desktop\\AlphaHive_V3_A_DATA_HEALTH_deliverables\\agent_outputs\\antigravity\\RESEARCHJOB-FIRST-ASSESSMENT-GEMINI-001-CORRECTION-001-PARK.md`

## Objective

Correct only the `synthesis_findings.summary` wording and recompute the
production `artifact_hash`. The original candidate has correct schema, hash and
all live bindings, but production rejects its summary because the serialized
text contains the forbidden execution token `PAPER_PLAN` inside the phrase
`paper_plan_capability`.

Use exactly this replacement summary:

`Multiple sources reported before the external information cutoff that the BONK DAO treasury was drained of approximately $20 million via a malicious governance proposal (BIP #76). The imported public news remains UNVERIFIED_EXTERNAL_EVIDENCE. The historical replay is qualitative-only, the current quality gate is BLOCK, and performance eligibility remains false.`

Leave every other field byte-for-byte semantically unchanged. Remove
`artifact_hash`, recompute SHA-256 using the production rule
`json.dumps(value, sort_keys=True, ensure_ascii=False, default=str)` with
default separators, then restore it. Expected corrected hash:
`0a7c8e9dd06e5277f6c9ea5a7d900e03cb64a59f27e5e862b573cf16124b7ca6`.

## Hard boundaries

Do not modify any repository, configuration, results, job store, test, data,
scheduler, database, outbox, credential or external account. Do not submit any
endpoint. Do not create OwnerDecision, PaperPlan, notification, trigger or
trading activity. If the source differs, write PARK rather than guessing.
