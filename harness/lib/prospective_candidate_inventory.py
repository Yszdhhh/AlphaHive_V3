"""Read-only inventory for prospective candidate production.

This module does not create runs, alter ledgers, refresh data, or change scan
thresholds.  It answers one operational question: is there a fresh,
registry-authorized ``PROSPECTIVE_LIVE`` run from which a new ResearchJob may
be created?  Historical replay rows are reported for diagnostics only and are
never promoted to prospective candidates.
"""
from __future__ import annotations

import csv
import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


def _parse_utc(value: Any) -> datetime | None:
    if not isinstance(value, str) or not value.strip():
        return None
    try:
        parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
    except ValueError:
        return None
    if parsed.tzinfo is None:
        return None
    return parsed.astimezone(timezone.utc)


def _load_registry(path: Path | None) -> dict[str, dict[str, Any]]:
    if path is None or not path.exists():
        return {}
    try:
        import yaml

        payload = yaml.safe_load(path.read_text(encoding="utf-8")) or {}
    except ImportError:  # pragma: no cover - project runtime provides yaml
        payload = json.loads(path.read_text(encoding="utf-8"))
    return {
        str(entry.get("run_id")): entry
        for entry in payload.get("runs", [])
        if isinstance(entry, dict) and entry.get("run_id")
    }


def _candidate_rows(path: Path) -> list[dict[str, Any]]:
    if not path.exists():
        return []
    with path.open(newline="", encoding="utf-8-sig") as handle:
        return list(csv.DictReader(handle))


def _run_snapshot(run_dir: Path, registry: dict[str, dict[str, Any]]) -> dict[str, Any]:
    manifest_path = run_dir / "run_manifest.json"
    if not manifest_path.exists():
        return {"run_id": run_dir.name, "valid": False, "reasons": ["manifest_missing"]}
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    entry = registry.get(run_dir.name, {})
    candidates = _candidate_rows(run_dir / "candidates.csv")
    scan_time = _parse_utc(manifest.get("scan_time_utc"))
    completed_bar = _parse_utc(manifest.get("last_completed_bar_utc"))
    integrity = manifest.get("integrity") if isinstance(manifest.get("integrity"), dict) else {}
    reasons: list[str] = []
    if not (run_dir / "input_snapshot.csv").exists():
        reasons.append("snapshot_missing")
    if not (run_dir / "candidates.csv").exists():
        reasons.append("candidates_missing")
    if integrity.get("no_lookahead_attested") is not True:
        reasons.append("no_lookahead_not_attested")
    return {
        "run_id": run_dir.name,
        "valid": not reasons,
        "scan_time_utc": scan_time.isoformat() if scan_time else None,
        "last_completed_bar_utc": completed_bar.isoformat() if completed_bar else None,
        "mode": manifest.get("mode"),
        "manifest_status": manifest.get("status"),
        "registry_status": entry.get("status"),
        "registry_eligible_for_judgment": entry.get("eligible_for_judgment"),
        "candidate_count": len(candidates),
        "candidate_symbols": [row.get("symbol") for row in candidates if row.get("symbol")],
        "reasons": reasons,
    }


def inspect_prospective_candidates(
    runs_dir: str | Path,
    registry_path: str | Path | None = None,
    *,
    now_utc: str | datetime | None = None,
    freshness_hours: float = 24.0,
    minimum_candidates: int = 10,
) -> dict[str, Any]:
    """Return a deterministic, read-only prospective-candidate inventory."""
    root = Path(runs_dir)
    registry = _load_registry(Path(registry_path) if registry_path is not None else None)
    if now_utc is None:
        now = datetime.now(timezone.utc)
    elif isinstance(now_utc, datetime):
        now = now_utc.astimezone(timezone.utc)
    else:
        now = _parse_utc(now_utc)
        if now is None:
            raise ValueError("now_utc must be timezone-aware ISO timestamp")
    snapshots = []
    if root.exists():
        for child in root.iterdir():
            if child.is_dir():
                snapshots.append(_run_snapshot(child, registry))
    snapshots.sort(key=lambda item: (item.get("scan_time_utc") or "", item["run_id"]), reverse=True)
    latest = snapshots[0] if snapshots else None
    ready = []
    for item in snapshots:
        if not item.get("valid"):
            continue
        if item.get("mode") != "PROSPECTIVE_LIVE":
            continue
        if item.get("registry_status") != "clean" or item.get("registry_eligible_for_judgment") is not True:
            continue
        completed = _parse_utc(item.get("last_completed_bar_utc"))
        if completed is None or (now - completed).total_seconds() > freshness_hours * 3600:
            continue
        if item.get("candidate_count", 0) < 1:
            continue
        ready.append(item)
    blockers: list[str] = []
    if not ready:
        blockers.append("no_fresh_registry_authorized_prospective_run")
    if latest is None:
        blockers.append("no_scan_runs")
    else:
        if latest.get("candidate_count", 0) < minimum_candidates:
            blockers.append("latest_candidate_count_below_target")
        completed = _parse_utc(latest.get("last_completed_bar_utc"))
        if completed is None:
            blockers.append("latest_completed_bar_missing")
        elif (now - completed).total_seconds() > freshness_hours * 3600:
            blockers.append("latest_completed_bar_stale")
        if latest.get("registry_status") != "clean":
            blockers.append("latest_run_not_registry_clean")
    return {
        "schema_version": "prospective_candidate_inventory_v1",
        "generated_at_utc": now.isoformat(),
        "freshness_hours": freshness_hours,
        "minimum_candidates": minimum_candidates,
        "verdict": "READY" if ready else "PARK",
        "source_run_id": ready[0]["run_id"] if ready else None,
        "source_candidates": ready[0]["candidate_symbols"] if ready else [],
        "latest_observed_run": latest,
        "runs": snapshots,
        "blockers": sorted(set(blockers)),
        "read_only": True,
    }

