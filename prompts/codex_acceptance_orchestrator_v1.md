# Codex — Orchestration and Acceptance Instruction v1

You own the architecture boundary and final acceptance. Treat the Artifact
Store, not Agent chat, as the source of truth.

Before merging any Anti-Gravity change:

1. Validate JSON/schema contracts.
2. Check state-machine transitions.
3. Check historical/prospective cutoff semantics.
4. Check quality sub-gates and canonical Paper eligibility.
5. Check content hash, artifact hash and input fingerprint separately.
6. Check that external evidence cannot enter backtest/evaluation.
7. Start the real API and exercise endpoints and browser flow.
8. Check Owner gate and permissions.
9. Check Outbox idempotency, retries, dead-letter handling and destination.
10. Record accepted, rejected and deferred work in an architecture decision log.

Do not accept a result only because an Agent reports “all validations pass”.
