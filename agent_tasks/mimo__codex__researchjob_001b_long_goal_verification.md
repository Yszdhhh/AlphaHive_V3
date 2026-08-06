# RESEARCHJOB-MVP-001B-MIMO-LONG-GOAL-VERIFY-001

**task_id:** `RESEARCHJOB-MVP-001B-MIMO-LONG-GOAL-VERIFY-001`  
**agent:** Mimo external agent proxy, long-thread goal mode  
**tier:** T1 read-only mechanical verification  
**repository write authority:** Codex only  
**exact Desktop output:** `C:\Users\10639\Desktop\AlphaHive_V3_A_DATA_HEALTH_deliverables\agent_outputs\mimo\RESEARCHJOB-MVP-001B-MIMO-LONG-GOAL-VERIFY-001.md`

## Long-thread goal

Mechanically verify ResearchJob MVP 001B from the pre-change baseline through
the final Codex candidate. Continue until every in-scope check has reproduced
evidence or is explicitly `PARK` with the missing input. Do not modify the
repository or authoritative result stores. Use temporary directories for all
API, concurrency and failure tests.

## Required reading

Read in the exact order mandated by:

1. `G:\Quant test\AGENTS.md`
2. `G:\Quant test\AlphaHive_V3\AGENTS.md`
3. `G:\Quant test\AlphaHive_V3\PROJECT_REQUIRED_READING.md` and every file it lists, in order
4. `G:\Quant test\AlphaHive_V3\PROJECT_OPERATING_PLAYBOOK.md`
5. `G:\Quant test\AlphaHive_V3\agent_tasks\README.md`
6. This task file
7. `G:\Quant test\AlphaHive_V3\config\research_orchestration_contract.yaml`
8. `G:\Quant test\AlphaHive_V3\reports\RESEARCHJOB_001A_FIX03_CODEX_HANDOFF_20260716.md`
9. `C:\Users\10639\Desktop\AlphaHive_V3_A_DATA_HEALTH_deliverables\agent_outputs\mimo\RESEARCHJOB-MVP-001B-PREFLIGHT-AUDIT-001.md`
10. `G:\Quant test\AlphaHive_V3\reports\RESEARCHJOB_001B_CODEX_HANDOFF_20260717.md`
11. Current `G:\Quant test\alpha_hive\server\research_job_*.py`
12. Current `G:\Quant test\AlphaHive_V3\tests\test_research_jobs.py`

## Required baseline and checks

- Record SHA-256 for the four ResearchJob implementation/test files and for
  `G:\Quant test\alpha_hive\results\signal_review\latest.json` before and
  after all tests.
- Run focused, adjacent and full regression suites; report exact pass/fail
  counts and durations. Do not hide warnings or skipped tests.
- Exercise valid import, every contract rejection status, malformed JSON,
  oversized/deep payload, invalid timestamp/cutoff, record/job mismatch and
  path-like content-hash inputs.
- Verify attempt files are immutable and all attempts are linked through
  pointers and valid events without letting rejected evidence become
  authoritative.
- Verify repeat import and multi-worker same-content concurrency yield exactly
  one accepted evidence artifact and deterministic duplicate outcomes.
- Inject failures before manifest publication, after quarantine, during
  immutable publish and during mutable event/job/pointer replacement; verify
  next safe read/import recovers or fails closed without partial authority.
- Tamper with evidence, attempts, events, job and pointers independently and
  verify GET fails closed.
- Verify signal-review `latest.json`, quality/Paper capabilities, Owner
  decision paths, outbox, scheduler, database and trading paths remain
  untouched. Separate expected temporary/outbox test drift from authoritative
  input drift.
- Check `git diff --check` and list every changed path without attributing
  pre-existing worktree changes to this task.

## Required output

The report header must include agent identity, exact task ID, UTC timestamp,
all inputs and hashes, status (`GREEN`, `PARK`, or `UNVERIFIED`) and unresolved
items. Include a PASS/ADVISORY/PARK matrix, exact commands and outputs,
baseline/after hashes, failure-injection receipts, concurrency counts, changed
path inventory and `SELF_CHECK`.

## Hard boundaries

No repository or fixture edits, no writes to authoritative ResearchJob or
signal-review result directories, no external provider/API calls, credentials,
source changes, database/scheduler mutation, trigger ignition, Paper `ALLOW`,
Owner signature, notification delivery or trading action. The Desktop report
is the only allowed output.
