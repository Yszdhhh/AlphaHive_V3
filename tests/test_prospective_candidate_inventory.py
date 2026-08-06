from __future__ import annotations

import json
from pathlib import Path

from harness.lib.prospective_candidate_inventory import inspect_prospective_candidates


def _write_run(root: Path, run_id: str, manifest: dict, rows: list[dict]) -> None:
    run = root / run_id
    run.mkdir()
    (run / "run_manifest.json").write_text(json.dumps(manifest), encoding="utf-8")
    (run / "input_snapshot.csv").write_text("symbol,timestamp\nBTCUSDT,1\n", encoding="utf-8")
    headers = ["symbol", "record_id"]
    body = ",".join(headers) + "\n" + "\n".join(
        f"{row.get('symbol','')},{row.get('record_id','')}" for row in rows
    ) + ("\n" if rows else "")
    (run / "candidates.csv").write_text(body, encoding="utf-8")


def test_fresh_registered_prospective_run_is_ready(tmp_path: Path) -> None:
    runs = tmp_path / "runs"
    runs.mkdir()
    manifest = {
        "run_id": "prospective",
        "scan_time_utc": "2026-07-18T10:00:00+00:00",
        "last_completed_bar_utc": "2026-07-18T09:00:00+00:00",
        "mode": "PROSPECTIVE_LIVE",
        "integrity": {"no_lookahead_attested": True},
    }
    _write_run(runs, "prospective", manifest, [{"symbol": "SOLUSDT", "record_id": "r1"}])
    registry = tmp_path / "run_registry.yaml"
    registry.write_text(
        "runs:\n  - run_id: prospective\n    status: clean\n    eligible_for_judgment: true\n",
        encoding="utf-8",
    )
    result = inspect_prospective_candidates(
        runs,
        registry,
        now_utc="2026-07-18T10:30:00+00:00",
        minimum_candidates=1,
    )
    assert result["verdict"] == "READY"
    assert result["source_run_id"] == "prospective"
    assert result["source_candidates"] == ["SOLUSDT"]


def test_historical_or_stale_run_never_becomes_prospective(tmp_path: Path) -> None:
    runs = tmp_path / "runs"
    runs.mkdir()
    manifest = {
        "run_id": "replay",
        "scan_time_utc": "2026-07-17T00:00:00+00:00",
        "last_completed_bar_utc": "2026-07-10T00:00:00+00:00",
        "mode": "HISTORICAL_REPLAY",
        "integrity": {"no_lookahead_attested": True},
    }
    _write_run(runs, "replay", manifest, [{"symbol": "BTCUSDT", "record_id": "r1"}])
    registry = tmp_path / "run_registry.yaml"
    registry.write_text(
        "runs:\n  - run_id: replay\n    status: clean\n    eligible_for_judgment: true\n",
        encoding="utf-8",
    )
    result = inspect_prospective_candidates(
        runs,
        registry,
        now_utc="2026-07-18T10:30:00+00:00",
        minimum_candidates=1,
    )
    assert result["verdict"] == "PARK"
    assert result["source_run_id"] is None
    assert "no_fresh_registry_authorized_prospective_run" in result["blockers"]

