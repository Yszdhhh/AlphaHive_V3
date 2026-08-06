"""Fail-closed preview from a scanner candidate to a ResearchJob create request.

The bridge deliberately returns a request draft only.  It neither imports the
server repository nor writes a job directory, so candidate discovery cannot
silently become research, Paper, notification, or trading execution.
"""
from __future__ import annotations

import hashlib
import json
from datetime import datetime, timezone
from typing import Any


def _hash(value: Any) -> str:
    return hashlib.sha256(
        json.dumps(value, sort_keys=True, ensure_ascii=False, separators=(",", ":"), default=str).encode("utf-8")
    ).hexdigest()


def _utc(value: Any) -> datetime | None:
    if not isinstance(value, str) or not value.strip():
        return None
    try:
        parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
    except ValueError:
        return None
    if parsed.tzinfo is None:
        return None
    return parsed.astimezone(timezone.utc)


def preview_research_job_creation(
    candidate: dict[str, Any],
    run: dict[str, Any],
    *,
    now_utc: str | datetime,
    freshness_hours: float = 24.0,
) -> dict[str, Any]:
    """Return ``READY`` only for a fresh registry-authorized live candidate.

    A READY preview grants research creation *eligibility*, not a PaperPlan,
    OwnerDecision, direction, notification, trigger, or execution permission.
    """
    if isinstance(now_utc, datetime) and now_utc.tzinfo is None:
        raise ValueError("now_utc must be timezone-aware")
    now = now_utc.astimezone(timezone.utc) if isinstance(now_utc, datetime) else _utc(now_utc)
    if now is None:
        raise ValueError("now_utc must be timezone-aware")
    blockers: list[str] = []
    if not isinstance(candidate, dict):
        blockers.append("candidate_invalid")
        candidate = {}
    record_id = candidate.get("record_id")
    symbol = candidate.get("symbol")
    if not isinstance(record_id, str) or not record_id:
        blockers.append("record_id_missing")
    if not isinstance(symbol, str) or not symbol:
        blockers.append("symbol_missing")
    if not isinstance(run, dict):
        blockers.append("run_invalid")
        run = {}
    if run.get("mode") != "PROSPECTIVE_LIVE":
        blockers.append("not_prospective_live")
    if run.get("registry_status") != "clean" or run.get("registry_eligible_for_judgment") is not True:
        blockers.append("run_not_registry_authorized")
    integrity = run.get("integrity") if isinstance(run.get("integrity"), dict) else {}
    if integrity.get("no_lookahead_attested") is not True:
        blockers.append("no_lookahead_not_attested")
    completed = _utc(run.get("last_completed_bar_utc"))
    if completed is None:
        blockers.append("completed_bar_missing")
    elif (now - completed).total_seconds() > freshness_hours * 3600:
        blockers.append("completed_bar_stale")
    if candidate.get("quality_status") == "BLOCK":
        blockers.append("quality_blocked")
    if candidate.get("decision") or candidate.get("direction"):
        blockers.append("candidate_contains_decision_or_direction")
    package = {
        "schema_version": "candidate_research_job_preview_v1",
        "record_id": record_id,
        "symbol": symbol,
        "run_id": run.get("run_id"),
        "mode": "PROSPECTIVE_LIVE",
        "scan_time_utc": run.get("scan_time_utc"),
        "last_completed_bar_utc": run.get("last_completed_bar_utc"),
        "quality_status": candidate.get("quality_status"),
        "source_candidate_hash": _hash(candidate),
        "source_run_hash": _hash(run),
        "research_capability": "ALLOW" if not blockers else "BLOCK",
        "paper_plan_capability": "BLOCK",
        "performance_eligible": False,
        "authority": "RESEARCH_JOB_CREATE_PREVIEW_ONLY",
    }
    package["artifact_hash"] = _hash(package)
    verdict = "READY" if not blockers else "PARK"
    return {
        "schema_version": "candidate_research_job_creation_preview_v1",
        "verdict": verdict,
        "blockers": sorted(set(blockers)),
        "candidate_package_preview": package,
        "create_request_draft": {"record_id": record_id} if verdict == "READY" else None,
        "hard_exclusions": [
            "no_job_directory_write",
            "no_owner_decision",
            "no_paper_plan",
            "no_notification",
            "no_trigger",
            "no_trade",
        ],
    }
