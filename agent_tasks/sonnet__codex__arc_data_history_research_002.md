# ARC-DATA-HISTORY-RESEARCH-002 - independent public historical-data research

**agent:** Sonnet
**task_id:** ARC-DATA-HISTORY-RESEARCH-002
**tier:** T1 / read-only external research
**output:** `C:\Users\10639\Desktop\AlphaHive_V3_A_DATA_HEALTH_deliverables\agent_outputs\sonnet\ARC-DATA-HISTORY-RESEARCH-002.md`

## Required reading

1. `G:\Quant test\AGENTS.md`
2. `G:\Quant test\AlphaHive_V3\AGENTS.md`
3. `G:\Quant test\AlphaHive_V3\PROJECT_REQUIRED_READING.md`
4. `G:\Quant test\AlphaHive_V3\PROJECT_CONSTITUTION.md`
5. `G:\Quant test\AlphaHive_V3\AGENT_ORCHESTRATION_PROTOCOL.md`
6. `G:\Quant test\AlphaHive_V3\OWNER_APPROVALS.md`
7. `G:\Quant test\AlphaHive_V3\OWNER_DECISIONS_NEEDED.md`
8. This task file

## Objective

Independently research whether official/public Binance sources can provide historical Klines, Open Interest, and taker buy/sell data beyond the current rolling window, and document the implications for AlphaHive historical retention and M-A2 readiness.

## Required checks

1. Compare current CoinGlass date ranges with Binance free-data date ranges.
2. Verify whether official Binance Vision/S3 archives or documented public endpoints cover historical Klines, OI, and taker buy/sell data.
3. Record retention, granularity, symbol coverage, rate limits, reproducibility, licensing, and whether credentials or paid access are required.
4. Identify unavailable older derived ratios and whether that limits model or replay use.
5. Recommend a historical cutoff and safe backfill option, clearly separating verified facts, inference, recommendation, and Owner decisions.

## Hard boundaries

- Read-only research; do not modify repository, database, Parquet files, scheduler, Hermes scripts, or credentials.
- No authenticated API calls, no batch backfill, no live pull, and no CoinGlass login.
- Do not change `data_contracts.yaml`, triggers, thresholds, Paper eligibility, or trading behavior.
- If a fact cannot be verified, mark it `UNVERIFIED`; do not infer from filenames alone.

## Deliverable format

Write only to the specified Desktop output path. The report header must contain `agent=Sonnet`, `task_id=ARC-DATA-HISTORY-RESEARCH-002`, UTC timestamp, exact sources consulted, status (`GREEN`, `UNVERIFIED`, or `PARK`), and unresolved items. Include a source-comparison table and final Owner-decision list.
