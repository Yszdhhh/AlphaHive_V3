# External workspace inventory for review

**Inventory date:** 2026-08-06
**Audience:** independent cloud reviewers of AlphaHive V3
**Scope:** descriptive map of sibling material under the local `G:\Quant test` workspace. The sibling directories are **not** copied into this repository by this document.

## Review starting point

`AlphaHive_V3/` is the canonical source for the current review. It is the auditable anomaly-research and paper-execution-discipline system described in [`README.md`](../README.md) and [`PROJECT_CONSTITUTION.md`](../PROJECT_CONSTITUTION.md). It is not an automated trading bot, does not make Long/Short decisions, and does not authorize paper or live execution by itself.

The older `alpha_hive/` tree, the dashboard packages, and the orchestration/runtime trees are reference material only. Do not merge their code, metrics, factor claims, data, or execution paths into V3 without a new file-level review, tests, provenance, and the applicable Owner decision.

## What may be reusable

| Workspace path | What it contains | Potential value to V3 | Review posture |
|---|---|---|---|
| `external_architecture_pack/PROJECT_BRIEF.md` | Earlier system brief, local cockpit/API concept, signal-review flow, and DeepResearchPromptPackage outline | Useful for understanding the intended human workflow: anomaly scan → explainable review → bounded external research prompt | Context only; reconcile every statement with current V3 contracts and reports |
| `alpha_hive/dashboard/` | Static dashboards, review cockpit, mock data, and a small local server | Candidate UI patterns for an auditable review cockpit and prompt-copy workflow | Reuse presentation ideas only after checking that no hidden signal or direction logic is introduced |
| `alpha_hive/server/` | Earlier API/service/repository layer for signal review and research-job outputs | Candidate reference for HTTP boundary, record lookup, and prompt export | Legacy/parallel implementation; verify schemas and data provenance before reuse |
| `Dashboard_R1_FIX_PACKAGE/` | Frontend repair package and standalone preview | Reusable Plotly/HTML interaction and rendering fixes | Frontend-only reference; do not treat its old factor receipts as current evidence |
| `refactor_kickoff/` | Refactor plans, execution checklists, architecture notes, subjective-quant and beta-hedge research notes | Historical design rationale, negative findings, and migration checklists | Historical evidence; preserve provenance and do not revive graveyard directions without new evidence |
| `us_stock_daily/` | Python report/chart generator plus generated daily-report examples | Reusable reporting, chart generation, and Markdown briefing patterns | Separate US-equity utility; no crypto research conclusion should be inferred from it |
| `alpha_hive/tools/QuantDinger/` | External/open-source quant operating-system code with charting, research, backtesting, MCP, and multi-venue execution examples | Architecture inspiration for local-first tools and agent/MCP boundaries | Treat as an external dependency/reference; V3 must not inherit live-order paths, credentials, or execution assumptions |
| `alpha_hive/tools/Kronos/` | External financial-market foundation-model code, tokenizer/fine-tuning examples, and model documentation | Possible future offline research/forecasting experiment | Separate research line; any use needs an explicit experiment, leakage controls, licensing/compute review, and no trading authority |

## Material that should not be reused automatically

| Workspace path | Why it is excluded from automatic reuse |
|---|---|
| `AO_DEV/` | Development runtime, Go toolchain, module cache, and agent-orchestrator implementation. It is infrastructure, not AlphaHive research evidence. |
| `AO_SANDBOX/` | Sandbox/clone of AlphaHive material. It can diverge from the canonical repository and must not be treated as a second source of truth. |
| `.openclaw/`, `.agents/`, `memory/` | Local runtime state, agent memory, and provenance/session material. These are not public project inputs. |
| Root `MEMORY.md`, `USER.md`, `IDENTITY.md`, `SOUL.md`, `TOOLS.md`, and similar files | Personal or workspace-level operating context; not part of the V3 product boundary. |
| Raw data outside the repository and local generated data inside it | Raw databases, Parquet snapshots, caches, lock files, and runtime outputs are intentionally outside the public review source. JSON/YAML manifests and hashes may be retained when they document reproducibility without carrying the raw data. |
| Any credential, token, `.env`, key, proxy, notification, or trading configuration | The V3 constitution and orchestration protocol prohibit exposing or changing these as part of research review. |

## Suggested external-review questions

1. Which dashboard/API concepts from the legacy `alpha_hive` line can be re-expressed as read-only views over the current V3 contracts without duplicating governance or creating a second source of truth?
2. Which historical factor findings are genuinely reproducible from the current evidence, and which belong in the graveyard or remain `UNVERIFIED`?
3. Can the current canonical price snapshot, research-job, and paper-discipline boundaries remain fail-closed when the UI, external provider, or data source is replaced?
4. Which components are safe T1/T2 engineering candidates, and which would require an explicit Owner/T3 decision because they touch data-source precedence, triggers, Paper `ALLOW`, credentials, notifications, or trading?

## Public-review boundary

This inventory is intentionally a map, not a bulk export. The public repository should be reviewed as follows:

- Start with `PROJECT_CONSTITUTION.md`, `GRAVEYARD.md`, `KNOWN_LIMITATIONS.md`, and `OWNER_DECISIONS_NEEDED.md`.
- Treat `config/`, `harness/`, `scripts/`, `tests/`, and dated `reports/` as the current evidence surface.
- Treat sibling paths in this document as leads for targeted comparison, not as approved dependencies.
- Do not infer a profitable strategy, a live-trading capability, or a completed quality gate from historical reports or legacy dashboards.
- Do not assume that a missing raw Parquet file is an implementation defect: public review excludes raw data by design; the tracked manifests and hashes define what can be checked locally when the data is available.
