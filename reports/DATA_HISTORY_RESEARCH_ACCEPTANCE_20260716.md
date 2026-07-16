# Historical-data research acceptance record

**Date:** 2026-07-16 (Asia/Shanghai)
**Reviewer:** Codex
**Artifact:** `ARC-DATA-HISTORY-RESEARCH-002`

## Current disposition

`PARK / DEEPSEEK_FINAL_AUDIT_ACCEPTED`

The research report exists at:

`C:\Users\10639\Desktop\AlphaHive_V3_A_DATA_HEALTH_deliverables\agent_outputs\sonnet\ARC-DATA-HISTORY-RESEARCH-002.md`

The research is useful as a lead, but is not accepted as a global historical-data decision basis.

DeepSeek's independent final audit exists at:

`C:\Users\10639\Desktop\AlphaHive_V3_A_DATA_HEALTH_deliverables\agent_outputs\deepseek\ARC-DATA-HISTORY-FINAL-AUDIT-001_INDEPENDENT_REVIEW.md`

Final verdict: `PARK`.

## Reasons for the hold

1. The report states `agent=Sonnet`, while the Owner reports that the first part was produced by Sonnet and the latter part by Gemini. The handoff and provenance are not recorded in the artifact.
2. The critical `2020-09-01` OI/taker metrics claim has no exact object keys, sample files, checksum values, or reproducible archive listing in the report.
3. The report's official-source citations are names, not evidence links or object-level verification.
4. A full-feature cutoff cannot be set globally until symbol coverage and dimension-specific first dates are independently verified.

The report's recommendations to backfill, set a 2020-09-01 cutoff, or deprecate CoinGlass remain T3 Owner decisions and are not authorized by this record.

## Verified conclusions accepted from DeepSeek

- BTCUSDT metrics beginning 2020-09-01 are object-level verified.
- BTCUSDT 1h Klines beginning 2020-01 are object-level verified.
- The archive checksum detail is CRC64NVME; the earlier SHA-256 wording is incorrect.
- ETHUSDT, DOGEUSDT and SOLUSDT metrics begin at 2021-12-01 in the audited samples.
- The remaining 55 non-sample symbols have not been individually verified.
- Therefore 2020-09-01 cannot be used as a global full-universe cutoff.

## Next gate

The next optional read-only task is a symbol-by-symbol S3 coverage matrix for the current effective universe. Until that verification is complete and the Owner chooses a cutoff policy, do not start a backfill or source switch.
