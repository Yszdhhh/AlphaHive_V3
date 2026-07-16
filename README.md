# AlphaHive V3

AlphaHive V3 is an auditable anomaly-research and paper-execution-discipline system. It is **not** an automated trading bot and does not make trading decisions for the Owner.

## Start here

- Agents: read [`PROJECT_REQUIRED_READING.md`](PROJECT_REQUIRED_READING.md) before any work.
- New conversations: also read [`PROJECT_OPERATING_PLAYBOOK.md`](PROJECT_OPERATING_PLAYBOOK.md) for the persistent dispatch, collaboration and acceptance workflow.
- Humans: see [`PROJECT_CONSTITUTION.md`](PROJECT_CONSTITUTION.md) for purpose and boundaries, then [`KNOWN_LIMITATIONS.md`](KNOWN_LIMITATIONS.md) for evidence gaps.
- External-agent work: use [`agent_tasks/README.md`](agent_tasks/README.md); only Codex writes this repository.
- Binance public-data operations: see [`reports/BINANCE_PULL_OPERATIONS_20260715.md`](reports/BINANCE_PULL_OPERATIONS_20260715.md).

## Verification

```powershell
python -m pytest -q
```

## Layout

- `config/` — versioned contracts and universe definitions.
- `harness/` — research packaging and validation logic.
- `scripts/` — local scan, validation, and packaging utilities.
- `tests/` — regression coverage.
- `reports/` — dated evidence and operations records; see its README before treating a report as current governance.
- `agent_tasks/` — dispatch instructions for isolated external work.
