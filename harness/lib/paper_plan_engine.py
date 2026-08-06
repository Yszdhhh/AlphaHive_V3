"""Deterministic, offline PaperPlan construction.

This module deliberately has no provider, exchange, scheduler, notification or
database dependency.  It accepts an already materialized OwnerDecision-shaped
fixture and produces a content-addressed plan only when the input is an
eligible prospective job.  The real OwnerDecision endpoint remains outside
this sandbox.
"""
from __future__ import annotations

import hashlib
import json
from datetime import datetime, timezone
from typing import Any, Iterable


class PaperPlanRejected(ValueError):
    """A fail-closed plan construction rejection."""

    def __init__(self, code: str, message: str | None = None):
        self.code = code
        super().__init__(message or code)


def canonical_json(value: Any) -> str:
    return json.dumps(value, sort_keys=True, ensure_ascii=False, separators=(",", ":"), default=str)


def content_hash(value: Any) -> str:
    return hashlib.sha256(canonical_json(value).encode("utf-8")).hexdigest()


def preset_hash(preset: dict[str, Any]) -> str:
    value = {key: item for key, item in preset.items() if key not in {"preset_hash", "artifact_hash"}}
    return content_hash(value)


def export_research_job_prompt(job_id: str, input_package: dict[str, Any]) -> dict[str, Any]:
    """Create a deterministic provider-neutral local prompt export.

    The function deliberately does not import or call an LLM/provider.  The
    caller owns the immutable input package; this wrapper only binds it to a
    ResearchJob and content-addresses the resulting local artifact.
    """
    if not isinstance(job_id, str) or not job_id:
        raise PaperPlanRejected("invalid_job_id")
    if not isinstance(input_package, dict) or not input_package:
        raise PaperPlanRejected("invalid_prompt_package")
    package = json.loads(json.dumps(input_package, ensure_ascii=False, default=str))
    package_job_id = package.get("job_id")
    if package_job_id is not None and package_job_id != job_id:
        raise PaperPlanRejected("prompt_job_binding_mismatch")
    body = {
        "schema_version": "research_job_prompt_export_v1",
        "job_id": job_id,
        "input_package_hash": content_hash(package),
        "provider_neutral": True,
        "provider_calls": False,
        "input_package": package,
    }
    body["artifact_hash"] = content_hash(body)
    return body


def _utc(value: Any) -> datetime:
    if not isinstance(value, str) or not value.strip():
        raise PaperPlanRejected("invalid_timestamp")
    try:
        parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
    except ValueError as exc:
        raise PaperPlanRejected("invalid_timestamp") from exc
    if parsed.tzinfo is None:
        raise PaperPlanRejected("timestamp_requires_timezone")
    return parsed.astimezone(timezone.utc)


def _bars(bars: Iterable[dict[str, Any]]) -> list[dict[str, Any]]:
    normalized = []
    for bar in bars:
        if not isinstance(bar, dict):
            raise PaperPlanRejected("invalid_bar")
        ts = _utc(bar.get("timestamp"))
        try:
            open_price = float(bar["open"])
        except (KeyError, TypeError, ValueError) as exc:
            raise PaperPlanRejected("invalid_bar_price") from exc
        if open_price <= 0:
            raise PaperPlanRejected("invalid_bar_price")
        normalized.append({"timestamp": ts.isoformat(), "_timestamp": ts, "open": open_price})
    normalized.sort(key=lambda item: item["_timestamp"])
    if not normalized:
        raise PaperPlanRejected("missing_entry_bar")
    if any(left["_timestamp"] >= right["_timestamp"] for left, right in zip(normalized, normalized[1:])):
        raise PaperPlanRejected("duplicate_or_unsorted_bars")
    return normalized


def build_paper_plan(
    job: dict[str, Any],
    owner_decision: dict[str, Any],
    preset: dict[str, Any],
    bars: Iterable[dict[str, Any]],
) -> dict[str, Any]:
    """Build a deterministic plan for an isolated synthetic eligible fixture."""
    if not isinstance(job, dict) or not isinstance(owner_decision, dict) or not isinstance(preset, dict):
        raise PaperPlanRejected("invalid_input")
    if job.get("status") != "RESEARCH_ASSESSMENT_READY":
        raise PaperPlanRejected("invalid_job_state")
    if job.get("mode") != "PROSPECTIVE_LIVE":
        raise PaperPlanRejected("historical_mode_blocked")
    capabilities = job.get("capabilities") or {}
    if capabilities.get("paper_plan_capability") != "ALLOW":
        raise PaperPlanRejected("paper_capability_blocked")
    if job.get("performance_eligible") is not True:
        raise PaperPlanRejected("performance_not_eligible")
    if owner_decision.get("decision") != "APPROVE_PAPER":
        raise PaperPlanRejected("owner_decision_not_approve")
    if not owner_decision.get("owner_id") or owner_decision.get("owner_authenticated") is not True:
        raise PaperPlanRejected("owner_authentication_required")
    if not owner_decision.get("owner_confirmation") or owner_decision.get("confirmation_text_valid") is not True:
        raise PaperPlanRejected("owner_confirmation_required")
    for key in ("job_id", "record_id", "candidate_package_hash", "evidence_set_hash", "verification_hash", "assessment_hash"):
        if owner_decision.get(key) != job.get(key):
            raise PaperPlanRejected(f"binding_mismatch:{key}")
    if owner_decision.get("job_id") != job.get("job_id") or owner_decision.get("record_id") != job.get("record_id"):
        raise PaperPlanRejected("identity_binding_mismatch")
    if preset.get("schema_version") != "paper_execution_presets_v1" or preset.get("status") != "APPROVED":
        raise PaperPlanRejected("preset_not_approved")
    if owner_decision.get("selected_preset_version") != preset.get("preset_version"):
        raise PaperPlanRejected("preset_version_mismatch")
    actual_preset_hash = preset_hash(preset)
    if owner_decision.get("selected_preset_hash") != actual_preset_hash:
        raise PaperPlanRejected("preset_hash_mismatch")
    direction = owner_decision.get("direction")
    if direction not in {"LONG", "SHORT"}:
        raise PaperPlanRejected("invalid_direction")
    try:
        decision_time = _utc(owner_decision["decision_time_utc"])
    except KeyError as exc:
        raise PaperPlanRejected("missing_decision_time") from exc
    normalized_bars = _bars(bars)
    entry = next((bar for bar in normalized_bars if bar["_timestamp"] > decision_time), None)
    if entry is None:
        raise PaperPlanRejected("missing_entry_bar")
    horizon_hours = int(preset.get("horizon_hours", owner_decision.get("horizon_hours", 0)))
    stop_distance_pct = float(preset.get("stop_distance_pct", owner_decision.get("stop_distance_pct", 0)))
    targets = preset.get("take_profit_targets")
    if horizon_hours <= 0 or stop_distance_pct <= 0 or not isinstance(targets, list) or not targets:
        raise PaperPlanRejected("preset_missing_execution_fields")
    if abs(sum(float(item.get("exit_weight_pct", 0)) for item in targets) - 100.0) > 1e-9:
        raise PaperPlanRejected("take_profit_weights_invalid")
    plan = {
        "schema_version": "paper_plan_v1",
        "job_id": job["job_id"],
        "record_id": job["record_id"],
        "candidate_package_hash": job["candidate_package_hash"],
        "evidence_set_hash": job["evidence_set_hash"],
        "verification_hash": job["verification_hash"],
        "assessment_hash": job["assessment_hash"],
        "owner_id": owner_decision["owner_id"],
        "decision_time_utc": decision_time.isoformat(),
        "direction": direction,
        "selected_preset_version": preset["preset_version"],
        "selected_preset_hash": actual_preset_hash,
        "entry_anchor_timestamp_utc": entry["timestamp"],
        "entry_reference_price": entry["open"],
        "horizon_hours": horizon_hours,
        "stop_distance_pct": stop_distance_pct,
        "take_profit_targets": targets,
        "paper_risk_per_trade_pct": float(preset.get("paper_risk_per_trade_pct", 0)),
        "max_open_portfolio_risk_pct": float(preset.get("max_open_portfolio_risk_pct", 0)),
        "friction_bps_roundtrip": float(preset.get("friction_bps_roundtrip", 0)),
        "no_live_order_path": True,
    }
    plan["plan_id"] = "plan_" + content_hash(plan)[:32]
    plan["artifact_hash"] = content_hash(plan)
    return plan
