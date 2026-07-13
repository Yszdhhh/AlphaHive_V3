"""
external_evidence_normalizer.py

Normalizes a Grok 4.5 research bundle into agent_artifact_bundle_v1.

Handles the real Grok bundle structure:
  - ThemeDiscoveryReport
  - ExternalResearchEvidence
  - CaseStudyReport
  - RedTeamReport

Rules:
  - performance_eligible = false
  - All evidence tagged UNVERIFIED_EXTERNAL_EVIDENCE
  - No Long/Short conclusions
  - No Paper Plan
  - Real 64-char SHA-256 for every artifact and the bundle
  - file:// sources tagged INTERNAL_LOCAL_REFERENCE
  - Preserves: source_url, published_at_utc, cutoff_relation, no_trade_flags
  - Deduplicates artifacts with same content hash
"""

from __future__ import annotations

import hashlib
import json
import re
from datetime import datetime, timezone
from typing import Any


# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

SCHEMA_VERSION = "agent_artifact_bundle_v1"
CONTRACT_VERSION = "research_orchestration_contract_v1"
PRODUCER_ID = "mimo-ext-002"
UNVERIFIED_TAG = "UNVERIFIED_EXTERNAL_EVIDENCE"
INTERNAL_LOCAL_PREFIX = "INTERNAL_LOCAL_REFERENCE"
FILE_REF_PREFIX = "file://"


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _sha256_64(data: str) -> str:
    """Full 256-bit SHA-256 as 64 hex chars."""
    return hashlib.sha256(data.encode("utf-8")).hexdigest()


def _canonical_json(obj: Any) -> str:
    """Deterministic JSON serialization."""
    return json.dumps(obj, sort_keys=True, ensure_ascii=False, default=str)


def _artifact_hash(artifact: dict) -> str:
    """SHA-256 of artifact's canonical JSON."""
    return _sha256_64(_canonical_json(artifact))


def _normalize_ts(ts: str | None) -> str | None:
    if not ts:
        return None
    for fmt in (
        "%Y-%m-%dT%H:%M:%S%z",
        "%Y-%m-%dT%H:%M:%SZ",
        "%Y-%m-%dT%H:%M:%S",
        "%Y-%m-%d",
    ):
        try:
            dt = datetime.strptime(ts, fmt)
            if dt.tzinfo is None:
                dt = dt.replace(tzinfo=timezone.utc)
            return dt.isoformat()
        except ValueError:
            continue
    return ts


def _is_file_ref(source_url: str | None) -> bool:
    return bool(source_url and source_url.startswith(FILE_REF_PREFIX))


def _tags_for_evidence(source_url: str | None) -> list[str]:
    tags = [UNVERIFIED_TAG]
    if _is_file_ref(source_url):
        tags.append(INTERNAL_LOCAL_PREFIX)
    return tags


# ---------------------------------------------------------------------------
# Artifact builders per Grok report type
# ---------------------------------------------------------------------------

def _build_theme_artifacts(theme_report: dict, produced_at: str) -> list[dict]:
    """Flatten ThemeDiscoveryReport themes into artifacts."""
    artifacts = []
    window = theme_report.get("window_utc", {})
    for theme in theme_report.get("themes", []):
        theme_id = theme.get("theme_id", "UNKNOWN")
        # Merge all sources
        all_sources = []
        for src in theme.get("official_sources", []):
            all_sources.append({**src, "source_tier_label": "official"})
        for src in theme.get("independent_sources", []):
            all_sources.append({**src, "source_tier_label": "independent"})

        for idx, src in enumerate(all_sources):
            url = src.get("source_url")
            artifact = {
                "artifact_id": f"theme-{theme_id}-{idx:03d}",
                "artifact_type": "theme_source",
                "grok_report_type": "ThemeDiscoveryReport",
                "theme_id": theme_id,
                "theme_name": theme.get("theme_name"),
                "related_symbols": theme.get("related_symbols", []),
                "event_type": theme.get("event_type"),
                "source_tier": src.get("tier"),
                "source_tier_label": src.get("source_tier_label"),
                "source_url": url,
                "source_author": src.get("source_author"),
                "published_at_utc": _normalize_ts(src.get("published_at_utc")),
                "observed_at_utc": produced_at,
                "conflicting_claims": theme.get("conflicting_claims", []),
                "narrative_saturation": theme.get("narrative_saturation"),
                "likely_already_priced_in": theme.get("likely_already_priced_in"),
                "required_quant_checks": theme.get("required_quant_checks", []),
                "no_trade_flags": theme.get("no_trade_flags", []),
                "citations": theme.get("citations", []),
                "tags": _tags_for_evidence(url),
            }
            artifact["artifact_hash"] = _artifact_hash(artifact)
            artifacts.append(artifact)
    return artifacts


def _build_evidence_artifacts(evidence_report: dict, produced_at: str) -> list[dict]:
    """Flatten ExternalResearchEvidence.evidence into artifacts."""
    artifacts = []
    for ev in evidence_report.get("evidence", []):
        url = ev.get("source_url")
        artifact = {
            "artifact_id": f"ev-{ev.get('evidence_id', 'UNKNOWN')}",
            "artifact_type": "external_evidence",
            "grok_report_type": "ExternalResearchEvidence",
            "evidence_id": ev.get("evidence_id"),
            "record_id": ev.get("record_id"),
            "source_type": ev.get("source_type"),
            "source_url": url,
            "source_author": ev.get("source_author"),
            "published_at_utc": _normalize_ts(ev.get("published_at_utc")),
            "observed_at_utc": produced_at,
            "cutoff_relation": ev.get("cutoff_relation"),
            "claim": ev.get("claim"),
            "evidence_summary": ev.get("evidence_summary"),
            "confidence": ev.get("confidence"),
            "no_trade_flags": ev.get("no_trade_flags", []),
            "content_hash": ev.get("content_hash"),
            "tags": _tags_for_evidence(url),
        }
        artifact["artifact_hash"] = _artifact_hash(artifact)
        artifacts.append(artifact)
    return artifacts


def _build_case_artifacts(case_report: dict, produced_at: str) -> list[dict]:
    """Flatten CaseStudyReport.cases into artifacts."""
    artifacts = []
    for case in case_report.get("cases", []):
        # Take first source_url for the artifact
        urls = case.get("source_urls", [])
        primary_url = urls[0] if urls else None
        artifact = {
            "artifact_id": f"case-{case.get('case_id', 'UNKNOWN')}",
            "artifact_type": "case_study",
            "grok_report_type": "CaseStudyReport",
            "case_id": case.get("case_id"),
            "label_bucket": case.get("label_bucket"),
            "theme_id": case.get("theme_id"),
            "symbol": case.get("symbol"),
            "event_time": _normalize_ts(case.get("event_time")),
            "price_reaction": case.get("price_reaction"),
            "outcome_label": case.get("outcome_label"),
            "failure_reason": case.get("failure_reason"),
            "quant_snapshot": case.get("quant_snapshot"),
            "replay_features": case.get("replay_features", []),
            "source_urls": urls,
            "source_url": primary_url,
            "published_at_utc": _normalize_ts(case.get("event_time")),
            "observed_at_utc": produced_at,
            "no_trade_flags": [],
            "tags": _tags_for_evidence(primary_url),
        }
        artifact["artifact_hash"] = _artifact_hash(artifact)
        artifacts.append(artifact)
    return artifacts


def _build_redteam_artifacts(redteam_report: dict, produced_at: str) -> list[dict]:
    """Flatten RedTeamReport.findings into artifacts."""
    artifacts = []
    for finding in redteam_report.get("findings", []):
        artifact = {
            "artifact_id": f"rt-{finding.get('finding_id', 'UNKNOWN')}",
            "artifact_type": "red_team_finding",
            "grok_report_type": "RedTeamReport",
            "finding_id": finding.get("finding_id"),
            "category": finding.get("category"),
            "severity": finding.get("severity"),
            "status": finding.get("status"),
            "detail": finding.get("detail"),
            "evidence_refs": finding.get("evidence_refs", []),
            "recommended_fix": finding.get("recommended_fix"),
            "published_at_utc": produced_at,
            "observed_at_utc": produced_at,
            "no_trade_flags": [],
            "tags": [UNVERIFIED_TAG],
        }
        artifact["artifact_hash"] = _artifact_hash(artifact)
        artifacts.append(artifact)
    return artifacts


# ---------------------------------------------------------------------------
# Deduplication
# ---------------------------------------------------------------------------

def _dedup_artifacts(artifacts: list[dict]) -> tuple[list[dict], int]:
    """Stable dedup by artifact_hash. Returns (deduped, original_count)."""
    seen: set[str] = set()
    result = []
    for art in artifacts:
        h = art["artifact_hash"]
        if h not in seen:
            seen.add(h)
            result.append(art)
    return result, len(artifacts)


# ---------------------------------------------------------------------------
# Main normalizer
# ---------------------------------------------------------------------------

def normalize_grok_bundle(
    raw: dict,
    observed_at_utc: str,
    task_id: str,
    job_id: str,
    producer: str,
    source_job_id: str,
) -> dict:
    """
    Normalize a real Grok 4.5 bundle into agent_artifact_bundle_v1.
    """
    produced_at = observed_at_utc  # required, no fallback
    raw_task_id = task_id
    job_id = job_id

    # --- Collect all artifacts from all report types ---
    all_artifacts: list[dict] = []
    artifacts_section = raw.get("artifacts", {})

    if "ThemeDiscoveryReport" in artifacts_section:
        all_artifacts.extend(_build_theme_artifacts(artifacts_section["ThemeDiscoveryReport"], produced_at))

    if "ExternalResearchEvidence" in artifacts_section:
        all_artifacts.extend(_build_evidence_artifacts(artifacts_section["ExternalResearchEvidence"], produced_at))

    if "CaseStudyReport" in artifacts_section:
        all_artifacts.extend(_build_case_artifacts(artifacts_section["CaseStudyReport"], produced_at))

    if "RedTeamReport" in artifacts_section:
        all_artifacts.extend(_build_redteam_artifacts(artifacts_section["RedTeamReport"], produced_at))

    # --- Dedup ---
    deduped, raw_count = _dedup_artifacts(all_artifacts)

    # --- Input fingerprint ---
    input_fp = _sha256_64(_canonical_json(raw))

    # --- Handoff ---
    handoff = {
        "producer": producer,
        "produced_at_utc": produced_at,
        "source_job_id": source_job_id,
        "input_fingerprint": input_fp,
        "raw_source_count": raw_count,
        "deduplicated_count": len(deduped),
        "artifact_count": len(deduped),
        "grok_report_types_present": list(artifacts_section.keys()),
        "note": (
            "All evidence is UNVERIFIED_EXTERNAL_EVIDENCE. "
            "No Long/Short direction is assigned. "
            "No Paper Plan is generated. "
            "performance_eligible is false per scope_limits."
        ),
    }

    # --- Bundle ---
    bundle = {
        "schema_version": SCHEMA_VERSION,
        "contract_version": CONTRACT_VERSION,
        "task_id": task_id,
        "job_id": job_id,
        "source_job_id": source_job_id,
        "producer": producer,
        "input_fingerprint": input_fp,
        "observed_at_utc": produced_at,
        "query": raw.get("input_fingerprint", {}).get("target_symbol", raw_task_id),
        "task_description": f"Normalized external intel from {raw_task_id}",
        "artifacts": deduped,
        "handoff": handoff,
        "performance_eligible": False,
        "scope_limits_preserved": raw.get("scope_limits"),
        "source_credibility_rules": raw.get("source_credibility_rules"),
    }

    # --- Bundle hash ---
    bundle_for_hash = {k: v for k, v in bundle.items() if k != "artifact_hash"}
    bundle["artifact_hash"] = _sha256_64(_canonical_json(bundle_for_hash))

    return bundle


# ---------------------------------------------------------------------------
# Validation
# ---------------------------------------------------------------------------

def validate_bundle(bundle: dict) -> list[str]:
    errors: list[str] = []

    if bundle.get("schema_version") != SCHEMA_VERSION:
        errors.append(f"schema_version must be {SCHEMA_VERSION}")

    for required in ("task_id", "job_id", "producer", "contract_version",
                     "input_fingerprint", "performance_eligible", "artifacts", "handoff"):
        if required not in bundle:
            errors.append(f"Missing: {required}")

    if bundle.get("performance_eligible") is not False:
        errors.append("performance_eligible must be false")

    if not isinstance(bundle.get("artifacts"), list):
        errors.append("artifacts must be a list")
    else:
        for i, art in enumerate(bundle["artifacts"]):
            h = art.get("artifact_hash", "")
            if len(h) != 64:
                errors.append(f"artifact[{i}]: hash must be 64 chars, got {len(h)}")
            tags = art.get("tags", [])
            if UNVERIFIED_TAG not in tags:
                errors.append(f"artifact[{i}]: must be tagged {UNVERIFIED_TAG}")

    return errors


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------

if __name__ == "__main__":
    import sys
    if len(sys.argv) < 3:
        print("Usage: python external_evidence_normalizer.py <input.json> <output.json>")
        sys.exit(1)

    with open(sys.argv[1], "r", encoding="utf-8") as f:
        raw = json.load(f)

    result = normalize_grok_bundle(raw)
    errors = validate_bundle(result)
    if errors:
        for e in errors:
            print(f"ERROR: {e}")
        sys.exit(1)

    with open(sys.argv[2], "w", encoding="utf-8") as f:
        json.dump(result, f, indent=2, ensure_ascii=False)

    print(f"OK: {len(result['artifacts'])} artifacts from {result['handoff']['raw_source_count']} raw")
