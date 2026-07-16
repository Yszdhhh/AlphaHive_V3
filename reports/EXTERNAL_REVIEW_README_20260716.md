# AlphaHive V3 — external review package

Open `00_READ_FIRST/PROJECT_STATUS_20260716.md` first.

## What is included

- `00_READ_FIRST/`: project status, blockers, Owner decision gates and review instructions.
- `01_REPO_SOURCE/AlphaHive_V3_SOURCE_20260716.zip`: clean Git snapshot at the packaged commit; no `.git`, raw databases, credentials or Hermes state.
- `02_KEY_REPORTS/`: current runtime, canonical, historical-data and acceptance reports.
- `03_AGENT_AUDITS/`: formal Mimo, antigravity, Sonnet and DeepSeek reports that are available on Desktop.
- `04_TASK_SPECS/`: exact task specifications used for independent review.
- `05_RUNTIME_EVIDENCE/`: latest Binance pull reports only; no checkpoint or raw Parquet data.
- `06_MANIFEST/`: file list, SHA-256 manifest and package boundary notes.

## Review order

1. Read `00_READ_FIRST/PROJECT_STATUS_20260716.md`.
2. Read `02_KEY_REPORTS/DATA_CANONICAL_COVERAGE_20260715.md` and the current acceptance reports.
3. Read the DeepSeek canonical and historical final audits in `03_AGENT_AUDITS/`.
4. Inspect the repository snapshot and run the documented tests if needed.

## Current decision boundary

The additive adapters and live Binance runtime are reviewable. Physical historical backfill, canonical database creation, data-contract source switching, OI cross-source ratio policy, CoinGlass deprecation and Paper/trigger changes remain Owner-controlled T3 decisions.

## Known evidence gap

The prior M-C2 final-audit verdict was accepted by the project, but the original Desktop Markdown was not found during consolidation. This is explicitly recorded in the status report; do not reconstruct or infer the missing file.
