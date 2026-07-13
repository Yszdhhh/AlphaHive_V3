# AlphaHive External Project Overview

## One-sentence definition

AlphaHive is an **explainable crypto anomaly-research and paper-execution
discipline system**: it helps the owner discover unusual market conditions,
organize external research, make an accountable decision, and later track a
paper plan. It is not an autonomous trading bot.

## Intended owner experience

1. A local scanner finds a small number of abnormal crypto candidates.
2. A web cockpit explains *why* each candidate was selected, what data is
   missing, and whether it is research-only or eligible for a later paper plan.
3. The owner copies a structured deep-research prompt to a cloud AI or research
   provider.
4. Returned research is brought back as external evidence, checked for source,
   time cutoff, duplication and provenance.
5. The owner—not an agent—decides whether to reject, watch, or approve a
   paper-only plan, with hypothesis, invalidation, horizon and risk preset.
6. The system preserves an audit trail and later sends only actionable alerts
   to a dashboard and Feishu/Hermes outbox.

## Design principles

- **Human authority:** no agent can sign an Owner decision or place a real
  trade.
- **Fail closed:** missing identity, integrity or required market context blocks
  Paper capability; missing values never silently become zero.
- **Research may continue under uncertainty:** a quality BLOCK can still be
  researched, but cannot create a Paper Plan.
- **Provider neutrality:** Grok, Gemini, Claude or future services are manual
  research executors that emit the same JSON artifact shape. No provider is a
  permanent dependency.
- **Immutable evidence:** external material remains
  `UNVERIFIED_EXTERNAL_EVIDENCE` until independently verified; it cannot write
  to quality gates, decisions or plans.
- **Reproducibility:** scanning inputs, prompt packages, evidence, assessments,
  decisions and plans must be versioned and hash-linked.

## Architecture blueprint

```text
[Market / derivatives scanner]
             |
             v
[Deterministic quality gates]
             |
             v
[Signal Review API + Web cockpit]
             |
             v
[Deep-research prompt package]
             |
             v
[Manual external research providers]
             |
             v
[ResearchJob: immutable evidence and workflow ledger]
             |
             v
[Verification + research assessment]
             |
             v
[Owner decision]
             |
             v
[Deterministic Paper Plan] --> [Notification outbox / Feishu]
```

## Module map and maturity

| Module | Purpose | Current maturity |
|---|---|---|
| Market scanner | Detect unusual price/volume/derivatives conditions | Available |
| Quality gates | Integrity, identity, history, derivatives, liquidity, Paper eligibility | Available; fail-closed |
| Signal Review dashboard | Candidate queue, trigger explanation, market snapshot, prompt copy, Paper UI shell | Available |
| Signal Review API/exporter | Serve current reviewed candidates to dashboard | Available |
| Deep-research prompt package | Direction-neutral research brief with cutoff, factors, missing data and prohibitions | Available |
| External evidence contract | Normalize external outputs, retain provenance/cutoff/hash, flag unverified status | Available as contract/fixture baseline |
| ResearchJob workflow store | Frozen candidate snapshot, event history, evidence/decision versioning | In construction; not yet accepted |
| Evidence import & quarantine | Safely import and reject malformed/late/mismatched evidence | Planned |
| Verification & assessment | Separate evidence verification from qualitative synthesis | Planned |
| Owner decision ledger | Bind decision to exact package/evidence/assessment/risk versions | Planned |
| Paper Plan engine | Produce paper-only plan under deterministic risk discipline | Planned |
| Feishu/Hermes outbox | Notify only on actionable state changes | Planned |
| Live trading | Autonomous or exchange execution | Explicitly out of scope |

## Current reality and key gap

The system already solves **signal discovery, explanation and external research
prompting**. The main missing capability is not another AI model or another
factor: it is a trustworthy workflow layer that makes research, evidence,
owner decisions and paper discipline durable, versioned and auditable.

## Development roadmap

1. **ResearchJob foundation:** freeze a candidate into a durable research task.
2. **Evidence import:** accept or reject manual external research without
   letting bad imports poison a task.
3. **Verification and assessment:** distinguish raw claims from verified
   evidence and direction-neutral analysis.
4. **Owner decision:** require explicit human confirmation and bind it to exact
   upstream versions.
5. **Paper Plan:** generate only after valid owner approval and required data
   eligibility.
6. **Outbox and cockpit integration:** surface state changes in Web and Feishu.

## Questions for an external architecture review

1. Is this separation between deterministic screening, external evidence,
   human decision and paper execution appropriate?
2. Which module boundaries should be strengthened before building evidence
   import and Owner decision flows?
3. Does the staged roadmap avoid premature automation and provider lock-in?
4. What are the highest-risk failure modes for a file-backed, auditable
   workflow before it grows into a larger system?
5. Which product capability would create the most value next without weakening
   safety or traceability?
