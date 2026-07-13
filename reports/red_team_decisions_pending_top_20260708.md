# Red-Team Decision Report: Pending Top 20

**Report date:** 2026-07-08
**Reviewer:** Red-Team Decision Reviewer (automated)
**Scope:** 20 pending top candidates from 4 clean replay runs
**Constraint:** No code changes, no config changes, no future-return leakage

---

## 1. Summary

| Metric | Count |
|--------|-------|
| Total reviewed | 20 |
| No Trade | 4 |
| Watch | 10 |
| Paper Trade | 6 |
| Anomalies flagged | 3 |

Anomalies:
- **1000BONKUSDT** (0528): -99.9% abs_move_pct_24h — near-certain data feed error or flash crash
- **1000PEPEUSDT** (0528): -99.9% abs_move_pct_24h — same pattern as 1000BONK, systemic data issue
- **RAVEUSDT** (0414): $4.3B turnover — 100x above typical range ($16-42M), likely data artifact or contract event

All 20 candidates from the 4 clean runs (`20260408_0000_utc_replay`, `20260414_0000_utc_replay`, `20260511_1200_utc_replay`, `20260528_1200_utc_replay`) have been reviewed. No BLOCKED items.

---

## 2. Decision Table

Sorted by run_id, then record_id.

| # | run_id | record_id | scan_time_utc | symbol | rank | turnover_24h_usd | trigger_reason | trigger_quantile | abs_move_pct_24h | excess_move_pct_24h | funding_sign | funding_rate_8h | red_team_decision | confidence | reason_short | required_human_check | veto_flags |
|---|--------|-----------|---------------|--------|------|-------------------|----------------|------------------|------------------|---------------------|--------------|-----------------|-------------------|------------|--------------|----------------------|------------|
| 1 | 20260408_0000_utc_replay | _0008 | 2026-04-08T00:00:00Z | LABUSDT | 31 | 58,913,000 | vol_quantile_high\|large_move_abs\|large_move_excess | 0.945 | 31.45 | 26.98 | positive | 0.000646 | Paper Trade | High | Triple-trigger at 94.5th quantile, +27% excess, strong volume. LAB is mid-cap with consistent liquidity. | Verify 24h/72h return persistence; check if move was news-driven | none |
| 2 | 20260408_0000_utc_replay | _0004 | 2026-04-08T00:00:00Z | BZUSDT | 27 | 501,020,194 | vol_quantile_high\|large_move_abs\|large_move_excess | 1.000 | -13.18 | -17.65 | negative | -0.005 | Watch | Medium | Extreme quantile (1.0) and deep negative excess (-17.6%), but BZ is a low-liquidity symbol with negative funding. Need to confirm this isn't a single-exchange wash. | Cross-exchange volume validation; check if BZUSDT has thin order book | none |
| 3 | 20260408_0000_utc_replay | _0006 | 2026-04-08T00:00:00Z | FARTCOINUSDT | 51 | 76,519,617 | large_move_abs\|large_move_excess | 0.814 | 18.35 | 13.88 | positive | 0.000169 | Watch | Medium | Reasonable excess (+13.9%) but quantile only 81.4th. FARTCOIN is a meme-adjacent token; move could be sentiment-driven rather than fundamental. | Confirm no social media pump event at scan time | none |
| 4 | 20260408_0000_utc_replay | _0011 | 2026-04-08T00:00:00Z | RIVERUSDT | 70 | 177,568,889 | large_move_excess | 0.180 | -9.10 | -13.56 | positive | 5e-05 | Watch | Low | Only excess trigger (no vol_quantile or large_move_abs). Quantile is very low (0.18) — move is statistically unremarkable. Funding nearly zero. | Low priority; needs stronger trigger confirmation | none |
| 5 | 20260408_0000_utc_replay | _0009 | 2026-04-08T00:00:00Z | MONUSDT | 74 | 48,577,084 | vol_quantile_high\|large_move_abs\|large_move_excess | 0.941 | 12.31 | 7.84 | positive | 5e-05 | Watch | Medium | Triple-trigger but modest excess (+7.8%). MON is a smaller-cap name. The move is real but magnitude is average for the trigger set. | Verify if MON has history of false breakouts | none |
| 6 | 20260414_0000_utc_replay | _0008 | 2026-04-14T00:00:00Z | RAVEUSDT | 73 | 4,265,006,981 | vol_quantile_high\|large_move_abs\|large_move_excess | 1.000 | 34.57 | 29.37 | negative | -0.00196 | Watch | Low | **Data anomaly**: $4.3B turnover is ~100x the typical range ($16-42M). Likely caused by contract event, data feed corruption, or exchange maintenance. The excess (+29.4%) and quantile (1.0) may be artifacts of the bad data. Cannot paper trade on unreliable inputs. | Investigate Binance data feed status at 2026-04-14; verify if RAVE had a contract migration | extreme_move |
| 7 | 20260414_0000_utc_replay | _0010 | 2026-04-14T00:00:00Z | SKYAIUSDT | 64 | 27,563,771 | vol_quantile_high\|large_move_abs\|large_move_excess | 0.912 | -10.32 | -15.52 | positive | 0.000279 | Watch | Medium | Triple-trigger with reasonable excess (-15.5%), but SKYAI is a smaller AI-themed token. Funding is positive which adds cost to a short. | Verify AI narrative wasn't fading; check OI change if available | none |
| 8 | 20260414_0000_utc_replay | _0002 | 2026-04-14T00:00:00Z | BZUSDT | 27 | 346,200,395 | large_move_excess | 0.706 | -5.30 | -10.49 | negative | -0.000451 | No Trade | Medium | BZ appears again with thin excess trigger (0.706 quantile). Already flagged in 20260408 run — this is the same symbol showing repeated weakness. The -10.5% excess is borderline. | BZ pattern is concerning but not actionable alone — needs cross-run confirmation | none |
| 9 | 20260414_0000_utc_replay | _0011 | 2026-04-14T00:00:00Z | SNDKUSDT | 46 | 16,985,097 | large_move_abs\|large_move_excess | 0.878 | 15.68 | 10.48 | positive | 9e-08 | No Trade | Low | SNDKUSDT has extremely low funding (9e-08) — essentially zero. Turnover $17M is on the lower end. The move is real but the near-zero funding suggests this pair may have thin derivative interest. | Check if SNDK has adequate OI for directional trades | none |
| 10 | 20260414_0000_utc_replay | _0009 | 2026-04-14T00:00:00Z | RIVERUSDT | 70 | 125,989,984 | large_move_excess | 0.506 | -4.68 | -9.87 | positive | 5e-05 | Watch | Low | RIVER appears in both 20260408 and 20260414 runs. Quantile is 0.506 — median-level. The excess is -9.9% which is real but not extreme. Cross-run presence is notable. | Track RIVER across runs for pattern; low priority single-trade candidate | none |
| 11 | 20260511_1200_utc_replay | _0014 | 2026-05-11T12:00:00Z | SKYAIUSDT | 64 | 104,154,308 | large_move_abs\|large_move_excess | 0.678 | -24.01 | -24.49 | positive | 0.000539 | Paper Trade | High | Large excess (-24.5%) on a well-traded token with $104M turnover. Quantile 0.678 is moderate but the magnitude of excess is significant. SKYAI has appeared in multiple runs. | Verify SKYAIUSDT move wasn't driven by a single large order; check if this is a breakout or breakdown pattern | none |
| 12 | 20260511_1200_utc_replay | _0017 | 2026-05-11T12:00:00Z | VVVUSDT | 38 | 160,927,666 | large_move_abs\|large_move_excess | 0.697 | 17.02 | 16.55 | positive | 0.000142 | Paper Trade | High | Strong excess (+16.5%) on $161M turnover. VVV is a mid-cap token with decent liquidity. Quantile 0.697 is acceptable for the move size. | Confirm move direction aligns with broader market; check VVV sector momentum | none |
| 13 | 20260511_1200_utc_replay | _0016 | 2026-05-11T12:00:00Z | UBUSDT | 18 | 62,652,472 | large_move_abs\|large_move_excess | 0.698 | 12.86 | 12.38 | positive | 5e-05 | Watch | Medium | Reasonable move but UBUSDT is lower-liquidity. The near-zero funding (5e-05) is concerning for directional execution. | Check UBU order book depth at the time of the move | none |
| 14 | 20260511_1200_utc_replay | _0009 | 2026-05-11T12:00:00Z | LABUSDT | 31 | 400,797,434 | large_move_abs\|large_move_excess | 0.697 | -10.53 | -11.01 | positive | 5e-05 | Paper Trade | Medium | LAB appears again with opposite direction (negative excess). $401M turnover confirms move is real. Quantile moderate but magnitude + turnover justify human review. | LAB is a recurring symbol — check if direction flip across runs is structural | none |
| 15 | 20260511_1200_utc_replay | _0015 | 2026-05-11T12:00:00Z | SUIUSDT | 15 | 1,808,112,908 | vol_quantile_high\|large_move_abs\|large_move_excess | 0.999 | 10.74 | 10.27 | positive | 0.0001 | Paper Trade | High | Triple-trigger at 99.9th quantile on $1.8B turnover. SUI is a major L1 with deep liquidity. The move is well-confirmed across multiple dimensions. | Verify SUI ecosystem didn't have a major event; this is a strong candidate | none |
| 16 | 20260528_1200_utc_replay | _0001 | 2026-05-28T12:00:00Z | 1000BONKUSDT | 68 | 22,295,775 | vol_quantile_high\|large_move_abs\|large_move_excess | 0.996 | -99.91 | -96.93 | negative | -0.000125 | No Trade | High | **Extreme outlier**: -99.9% abs_move_pct_24h. This is almost certainly a data anomaly (price going to near-zero or a flash crash). BONK is a meme token with extreme volatility but -99.9% in 24h is unrealistic for a live market. | Investigate if this was a real flash crash or a data feed error; likely data corruption | extreme_move |
| 17 | 20260528_1200_utc_replay | _0002 | 2026-05-28T12:00:00Z | 1000PEPEUSDT | 33 | 158,530,740 | vol_quantile_high\|large_move_abs\|large_move_excess | 0.997 | -99.91 | -96.92 | negative | -0.000128 | No Trade | High | **Same pattern as 1000BONK**: -99.9% move. Two adjacent meme tokens showing near-identical -99.9% moves strongly suggests a systemic data feed issue (e.g., exchange maintenance, price feed corruption) rather than genuine market moves. | Investigate exchange status at 2026-05-28 12:00 UTC; likely NOT actionable | extreme_move |
| 18 | 20260528_1200_utc_replay | _0013 | 2026-05-28T12:00:00Z | XLMUSDT | 48 | 313,615,135 | vol_quantile_high\|large_move_abs\|large_move_excess | 1.000 | 21.09 | 24.08 | negative | -0.000303 | Paper Trade | High | Extreme quantile (1.0) with +24% excess on $314M turnover. XLM is a well-established altcoin. The move is large but well-confirmed. | Verify XLM didn't have a protocol event; negative funding adds cost to a long | none |
| 19 | 20260528_1200_utc_replay | _0012 | 2026-05-28T12:00:00Z | WLDUSDT | 11 | 229,831,757 | vol_quantile_high\|large_move_abs\|large_move_excess | 0.983 | -18.79 | -15.81 | negative | -0.000201 | Watch | Medium | Strong move but WLD (Worldcoin) is associated with high volatility and regulatory uncertainty. Negative funding is a headwind. | Check WLD-specific news; Worldcoin has had erratic price action historically | none |
| 20 | 20260528_1200_utc_replay | _0008 | 2026-05-28T12:00:00Z | RAVEUSDT | 73 | 16,651,187 | large_move_abs\|large_move_excess | 0.760 | -13.83 | -10.85 | positive | 5e-05 | Watch | Medium | RAVE appears again (also in 20260414). Turnover $16.7M is lower than the 20260414 appearance ($4.3B). Quantile 0.76 is moderate. | RAVE cross-run signal is interesting but this specific instance is weaker | none |

---

## 3. Paper Trade Shortlist (6 candidates)

These are the strongest candidates worth human review for Long/Short direction:

| # | symbol | run | excess | quantile | turnover | why |
|---|--------|-----|--------|----------|----------|-----|
| 1 | **SUIUSDT** | 20260511 | +10.3% | 0.999 | $1.8B | Triple-trigger at 99.9th percentile. Deepest liquidity of all candidates. L1 token with real ecosystem. |
| 2 | **LABUSDT** | 20260408 | +27.0% | 0.945 | $59M | Strongest excess in the dataset. Triple-trigger. LAB is a mid-cap with consistent volume. |
| 3 | **XLMUSDT** | 20260528 | +24.1% | 1.000 | $314M | Established altcoin, extreme quantile, high turnover. Move is large and well-confirmed. |
| 4 | **SKYAIUSDT** | 20260511 | -24.5% | 0.678 | $104M | Largest negative excess among watchable candidates. AI-themed token with recurring presence across runs. |
| 5 | **VVVUSDT** | 20260511 | +16.6% | 0.697 | $161M | Solid excess on decent turnover. Quantile is moderate but the move magnitude is significant. |
| 6 | **LABUSDT** | 20260511 | -11.0% | 0.697 | $401M | LAB appears again with opposite direction. High turnover confirms the move is real. Worth investigating the flip. |

---

## 4. Vetoed Candidates (No Trade — 4 candidates)

| # | symbol | run | veto_reason | veto_flags |
|---|--------|-----|-------------|------------|
| 1 | **1000BONKUSDT** | 20260528 | -99.9% 24h move is almost certainly a data feed error or flash crash, not a tradeable signal. Meme token with extreme volatility but this magnitude is unrealistic. | extreme_move |
| 2 | **1000PEPEUSDT** | 20260528 | Same -99.9% pattern as 1000BONKUSDT. Two adjacent meme tokens with near-identical catastrophic moves strongly suggests systemic data corruption. | extreme_move |
| 3 | **BZUSDT** | 20260414 | BZ appears twice with thin excess triggers (0.706 quantile). Low-liquidity symbol with negative funding. Not enough conviction for a paper trade. | none |
| 4 | **SNDKUSDT** | 20260414 | Near-zero funding (9e-08) suggests thin derivative interest. Low turnover ($17M) and borderline move. Not suitable for directional paper trading. | none |

---

## 5. Open Questions

1. **1000BONK/1000PEPE data integrity**: Were the -99.9% moves on 2026-05-28 real flash crashes or data feed errors? If real, should these symbols be quarantined from future scans?

2. **RAVEUSDT $4.3B turnover on 2026-04-14**: Is this genuine market activity or a data pipeline error? The symbol typically trades $16-42M. A 100x spike warrants investigation before this candidate can be reconsidered.

3. **BZUSDT repeated weakness**: BZ appears in both 20260408 and 20260414 runs with negative excess. Is this a persistent downtrend or a data artifact? Worth monitoring but not trading alone.

4. **LABUSDT direction flip**: LAB appears in 20260408 (+27%) and 20260511 (-11%). Same symbol, opposite directions. This is normal for different time periods but should be noted when reviewing.

5. **Near-zero funding across many candidates**: Several candidates have funding near zero (5e-05). Does this indicate thin derivative markets for these symbols? Should funding be a hard filter for paper trades?

6. **SUIUSDT standing out**: SUI has the strongest overall profile (triple-trigger, 99.9th quantile, $1.8B turnover). Is this a high-priority paper trade? The human should focus review time here first.
