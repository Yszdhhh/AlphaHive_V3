# parallel_grok_unlockdex - Token Unlock Calendar x CEX-DEX Arb Data Recon

- Agent: GrokUnlockDex (market-researcher)
- Date: 2026-08-08
- Scope: data availability recon only; no backtest / trade advice
- Verification: dual-provider search (xAI web + Gemini grounding) + official docs + live HTTP probes
- Context: listing calendar already exists (Binance exchangeInfo onboardDate / s009)

---

## 0. Executive summary (what to run first)

| Goal | Free-first path | Grade | Why |
|---|---|---|---|
| Daily unlock events x wash_cvd | Mobula Free/Demo metadata release_schedule; Tokenomist Free Trial for institutional fields | A- (Mobula) / A (Tokenomist trial) | Mobula demo returns date/amount/allocation live; Tokenomist has valueToMarketCap + cliff/linear via daily-emission but API is not free forever |
| Hourly CEX-DEX basis scan | Binance REST/WS bookTicker + Uniswap v3 pool slot0 via free public RPC | A | Hosted Graph dead; hourly scan does not need subgraph |

Do NOT expect free unlock APIs from:
- DefiLlama emissions: Pro-only (live HTTP 402)
- CoinGecko / CoinMarketCap: no free unlock-calendar endpoint (web UI only / partial supply fields)
- Hosted Graph URL api.thegraph.com/subgraphs/name/uniswap/uniswap-v3: live 301 deprecated

---

## 1. Token unlock calendar

### 1.1 Tokenomist / TokenUnlocks (token.unlocks.app -> tokenomist.ai)

Confirmed (official docs + live):

| Item | Detail | Source / time |
|---|---|---|
| Brand | TokenUnlocks migrated / equivalent to Tokenomist | tokenomist.ai/pricing, docs 2026-08-08 |
| Base URL | https://api.tokenomist.ai | docs.tokenomist.ai |
| Auth | Header x-api-key; no key -> 401 | live GET /v5/token/list 401 |
| Forever-free API | NO. Free web plan has no API | pricing Free  no API |
| Free Trial API | Yes, form request | docs.google.com form linked on pricing |
| Paid | Pro 9/mo: 300 calls/mo, unlock hist/future ~1y each; Standard API 49.95/mo: 50k calls, +/-2y; Elite 49.95/mo: 500k calls, +/-3y | tokenomist.ai/pricing |
| Quota | successful requests consume credit; 429; metadata.credit used/limit/resetAt | docs rate-limits |
| OpenAPI | https://docs.tokenomist.ai/openapi.yaml | docs |
| Docs index | https://docs.tokenomist.ai/llms.txt | docs |

Key endpoints (v5, key required):
- GET /v5/token/list - tokenId directory
- GET /v5/unlock/events/upcoming - cross-token upcoming calendar (best daily pull)
- GET /v5/unlock/events/{tokenId} - per-token cliff history
- GET /v5/daily-emission/{tokenId} - daily emission series (linear unlocks)

Fields that matter: unlockDate, cliffAmount, cliffValue, valueToMarketCap, allocationBreakdown, unlockPrecision, committedClaim.

Methodology cliff vs linear: https://docs.tokenomist.ai/methodology/cliff-and-linear-emission
Unlock Events skew cliff; linear covered by Daily Emission.

Completeness grade: A quality / C long-term free availability.

Trial form: https://docs.google.com/forms/d/e/1FAIpQLSebUG7Dq2mffAxoUfxbpSaN-GwUSB4vxmWA1PEobJlzcVesuw/viewform

### 1.2 Free / freemium alternatives

#### A. Mobula (LIVE free path)
| Item | Detail |
|---|---|
| Demo no key | https://demo-api.mobula.io/api/1/metadata?asset={Name} -> 200 |
| Prod | https://api.mobula.io/api/... needs key; no key live 429 |
| Free tier | 10,000 credits/mo, 1 RPS (docs.mobula.io/pricing) |
| Unlock fields | release_schedule[]: unlock_date(ms), tokens_to_unlock, allocation_details{}; also distribution[], circulating_supply, market_cap |
| Batch | GET /api/1/multi-metadata?assets=A,B,C (demo 200) |
| Docs | https://docs.mobula.io/rest-api-reference/endpoint/metadata |
| Live sample 2026-08-08 | Arbitrum: 38 schedule rows; can compute tokens/circ; LayerZero empty array (coverage uneven) |

Gaps vs Tokenomist: no standardized valueToMarketCap, no single upcoming cross-token EP, no explicit cliff/linear tag.
Grade: A- (free daily runnable)

#### B. DefiLlama Unlocks
| Item | Detail |
|---|---|
| Web | https://defillama.com/unlocks |
| Free API | NO emissions. live https://api.llama.fi/emissions -> 402 |
| Pro | GET https://pro-api.llama.fi/{KEY}/api/emissions ; /api/emission/{protocol} |
| Pro price | docs say 00/mo (api-docs.defillama.com) |
| Fields (docs) | token, circSupply, maxSupply, events, nextEvent, unlocksPerDay, mcap, gecko_id |

Grade: B+ data / F free API

#### C. CoinGecko
Web unlocks UI: https://www.coingecko.com/en/highlights/incoming-token-unlocks (Tokenomist-powered)
Free/Demo API: no unlock calendar endpoint
Paid-ish related: /coins/{id}/supply_breakdown (Analyst+) snapshot only
Grade: D API / B web

#### D. CoinMarketCap
Web: https://coinmarketcap.com/token-unlocks/
Free Basic API: no documented unlocks calendar endpoint
Maybe unlocked_circulating_supply style current fields only
Grade: D API / B web

#### E. Cryptorank
Web: https://cryptorank.io/token-unlock (200 HTML)
API claims upcoming-token-unlocks / vesting; live no key 401
Sandbox free tier advertised; full unlocks often Pro
Grade: C (needs key verification)

#### F. Dune
No official standardized unlock dataset; community queries
Free API ~2500 credits/mo (search claim; verify on account)
Use for on-chain vesting/claim custom, not market-wide calendar first path
Grade: C

#### G. Binance announcements
Unstructured; good for cross-check. Listings use exchangeInfo onboardDate (s009); unlocks not there.
Grade: D primary / B cross-check

#### H. Other
Apify foxlabs/token-unlocks-calendar (scrape DefiLlama): free tier but scraping/ToS risk -> C
Messari Token Unlocks: paid institutional, skip

### 1.3 Unlock source matrix

| Source | Free quota | History depth | Access | Date | Amount | circ/mcap | cliff vs linear | Grade |
|---|---|---|---|---|---|---|---|---|
| Mobula Free/Demo | 10k cr/mo, 1 RPS | per-token schedule | REST metadata | Y | Y | self circ% | weak | A- |
| Tokenomist Free Trial | form trial; not forever | trial often ~1y (search) | REST+key | Y | Y | valueToMarketCap | cliff+daily emission | A |
| Tokenomist Pro 9 | 300 calls/mo | API +/-1y | REST | Y | Y | Y | Y | B+ |
| Tokenomist Standard 50 | 50k calls/mo | +/-2y | REST | Y | Y | Y | Y | A |
| DefiLlama Pro 00 | Pro key | events/nextEvent | REST Pro | Y | Y | mcap | events | B |
| DefiLlama Free API | emissions 402 | - | - | web | - | - | - | F |
| CoinGecko Free API | no unlock EP | - | - | web | - | - | - | D |
| CMC Free API | no unlock EP | - | - | web | - | unlocked snapshot | - | D |
| Cryptorank Sandbox | low credit | unverified | REST+key | claimed | claimed | claimed | claimed | C |
| Dune Free | ~2.5k credits | custom | SQL->API | custom | custom | custom | on-chain | C |

Fullest: Tokenomist. Best free to start: Mobula.

### 1.4 Recommended path - daily unlock x wash_cvd

Phase 0 () Mobula:
GET https://demo-api.mobula.io/api/1/metadata?asset=Arbitrum
After free key: GET https://api.mobula.io/api/1/metadata?asset=Arbitrum
Batch: multi-metadata?assets=...

Pipeline:
1. watchlist = wash_cvd symbols intersect non-empty release_schedule
2. daily pull once -> expand schedule -> unlock_date in [T-1d, T+30d]
3. features: unlock_tokens, unlock/circ_supply, allocation_names, days_to_unlock
4. join wash_cvd on symbol+date (+/-1d or +/-3d window)
5. budget: 100 tokens x 1/day ~ 3k/mo << 10k

Phase 1 Tokenomist trial/Pro:
GET https://api.tokenomist.ai/v5/unlock/events/upcoming?start=YYYY-MM-DD&end=YYYY-MM-DD&page=1&pageSize=100
Header: x-api-key: YOUR_KEY
GET /v5/daily-emission/{tokenId}
GET /v5/unlock/events/{tokenId}
Prefer upcoming once; emission for linear. Cross-check large cliffs vs project docs / Binance announcements.

---

## 2. CEX-DEX on-chain arb data paths

### 2.1 Arb types (recon definition)

| Type | Definition | Data need |
|---|---|---|
| 1. CEX vs DEX same asset | Binance mid/bid/ask vs Uniswap v3 pool price | CEX book + DEX pool price/depth |
| 2. DEX triangle | multi-pool cycle on same chain | multi slot0 or quoter; optional subgraph pool list |

Recon only evaluates data path + free frequency, not tradable alpha.

### 2.2 CEX: Binance (confirmed)

| Item | Detail | Verify |
|---|---|---|
| Top of book | GET https://api.binance.com/api/v3/ticker/bookTicker?symbol=ETHUSDT | live 200 |
| All symbols book | GET .../ticker/bookTicker (no symbol) | live 200 ~424KB |
| Last price | GET .../ticker/price?symbol=ETHUSDT | live 200 |
| Weight limit | REQUEST_WEIGHT 6000/min/IP | exchangeInfo live |
| Free | public REST/WS, no key | confirmed |
| Stream | wss://stream.binance.com:9443/ws/<symbol>@bookTicker | docs |

Hourly: REST once/hour fine. Seconds: use WebSocket, do not poll REST hard.

Docs: https://developers.binance.com/docs/binance-spot-api-docs/rest-api/market-data-endpoints

### 2.3 DEX: Uniswap v3 price

#### 2.3.1 Hosted Graph - DEAD
POST https://api.thegraph.com/subgraphs/name/uniswap/uniswap-v3 -> live 301 to error.thegraph.com
Uniswap docs: Hosted deprecated; use decentralized network.
https://developers.uniswap.org/docs/ecosystem/subgraphs/overview

#### 2.3.2 The Graph Network
Mainnet v3 id: 5zvR82QoaXYFyDEKLZ9t6v9adgnptxYpKpSbxtgVENFV
Endpoint form: https://gateway.thegraph.com/api/<API_KEY>/subgraphs/id/5zvR82QoaXYFyDEKLZ9t6v9adgnptxYpKpSbxtgVENFV
No key live: auth error missing authorization header
Free tier: Studio ~100k queries/mo free (needs API key)
Studio: https://thegraph.com/studio/apikeys/
Best for pool discovery / historical swaps, not lowest-latency trade price

#### 2.3.3 Goldsky
Starter Free: 2250 worker-hours (~3 always-on), 100k entities, 20 req/10s (goldsky.com/pricing)
Prefer self-deploy official v3-subgraph; community EP schemas can differ
Code: https://github.com/Uniswap/v3-subgraph

#### 2.3.4 Direct on-chain slot0 (hourly preferred, LIVE verified)
selector 0x3850c7bd -> sqrtPriceX96, tick
Example pool USDC/WETH 0.05%: 0x88e6A0c2dDD26FEEb64F039a2c41296FcB3f5640

Free RPCs OK (live 200): ethereum.publicnode.com, 1rpc.io/eth, rpc.mevblocker.io, eth.drpc.org, ethereum-rpc.publicnode.com

Decode sample 2026-08-08: tick=200748, approx USDC/ETH ~1914.39; Binance ETHUSDT mid ~1916.01; gross basis ~0.08% (not fee-adjusted, not hard time-synced; proves pipeline)

price=(sqrtPriceX96/2^96)^2 then decimals adjust.
mid scan: slot0 enough; executable size: QuoterV2 eth_call heavier.
Pool universe: whitelist / occasional Graph top-TVL / Factory.getPool

### 2.4 Granularity / frequency vs free quotas

| Freq | CEX | DEX | Free OK? | Notes |
|---|---|---|---|---|
| Daily | REST 1x | slot0 1x | Y | research |
| Hourly (target) | REST or WS | slot0 per pool hourly | Y recommended | 20 pools x 24 x 30 ~14k eth_call/mo; multi-RPC rotate |
| Minute | WS | slot0/min | partial; public RPC rate limits | free registered RPC keys help |
| Second book | must WS | per-second slot0 unrealistic | N steady free | not needed for hourly research |

Answer: hourly CEX-DEX does NOT need second-level books; minute-hour mids enough. Free path = Binance public + multi public RPC slot0.

### 2.5 Cost items (execution layer)

| Cost | Rough | Meaning |
|---|---|---|
| CEX fee | ~0.02-0.1% | x2 if both sides |
| DEX fee | 0.01/0.05/0.3/1% | pool fee |
| Gas | L1 high / L2 low | plus deposit/withdraw |
| Slippage | size-dependent | Quoter/depth |
| Transfer latency | minutes-hours | kills many second-level edges |
| Bridge | if cross-chain | fee+risk |

Research first: signal-layer basis series; do not assume frictionless fills.

### 2.6 Type x source matrix

| Arb type | Source | Latency/freq | Costs | Feasibility |
|---|---|---|---|---|
| 1 CEX-DEX mid | Binance bookTicker + v3 slot0 public RPC | hourly; can go minute | data ~0; exec gas/fee/slip | A |
| 1 executable quote | depth/WS + QuoterV2 | minute | heavier RPC | B+ |
| 1 multi-alt cross-section | all bookTicker + multi pool slot0 | hourly | RPC scales with pools | A- |
| 2 DEX triangle | 3+ slot0/quoter | hour/min | path gas | B research / C free second exec |
| 2 subgraph history | Graph 100k free / Goldsky free | not real-time | query quota | B |
| Hosted Graph old URL | api.thegraph.com/.../uniswap-v3 | - | - | F dead |

### 2.7 Recommended hourly CEX-DEX path

1. CEX hourly: GET https://api.binance.com/api/v3/ticker/bookTicker?symbol=ETHUSDT (or all / WS)
2. DEX hourly: eth_call slot0 on whitelist pools; RPC failover publicnode/1rpc/drpc/mevblocker
3. Align: ts_cex, ts_dex, mid_cex, mid_dex, basis_bps=1e4*(dex-cex)/cex
4. Store hourly parquet/csv
5. Optional: Graph free key weekly top pools; add L2 pools
6. Seconds only later with WS + paid RPC (not P0)

---

## 3. Priority

### P0 this week ()
| Module | Action |
|---|---|
| Unlock | Mobula free key + daily metadata -> unlock_events_daily |
| Basis | Binance bookTicker hourly + Uniswap v3 slot0 hourly -> cex_dex_basis_1h |
| Join | unlock day x wash_cvd; basis separate monitor |

### P1 quality
Unlock: Tokenomist Free Trial; upcoming + valueToMarketCap
Basis: Graph free key pool universe; L2

### P2 paid only if P0 signals worth it
Tokenomist Standard / DefiLlama Pro / paid RPC - do not pre-buy in recon

---

## 4. Live probe log (2026-08-08)

| URL | HTTP | Note |
|---|---|---|
| api.tokenomist.ai/v5/token/list | 401 | needs x-api-key |
| api.tokenomist.ai/v5/unlock/events/upcoming | 401 | needs key |
| api.llama.fi/emissions | 402 | Pro-only |
| api.llama.fi/emission/protocols | 402 | Pro-only |
| coins.llama.fi/prices/current/coingecko:ethereum | 200 | free price OK |
| demo-api.mobula.io/api/1/metadata?asset=Arbitrum | 200 | has release_schedule |
| api.mobula.io/api/1/metadata?asset=Ethereum | 429 | needs key |
| api.binance.com/api/v3/ticker/bookTicker?symbol=ETHUSDT | 200 | bid/ask OK |
| api.binance.com/api/v3/exchangeInfo rateLimits | 200 | weight 6000/min |
| api.thegraph.com/subgraphs/name/uniswap/uniswap-v3 | 301 | Hosted dead |
| gateway.thegraph.com/api/subgraphs/id/5zvR... | 200 auth error | needs API key |
| ethereum.publicnode.com eth_call slot0 | 200 | price decodable |

---

## 5. Fact vs unverified

### Confirmed facts
- Tokenomist API requires key; free web has no API; Pro starts 300 calls/mo (docs+pricing+401 live)
- DefiLlama emissions free API 402 Pro-only (api-docs + live)
- Mobula demo returns usable release_schedule (live JSON)
- Uniswap hosted subgraph deprecated (docs + 301 live)
- Binance bookTicker free; IP weight 6000/min (exchangeInfo live)
- Multiple public RPCs can eth_call Uniswap v3 slot0 (live)

### Unverified
- Tokenomist Free Trial exact credits/days (email after form; search claims 50 tokens/1y etc.)
- Cryptorank Sandbox full unlocks inclusion (401 without key)
- Graph/Goldsky overage exact prices (billing page)
- Dune free 2500 credits (account Subscription page)
- Mobula prod auth header name (admin)
- Public RPC has no SLA

---

## 6. Real URL quick index

Unlock:
- https://docs.tokenomist.ai/
- https://tokenomist.ai/pricing
- https://docs.google.com/forms/d/e/1FAIpQLSebUG7Dq2mffAxoUfxbpSaN-GwUSB4vxmWA1PEobJlzcVesuw/viewform
- https://api.tokenomist.ai
- https://docs.mobula.io/rest-api-reference/endpoint/metadata
- https://docs.mobula.io/pricing
- https://demo-api.mobula.io/api/1/metadata?asset=Arbitrum
- https://api-docs.defillama.com/
- https://defillama.com/unlocks
- https://www.coingecko.com/en/highlights/incoming-token-unlocks
- https://coinmarketcap.com/token-unlocks/
- https://cryptorank.io/token-unlock

CEX-DEX:
- https://api.binance.com/api/v3/ticker/bookTicker?symbol=ETHUSDT
- https://developers.uniswap.org/docs/ecosystem/subgraphs/overview
- https://thegraph.com/studio/apikeys/
- subgraph id 5zvR82QoaXYFyDEKLZ9t6v9adgnptxYpKpSbxtgVENFV
- https://goldsky.com/pricing
- https://github.com/Uniswap/v3-subgraph
- pool 0x88e6A0c2dDD26FEEb64F039a2c41296FcB3f5640
- RPC https://ethereum.publicnode.com

---

## 7. One-line conclusions

- Daily unlock x wash_cvd: start with Mobula free metadata.release_schedule daily event table; parallel apply Tokenomist trial for %mcap and cliff/linear quality. Do not wait for DefiLlama/CG/CMC free unlock APIs - Pro-only or nonexistent.
- Hourly CEX-DEX basis: Binance bookTicker + Uniswap v3 slot0(public RPC). Do not depend on dead hosted Graph. Hourly is fully free; seconds need paid RPC/WS production stack.
