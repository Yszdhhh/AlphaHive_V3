---
name: neat-freak
description: Project-integrated knowledge and rule hygiene protocol.
source: User-supplied G:\下载\SKILL.md, integrated 2026-07-15.
---

# Knowledge hygiene protocol

Treat project knowledge as a maintained system, not an append-only diary. This protocol applies whenever the user asks to clean up documentation, synchronize knowledge, audit rules, prepare a handoff, or close a milestone.

## Ownership

| Layer | Purpose | Rule |
|---|---|---|
| `AGENTS.md` / `CLAUDE.md` | Agent entrypoint and durable constraints | Keep short; rules and pointers only. |
| Root governance documents | Constitution, Graveyard, approvals, limitations, orchestration | One source of truth per subject; never duplicate governing text. |
| `README.md` and `reports/` | Human onboarding and auditable historical evidence | Explain current use; label historical snapshots clearly. |
| Agent memory / isolated artifacts | Temporary context and provenance | Promote durable facts into project documents; do not make them a hidden authority. |

## Required hygiene workflow

1. Measure and inventory: list Markdown, rules, task instructions, repository status, ignored artifacts, and document sizes.
2. Audit both directions: check that practice follows the rules and that rules still describe current practice.
3. Reconcile facts: update existing authoritative documents rather than adding duplicate narratives. Mark stale reports as historical; never rewrite their evidence.
4. Apply only safe fixes automatically: missing pointers, missing README/index files, explicit approval records, ignored-secret coverage, and dead references whose replacement is certain.
5. Park destructive work: file deletion, renaming, moving historical evidence, or merging conflicting authorities requires Owner approval with impact stated.
6. Verify: links and named paths exist, required files remain readable, the worktree is understood, and no secret/cache artifact was added.

## Anti-bloat rules

- Put reusable operating facts in the appropriate document, not in a running session log.
- Add no history narrative to `AGENTS.md` or `CLAUDE.md`; use Git history or dated reports instead.
- Prefer editing/merging over adding. Every new document needs a distinct audience and owner.
- Use absolute dates, not “today”, “recently”, or “next week”.
- Historical evidence is retained and labelled; it is not silently deleted or retroactively altered.

## Completion checklist

- Required-reading entrypoint names all active authorities exactly once.
- Root README gives a newcomer a safe five-minute orientation.
- Current limitations and Owner-only decisions are distinguishable from completed approvals and historical audits.
- Rules contain no known dead path or unconditional instruction contradicted by active governance.
- Git status, secrets, ignored caches, and large/generated artifacts have been reviewed.
