# F21 dispatch matrix

This file distinguishes the task prompt, the assigned agent, the allowed write path, and the actual provenance of the current run.

| task_id | assigned agent | prompt file | only allowed output path | current provenance |
|---|---|---|---|---|
| `F21-RECON-001` | mimo | `agent_tasks/mimo__codex__data_refresh_recon.md` | `Desktop\AlphaHive_V3_F21_deliverables\agent_outputs\mimo\DATA_REFRESH_RECON.md` | Actual mimo read-only dispatch was attempted and stopped after no output returned; no mimo original is accepted. Earlier package copy is archived under `pc_fallback/` and must not be treated as mimo provenance. |
| `F21-PROMPT-001` | antigravity | `agent_tasks/antigravity__codex__prompt_rerender.md` | `Desktop\AlphaHive_V3_F21_deliverables\agent_outputs\antigravity\RENDERED_RESEARCH_PROMPT.md` + `PROMPT_RERENDER_AUDIT.md` | Actual antigravity read-only dispatch was attempted and stopped after no output returned; no antigravity original is accepted. Earlier package copy is archived under `pc_fallback/` and must not be treated as antigravity provenance. |
| `F21-PREVIEW-001` | Sonnet / PC review | `agent_tasks/sonnet__codex__f21_pre_review.md` | `Desktop\AlphaHive_V3_F21_deliverables\agent_outputs\sonnet\SONNET_F21_PC_PRE_REVIEW.md` | Actual Sonnet-labelled read-only subagent completed; original report is retained. |

There was no separate Claude-specific subagent dispatch in this run. `codex` remains the only repo writer. Agents may write only their own Desktop output directory; no agent may modify `AlphaHive_V3/`, `_bus/`, credentials, DB, or external data.

The ZIP is a local Desktop artifact, not an automatic remote upload. Because the two attempted dispatches returned no output, Codex records those slots as `MISSING` and keeps the PC-owned evidence separately under `pc_fallback/`; it does not relabel it as agent output.
