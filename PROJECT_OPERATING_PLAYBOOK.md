# AlphaHive V3 — task dispatch, collaboration and acceptance playbook

**Purpose:** persistent operating memory for new Codex conversations. Read this after `PROJECT_REQUIRED_READING.md` and before dispatching or accepting external-agent work.

## 1. Operating model

- Codex is the primary coordinator, repository writer, test runner, packager and final integrator.
- External agents do not write `G:\Quant test\AlphaHive_V3\` unless the Owner explicitly changes the task boundary.
- External agents write only their exact Desktop deliverable path. A chat summary is not a deliverable.
- Every task has one stable `task_id`, one owner agent, one exact output path and one final status.
- If a required path or input does not exist, the agent must output `PARK`; it must not guess, substitute a historical package, or silently continue.

## 2. Fixed agent roles

| Agent | Normal role | Not the default role |
|---|---|---|
| Codex | Implementation, integration, tests, commits, packaging, acceptance | Passive relay of agent summaries |
| Mimo | Runtime health, data coverage, checkpoint/scheduler reconciliation, mechanical read-only checks | Final code or policy gate |
| antigravity / Gemini 3.1 Pro | Architecture, schema, source-comparison and contract research; isolated prototypes | Sole final auditor of its own implementation |
| DeepSeek V4 | Independent final audit of code, packages, evidence and high-risk research claims | Duplicate worker that repeats another agent's summary |
| Sonnet | Optional exploratory research or PC pre-review when stable | Sole approval gate; use DeepSeek for final audit |

Use orthogonal roles. Mimo may inspect runtime while Agy studies schema and DeepSeek audits the resulting package. Two agents should audit the same package only when a deliberate second opinion is needed.

## 3. Task tiers

### T1 — safe / read-only / additive

Examples: runtime reconciliation, schema inspection, coverage reports, offline renderers, tests and documentation. Codex may implement a bounded T1 change, run tests, commit it and request an independent spot-check.

### T2 — engineering decision

Examples: naming, schema versioning, cutoff semantics, canonical field mapping and archive policy. Require evidence and explicit acceptance in the tracker. T2 does not authorize triggers, Paper or credentials.

### T3 — Owner approval required

Always `PARK` until the Owner approves the exact item: trigger ignition, threshold changes, Paper `ALLOW`, real trading/order paths, credentials/API/proxy changes, data-source path switching, canonical database activation, historical backfill, CoinGlass deprecation, or any directional thesis decision.

## 4. Dispatch procedure

1. Codex reads the shared required-reading set.
2. Codex creates or selects one exact task file under `agent_tasks/`.
3. The dispatch message names the agent, `task_id`, tier, objective, required inputs, exact output path, hard boundaries and required verdict tokens.
4. The agent reads shared docs first, then only the named task file. It must not self-select another task from a directory.
5. Read-only tasks with distinct outputs may run in parallel. If one task produces an input for another, run them sequentially.
6. Codex collects the formal Desktop reports, verifies them, updates `ARC_CURRENT_WAVE_001.md`, and only then integrates or packages.

### Copy-paste dispatch skeleton

```text
你是 [agent]，执行 task_id=[TASK-ID]，tier=[T1/T2/T3]。
先按顺序阅读：G:\Quant test\AGENTS.md、G:\Quant test\AlphaHive_V3\AGENTS.md、G:\Quant test\AlphaHive_V3\PROJECT_REQUIRED_READING.md，以及任务文件：G:\Quant test\AlphaHive_V3\agent_tasks\[TASK-FILE].md。
只执行该任务，不要自选其他任务。正式报告只能写入：[EXACT-DESKTOP-OUTPUT-PATH]。
如果必需输入或路径缺失，输出 PARK，不要猜测或替换路径。完成后回传正式报告路径、状态、证据、未决项；聊天摘要不能替代报告。
```

## 5. Parallelism rules

Safe to run together when all are true:

- every task is read-only or isolated;
- agents write different Desktop output files;
- no task depends on another task's not-yet-written report;
- no agent changes source code, scheduler, database, credentials or contracts.

Recommended parallel wave: Mimo runtime + Agy architecture research + DeepSeek independent audit. Sonnet research is optional and should not be the final gate.

## 6. Acceptance procedure

Codex accepts an agent result only after checking:

1. Exact output path exists and is the requested file, not a renamed or historical substitute.
2. Header contains agent identity, `task_id`, UTC timestamp, exact inputs, status/verdict and unresolved items.
3. Evidence is reproducible: file paths, line numbers, object keys, test logs or runtime reports.
4. Scope obeys the task boundary; no hidden repository, database, scheduler or credential mutation occurred.
5. Facts, inference, recommendation and Owner decisions are separated.
6. Contradictions are investigated directly against source files; summaries are not evidence.
7. Tests and `git diff --check` pass for Codex changes.

Acceptance labels:

- `ACCEPTED / GREEN`: evidence complete and scope safe.
- `ACCEPTED_WITH_ADVISORY_CORRECTION`: core result valid, wording or non-blocking detail needs correction.
- `PARK`: missing input, provenance gap, unresolved evidence or T3 decision.
- `FAIL`: boundary violation, unsupported claim, contradictory evidence or regression.

### 6.1 Mandatory next-stage closure

Every Codex acceptance record must end with a `Next stage and dispatch` section.
It must state the next ordered slice, its tier and hard exclusions; name every
external task with its stable `task_id`, exact task file and Desktop output
path; distinguish tasks ready to dispatch now from tasks waiting for a named
dependency; and list any Owner-only gates separately. The same acceptance
must update the current-wave tracker and include copy-paste dispatch messages
for external agents. In the user-facing acceptance reply, Codex must also
print each ready-to-dispatch message together with its full task-file and exact
Desktop-output paths; a link to a repository task file alone is not sufficient.
A completed slice may not leave the next engineering step implicit or buried in
a chat summary.

## 7. Provenance and audit separation

- The implementer must not be the sole final auditor of its own change.
- Preserve each agent's original report and model identity. If another model edits a report, record the handoff; otherwise mark provenance limited.
- DeepSeek is the default final auditor for code/package and high-risk evidence. Agy/Mimo findings are inputs, not final approval.
- Never upgrade a `PARK` or `UNVERIFIED` research claim to `GREEN` because another agent repeated it.

## 8. Packaging and Desktop hygiene

Codex creates one dated external-review package containing:

- `00_READ_FIRST/` status, governance and Owner gates;
- `01_REPO_SOURCE/` clean Git source snapshot without `.git`;
- `02_KEY_REPORTS/` current reports;
- `03_AGENT_AUDITS/` original agent artifacts;
- `04_TASK_SPECS/` exact task instructions;
- `05_RUNTIME_EVIDENCE/` selected runtime reports;
- `06_MANIFEST/` package boundary and file manifest.

Do not include raw databases, Parquet, `.env`, secrets, credentials, Hermes state or browser state. Keep the active `AlphaHive_V3_A_DATA_HEALTH_deliverables` folder because future agents may need its exact output path. Move older AlphaHive Desktop deliverable folders into one dated archive folder instead of deleting them.

## 9. New-conversation bootstrap

Paste this at the start of a new Codex conversation:

```text
这是 AlphaHive V3 的续接对话。请先读取：
G:\Quant test\AlphaHive_V3\PROJECT_REQUIRED_READING.md
G:\Quant test\AlphaHive_V3\PROJECT_OPERATING_PLAYBOOK.md
G:\Quant test\AlphaHive_V3\agent_tasks\ARC_CURRENT_WAVE_001.md
然后汇报：当前已完成项、唯一阻塞项、Owner 决策项、可并行派发项。遵守：只有 Codex 写仓库；外部 Agent 只写指定 Desktop 报告；路径不匹配必须 PARK；T3 不得自行执行。不要从旧聊天摘要推断状态，直接核对文件和测试。
```

## 10. Current project-specific rule

The active historical-data gate is `PARK`: BTCUSDT has an object-level 2020-09-01 metrics proof, but the full effective universe does not. No global cutoff, backfill, canonical source switch or CoinGlass deprecation may be inferred until the Owner decides and the required symbol-level evidence exists.
