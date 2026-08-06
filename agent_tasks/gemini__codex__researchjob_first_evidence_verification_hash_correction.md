# RESEARCHJOB-FIRST-EVIDENCE-VERIFICATION-GEMINI-001-CORRECTION-001

**task_id:** `RESEARCHJOB-FIRST-EVIDENCE-VERIFICATION-GEMINI-001-CORRECTION-001`  
**agent:** Gemini external agent proxy  
**tier:** T1/T2 read-only artifact hash correction  
**repository write authority:** Codex only  
**source candidate:** `C:\\Users\\10639\\Desktop\\AlphaHive_V3_A_DATA_HEALTH_deliverables\\agent_outputs\\antigravity\\RESEARCHJOB-FIRST-EVIDENCE-VERIFICATION-GEMINI-001.json`  
**exact corrected output:** `C:\\Users\\10639\\Desktop\\AlphaHive_V3_A_DATA_HEALTH_deliverables\\agent_outputs\\antigravity\\RESEARCHJOB-FIRST-EVIDENCE-VERIFICATION-GEMINI-001-CORRECTION-001.json`  
**fallback PARK output:** `C:\\Users\\10639\\Desktop\\AlphaHive_V3_A_DATA_HEALTH_deliverables\\agent_outputs\\antigravity\\RESEARCHJOB-FIRST-EVIDENCE-VERIFICATION-GEMINI-001-CORRECTION-001-PARK.md`

## Objective

Correct only the candidate report's `artifact_hash` serialization. The original
candidate has correct schema, job/record/candidate/evidence/predecessor
bindings, but its hash was computed with compact separators. The production
ResearchJob verifier uses the repository `_schema_canonical_json` rule:

`json.dumps(value, sort_keys=True, ensure_ascii=False, default=str)`

with default separators (including spaces). Remove `artifact_hash`, recompute
SHA-256 over the exact remaining JSON object using that rule, restore the hash,
and write the corrected JSON to the exact output path. Expected corrected hash:
`8e164d7dbf828e082827bf796bce0f4909cfea699c314261c3b7621865359882`.

## Hard boundaries

Do not change any other field, do not read or write the repository/job store,
do not submit any endpoint, and do not create an OwnerDecision, PaperPlan,
notification, trigger or trading action. If the source candidate differs from
the described object, write PARK rather than guessing. Return the exact output
path and hash.
