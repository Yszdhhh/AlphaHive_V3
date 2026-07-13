# AlphaHive Research Orchestration Decision

Date: 2026-07-12
Status: IMPLEMENTATION_BASELINE_ACCEPTED_RESEARCHJOB_MVP_001A_READY

## Decision

AlphaHive will use one central Research Orchestrator, immutable task envelopes,
structured artifacts, deterministic validators, and an explicit Owner gate.
It will not use an unconstrained Agent swarm or direct Agent-to-Agent chat
transmission as the system of record.

Development Agents and runtime research Agents are separate populations.

## Development Agents

- Codex: architecture, contracts, final acceptance and merge decisions.
- Anti-Gravity with Gemini 3.1 Pro High: primary mainline code executor.
- Mimo: bounded infrastructure work, evidence normalization, validators and fixtures.
- Grok: inactive as a provider; its accepted output remains a frozen fixture.
- DeepSeek: inactive for the current phase.

## Runtime Research Agents

- ThemeScout: ThemeDiscoveryReport and QuantCheckRequest only.
- CandidateEvidenceCollector: ExternalResearchEvidence only.
- EvidenceVerifier: source, duplication, cutoff and prompt-injection checks.
- ResearchSynthesizer: ResearchAssessment from a frozen package and verified evidence.
- PaperPlan Engine: deterministic code, not an Agent.
- Notification Worker: deterministic outbox consumer, not an Agent.

## Mandatory execution order

```text
SCANNED
 -> PACKAGE_READY
 -> RESEARCH_JOB_CREATED
 -> EVIDENCE_REQUESTED
 -> EVIDENCE_COLLECTED
 -> EVIDENCE_VERIFIED
 -> RESEARCH_ASSESSMENT_READY
 -> OWNER_REVIEW
 -> REJECTED | WATCHLISTED | PAPER_APPROVED
```

Exceptional states are retained separately: BLOCKED, VALIDATION_FAILED,
PROVIDER_FAILED, CUTOFF_VIOLATION and OWNER_ACTION_REQUIRED.

## What is deterministic

The following must remain code and must not be delegated to an LLM:

- snapshot cutoff and future-data filtering;
- run status and hash validation;
- quality sub-gates and Paper eligibility;
- risk preset calculations;
- PaperPlan generation;
- notification idempotency and retries;
- permission checks and Owner approval;
- state transitions.

## What may use an LLM

- discovering external themes;
- collecting public-source evidence;
- comparing conflicting claims;
- synthesizing verified evidence;
- red-teaming prompts and evidence packages.

## Completed implementation gate

The P0 contract baseline and provider-neutral evidence envelope have passed
independent acceptance. The real latest candidate correctly fails closed on
missing contract identity. Automatic Provider calls remain disabled.

## Next implementation gate

Implement `RESEARCHJOB-MVP-001A` only: a file-backed ResearchJob store,
server-generated job IDs, frozen candidate package, append-only hash-linked
events, atomic persistence and Create/Get API. Evidence import, Owner decisions,
PaperPlan and notifications are separate subsequent gates. Do not add automatic
LLM calls, live orders or Agent-to-Agent state transitions during this gate.

## Owner decisions still required

- approve the contract version;
- approve Paper eligibility rules;
- approve risk preset version and common discipline;
- approve which Provider may run in production;
- approve the final Paper decision workflow.
