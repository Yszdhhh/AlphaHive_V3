# AlphaHive V3 required reading

Every agent must complete this reading before inspecting code, selecting work, writing an artifact, or changing the repository. Read the task-specific instruction only **after** the shared material.

1. [`AGENTS.md`](AGENTS.md) — this entrypoint.
2. [`PROJECT_CONSTITUTION.md`](PROJECT_CONSTITUTION.md) — system purpose and non-negotiable safety boundaries.
3. [`GRAVEYARD.md`](GRAVEYARD.md) — directions that must not be revived without new auditable evidence and an Owner decision.
4. [`AGENT_ORCHESTRATION_PROTOCOL.md`](AGENT_ORCHESTRATION_PROTOCOL.md) — writers, reviewers, tiers, packaging, and approval boundaries.
5. [`KARPATHY_GUIDELINES.md`](KARPATHY_GUIDELINES.md) — think first, minimum scope, surgical changes, and verifiable completion.
6. [`NEAT_FREAK_SKILL.md`](NEAT_FREAK_SKILL.md) — knowledge hygiene, documentation ownership, and rule-audit workflow.
7. [`KNOWN_LIMITATIONS.md`](KNOWN_LIMITATIONS.md) and [`OWNER_DECISIONS_NEEDED.md`](OWNER_DECISIONS_NEEDED.md) — current evidence gaps and unresolved Owner-only decisions.
8. [`OWNER_APPROVALS.md`](OWNER_APPROVALS.md) — only after the preceding boundaries, to identify narrowly granted exceptions.

For external/isolated agents, then read [`agent_tasks/README.md`](agent_tasks/README.md) and only the exact task file named in the dispatch message. Do not infer a task from a directory, plan, or another agent's output.

## Interpretation rules

- The Constitution, Graveyard, and explicit Owner decisions override convenience or a task's implied direction.
- The current `AGENT_ORCHESTRATION_PROTOCOL.md` v1 is the Owner-confirmed governance equivalent of the Charter's named v2 protocol for this Autonomous Arc batch. This does not relax any T3 approval requirement.
- `KARPATHY_GUIDELINES.md` and `NEAT_FREAK_SKILL.md` add engineering and knowledge-hygiene discipline; they do not authorize changes outside the Constitution or the task tier.
- Only Codex writes `AlphaHive_V3/`. Other agents produce read-only findings or isolated Desktop artifacts unless an Owner explicitly changes that boundary.
