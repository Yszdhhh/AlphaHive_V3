# RESEARCHJOB-MVP-001A — Mimo Fixture Task

```yaml
task_id: RESEARCHJOB-MVP-001A-MIMO-FIXTURES
workspace_root: "G:\\Quant test"
```

Create fixtures only. Do not edit server, store, routes, contracts, dashboard or
authoritative run/result data.

## Allowed paths

```text
AlphaHive_V3/tests/fixtures/research_jobs/**
AlphaHive_V3/tests/fixtures/research_jobs/README.md
```

## Required fixtures

1. valid record ID cases;
2. invalid/path traversal/Windows reserved/overlong record ID cases;
3. duplicate-create request cases;
4. restart-persistence expected state;
5. valid two-event hash-chain example;
6. corrupted event-chain example;
7. immutable package pointer example.

Use JSON only where possible. Each fixture must state whether it is a valid or
invalid case and the expected reason code. Do not create nested project copies
or write under `alpha_hive/results`.
