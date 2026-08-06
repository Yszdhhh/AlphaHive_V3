# OWNER_APPROVALS

8. **2026-07-17 — Hermes repair verified.** Gemini's independent read-only
   `HERMES-POSTFIX-VERIFY-001-GEMINI` receipt is accepted `RECOVERED`: all four
   engines refreshed 59/59 symbols with zero final failures. This closes the
   transport advisory only and grants no trigger, Paper, source, credential or
   trading authority.

6. **2026-07-17 — Deep-research contract governance freeze.** The Owner approved
   freezing `config/deep_research_contract.yaml` as `contract_version: v1.0.0`,
   `status: FROZEN_V1`. This is a documentation and governance freeze only. It
   does not authorize provider automation, new data sources or credentials,
   trigger ignition, Paper `ALLOW`, notification delivery, or trading.

7. **2026-07-17 — Hermes repair claim.** The Owner reports that Hermes has been
   repaired. This records the claim only; runtime health remains subject to a
   read-only post-fix verification receipt before `PARTIAL /
   TRANSIENT_TRANSPORT_FAILURE` is closed.

5. **2026-07-16 — ARC-NEXT bounded foundation work.** The Owner approved Codex to execute and integrate N1–N5 within the T1/T2 boundary: additive canonical logical views, read-only overlap reconciliation, a fail-closed bounded `liquidity_gate`, checkpoint pruning from 73 to the 59-symbol effective universe, and a versioned data-contract update. This approval does **not** authorize a scanner source-path switch, S3 gap-fill, trigger ignition, `paper_eligibility=ALLOW`, credential/proxy changes, order-book collection, or any trading action. External agents may provide isolated read-only evidence or candidate artifacts; only Codex may write `AlphaHive_V3/`.

4. **2026-07-15 - candidate-universe expansion and bounded history backfill.** The Owner approved expanding the configured rank-10-80 candidate list from the partial 39-entry snapshot to the liquidity-qualified 66-entry local source range, retaining inactive symbols for historical identity but disabling them for live pulls; BTC/ETH/SOL remain reference-only benchmarks. The approved data operation includes public Binance klines backfill to the 90-day minimum, with no synthetic OI/Taker history and no Paper/trading permission change.

This is the narrow, dated record of Owner-granted exceptions. It is not a source of new authority; anything absent here remains governed by the Constitution and `OWNER_DECISIONS_NEEDED.md`.

9. **2026-07-18 — canonical price-source precedence and OHLCV publication
   boundary.** The Owner declared Binance public data the factual/current price
   source and CoinGlass the historical source. When the same price-dimension
   bar exists in both sources, Binance takes precedence and the conflict must
   remain auditable. A canonical OHLCV snapshot may be prepared when funding
   or OI are absent or stale, provided those dimensions are explicitly marked
   unavailable and cannot activate a derivative trigger, Paper eligibility or
   trading behavior. This approval does **not** yet authorize changing the
   active scanner path, silently filling a gap, historical backfill, trigger
   ignition, Paper `ALLOW`, credentials, notification delivery or trading.

10. **2026-07-18 — bounded canonical-price scanner activation.** The Owner
    confirmed the proposed price-gap policy: do not interpolate; block a
    symbol on any missing bar in its latest 48 completed hours; outside that
    guard, allow at most four bars per gap and at most six missing bars in the
    latest 90 days with `HISTORICAL_GAP_WARNING`; make a metric unavailable
    when its input window crosses a gap; otherwise block the symbol. The Owner
    also explicitly authorized the active scanner to consume a validated,
    immutable canonical **price** snapshot in place of the current CoinGlass
    kline path. This is limited to the effective live universe and must retain
    source provenance, conflict and gap evidence. It does not authorize
    backfill, a derivative-source change, trigger ignition, Paper `ALLOW`,
    notification delivery, credentials, or trading.

11. **2026-07-18 — OwnerDecision authentication mechanism.** The Owner
    selected `interactive_owner_confirmation_in_Codex`: an explicit affirmative
    reply from the Owner in this conversation is the required authentication
    context for a future bound OwnerDecision. The implementation must retain
    the stable non-secret Owner label and immutable hash bindings. This records
    a governance mechanism only; it is not an approval of any job, direction,
    PaperPlan, trigger, notification, or trading action.

12. **2026-07-18 — MVP003 OwnerDecision governance rules.** The Owner confirmed
    the fixed `owner_decision_confirmation_v1` text in
    `reports/OWNER_DECISION_CONFIRMATION_TEMPLATE_20260718.md` and the
    `immutable_exact_file_hash` preset-binding rule. Codex may implement the
    immutable, hash-bound OwnerDecision persistence and validation slice only.
    A future actual decision still requires the Owner's explicit affirmative
    reply for that exact bound job. This does not approve a job, direction,
    PaperPlan, trigger, notification, credential, source change, or trading.

13. **2026-07-18 — Paper-only preset freeze.** The Owner explicitly approved
    `config/paper_execution_presets.yaml` as `preset_version: v0.1.0`,
    `status: APPROVED`, scope `PAPER_ONLY`, bound to canonical SHA-256
    `a81ad47bbb332ef26d2399c7fae1e58ce1232534406f8b140f9654dd16edb958`.
    This authorization is limited to that configuration promotion. It does not
    authorize a PaperPlan, Paper execution, trigger ignition, delivery,
    notification, data/source/credential change, or live trading; it has no
    retrospective effect on a historical or BLOCK job.

1. **2026-07-14 — governance equivalence.** `AGENT_ORCHESTRATION_PROTOCOL.md` v1 is the sole governance-file equivalent of the Charter's referenced `AGENT_ORCHESTRATION_PROTOCOL_v2.md` for this Autonomous Arc batch. Non-T3 M-B3, M-A1, and M-C1 work may proceed under its existing red lines; every T3 item still requires separate Owner approval.
2. **2026-07-15 — Binance public-data operations.** The local Hermes Binance puller may use the public USD-M Futures API without credentials, maintain its existing hourly schedule, write its local `binance_free_db`, and apply conservative reliability controls. This approval excludes CoinGlass, API keys, credentials, proxy changes, trigger changes, paper permission, and any trading action.
3. **2026-07-15 — private Git synchronization.** The Owner approved synchronization to the private `Yszdhhh/AlphaHive_V3` repository. A push still requires explicit Owner approval; no token, key, or credential may be committed or exposed.
