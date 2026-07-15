# ARC-C-PREVIEW-001 — independent M-C2 offline cockpit pre-review

**agent:** Gemini 3.1 Pro  
**tier:** T1 / read-only independent review  
**output:** `C:\Users\10639\Desktop\AlphaHive_V3_C_M-C2_deliverables\agent_outputs\gemini_3_1_pro\ARC-C-PREVIEW-001_INDEPENDENT_REVIEW.md`

## Required reading

1. `G:\Quant test\AlphaHive_V3\AGENTS.md`
2. `G:\Quant test\AlphaHive_V3\PROJECT_REQUIRED_READING.md`
3. This task file.

## Objective

Review M-C2 for safe packaging as a local, non-sending candidate cockpit.  The review must be independent: do not rely on Codex's summary or claim an uninspected output is safe.

## Required inputs

- `G:\Quant test\AlphaHive_V3\scripts\97_render_local_cockpit.py`
- `G:\Quant test\AlphaHive_V3\tests\test_render_local_cockpit.py`
- commit `8567cb4` diff and direct parent context.
- `C:\Users\10639\Desktop\AlphaHive_V3_ArcC_MC2_deliverables\agent_outputs\mimo\ARC-C-COCKPIT-001.html`
- `C:\Users\10639\Desktop\AlphaHive_V3_ArcC_MC2_deliverables\agent_outputs\mimo\ARC-C-COCKPIT-001.css`
- `C:\Users\10639\Desktop\AlphaHive_V3_ArcC_MC2_deliverables\agent_outputs\mimo\ARC-C-COCKPIT-001.js`
- `C:\Users\10639\Desktop\AlphaHive_V3_ArcC_MC2_deliverables\agent_outputs\mimo\ARC-C-COCKPIT-001_README.md`
- `C:\Users\10639\Desktop\AlphaHive_V3_ArcC_MC2_deliverables\agent_outputs\mimo\ARC-C-COCKPIT-001_RUNTIME_RENDER.html`

## Required checks

1. Static-safety scan: no `fetch`, XHR, WebSocket, form submit/action, webhook, external script/style, credential, send control, or implicit network navigation.
2. Verify the renderer reads a local CSV and HTML-escapes candidate fields; assess whether the regression protects the no-network claim.
3. Verify the original Mimo artifact is preserved as provenance and distinguish it from the Codex-generated runtime render.
4. Confirm no trigger, threshold, paper eligibility, data-source, credential, or trading behavior changed.
5. State the minimal packaging evidence Codex must include and issue `PASS_FOR_M-C2_PACKAGING`, `PARK`, or `FAIL`.

## Hard boundaries

- Read-only: no repository or Desktop artifact modifications, no network calls, no browser send actions.
- Do not review unrelated milestones or invent a production deployment path.

## Deliverable format

Header must contain `agent=gemini_3_1_pro`, `task_id=ARC-C-PREVIEW-001`, UTC timestamp, exact inputs read, verdict, and unresolved items.  Answer all five checks with file/line evidence.
