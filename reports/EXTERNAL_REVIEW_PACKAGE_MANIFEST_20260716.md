# External review package manifest

**Package directory:** `C:\Users\10639\Desktop\AlphaHive_V3_EXTERNAL_REVIEW_20260716`
**Source snapshot:** Git `HEAD` at packaging time; `.git` excluded.

## Contents

| Directory | Contents | Deliberate exclusions |
|---|---|---|
| `00_READ_FIRST` | Status, governance, Owner gates, review instructions | None |
| `01_REPO_SOURCE` | Clean source ZIP from Git `HEAD` | `.git`, raw DB, Parquet, Hermes state, credentials |
| `02_KEY_REPORTS` | Current runtime, canonical, historical and acceptance reports | Historical raw run directories |
| `03_AGENT_AUDITS` | Available Mimo, antigravity, Sonnet, DeepSeek and cockpit artifacts | Missing M-C2 final-audit file is not reconstructed |
| `04_TASK_SPECS` | Current wave and exact external-agent task specifications | No agent conversation transcripts |
| `05_RUNTIME_EVIDENCE` | Latest five Binance pull reports | Checkpoint and live database |
| `06_MANIFEST` | This manifest and package boundary notes | — |

## Review caveats

- The M-C2 final-audit verdict was previously accepted but its original Desktop Markdown was not found during consolidation; this is explicitly recorded as a provenance gap.
- Historical research final verdict is `PARK`; no backfill or source switch is authorized.
- External reviewers should use the repository source snapshot and current tests as primary evidence.
