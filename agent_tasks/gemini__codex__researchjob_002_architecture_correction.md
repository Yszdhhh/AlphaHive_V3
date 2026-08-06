# RESEARCHJOB-MVP-002-GOAL-ARCH-001-CORRECTION-001

**task_id:** `RESEARCHJOB-MVP-002-GOAL-ARCH-001-CORRECTION-001`  
**agent:** Gemini external agent proxy  
**tier:** T1/T2 read-only architecture correction  
**repository write authority:** Codex only  
**exact Desktop output:** `C:\\Users\\10639\\Desktop\\AlphaHive_V3_A_DATA_HEALTH_deliverables\\agent_outputs\\antigravity\\RESEARCHJOB-MVP-002-GOAL-ARCH-001-CORRECTION-001.md`

## Objective

Correct only the version-layout and predecessor-hash ambiguity in the original
`RESEARCHJOB-MVP-002-GOAL-ARCH-001` report. Read the original task, the
original Desktop report, the current research orchestration contract and the
current ResearchJob implementation. Do not modify repository files.

## Required corrections

1. Specify one internally consistent immutable layout using the governing
   contract paths: `verification/vNNNN.json` and `assessment/vNNNN.json`.
   Define `NNNN` as a deterministic, monotonically allocated four-digit
   version per job and artifact kind. Content hash belongs inside the immutable
   artifact and pointers/event records; it is not the filename.
2. Define the exact canonical `evidence_set_hash`: SHA-256 of the canonical
   JSON array of accepted evidence artifact hashes, sorted lexicographically.
3. Define exact predecessor bindings:
   - verification binds the accepted evidence-set hash and the latest accepted
     evidence-import event hash;
   - assessment binds the accepted verification artifact hash and the
     `EVIDENCE_VERIFIED` event hash.
4. Correct the hash-mismatch outcome taxonomy: a candidate/evidence/
   predecessor hash mismatch is `REJECTED_BINDING`; record/job identity
   mismatch is `REJECTED_RECORD_MISMATCH`; malformed/invalid shape is
   `REJECTED_SCHEMA`; duplicates are `DUPLICATE`.
5. State how each accepted/rejected attempt, artifact, version allocation and
   pointer hash is persisted/recovered under the existing quarantine + fsync +
   job-lock model.

## Output and boundaries

Write a concise addendum only to the exact Desktop output path above. Include
task header, status, inputs, no-mutation statement, corrected API/state table,
schema/layout, binding table, persistence/recovery notes, focused test cases,
Owner decision list and SELF_CHECK. No provider/API/web calls, source fetches,
credentials, Owner/Paper/trigger/notification/trading activity or repository
writes. Any unresolved ambiguity must be marked `PARK`.
