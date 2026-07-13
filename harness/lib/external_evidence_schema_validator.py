#!/usr/bin/env python3
"""
External Evidence Schema Validator

Validates AlphaHive external evidence envelopes produced by external_evidence_normalizer.
"""

import json
import hashlib
from typing import Any

SCHEMA_VERSION = "agent_artifact_bundle_v1"
UNVERIFIED_TAG = "UNVERIFIED_EXTERNAL_EVIDENCE"

TOP_LEVEL_REQUIRED = [
    "schema_version",
    "task_id",
    "job_id",
    "producer",
    "contract_version",
    "input_fingerprint",
    "observed_at_utc",
    "artifacts",
    "handoff",
    "performance_eligible",
    "artifact_hash",
]

VALID_GROK_REPORT_TYPES = {
    "ThemeDiscoveryReport",
    "ExternalResearchEvidence",
    "CaseStudyReport",
    "RedTeamReport",
}


def canonical_json(obj: Any) -> str:
    return json.dumps(obj, sort_keys=True, ensure_ascii=False, default=str)


def compute_hex_hash(content: str) -> str:
    return hashlib.sha256(content.encode("utf-8")).hexdigest()


def validate_top_level(bundle: dict) -> list:
    errors = []
    for field in TOP_LEVEL_REQUIRED:
        if field not in bundle:
            errors.append(f"TOP_MISSING: {field}")

    if bundle.get("schema_version") != SCHEMA_VERSION:
        errors.append(f"TOP_SCHEMA_VERSION: expected '{SCHEMA_VERSION}', got '{bundle.get('schema_version')}'")

    if bundle.get("performance_eligible") is not False:
        errors.append(f"TOP_PERFORMANCE_ELIGIBLE: expected false, got {bundle.get('performance_eligible')}")

    if not bundle.get("artifacts"):
        errors.append("TOP_ARTIFACTS: empty or missing")

    handoff = bundle.get("handoff", {})
    if handoff.get("source_job_id") != "GROK-INTEL-001":
        errors.append(f"TOP_HANDOFF_SOURCE_JOB_ID: expected 'GROK-INTEL-001', got '{handoff.get('source_job_id')}'")

    return errors


def validate_artifact_hash(bundle: dict) -> list:
    errors = []
    stored = bundle.get("artifact_hash", "")
    envelope_for_hash = {k: v for k, v in bundle.items() if k != "artifact_hash"}
    recomputed = compute_hex_hash(canonical_json(envelope_for_hash))
    if stored != recomputed:
        errors.append(f"ARTIFACT_HASH_MISMATCH: stored={stored[:16]}... recomputed={recomputed[:16]}...")
    if len(stored) != 64:
        errors.append(f"ARTIFACT_HASH_FORMAT: expected 64-char hex, got {len(stored)} chars")
    return errors


def validate_artifact_fields(artifact: dict, idx: int) -> list:
    errors = []
    aid = artifact.get("artifact_id", f"idx-{idx}")

    # artifact_hash must be 64 chars
    h = artifact.get("artifact_hash", "")
    if len(h) != 64:
        errors.append(f"ART_HASH[{aid}]: expected 64-char hex, got {len(h)}")

    # Recomputability
    art_for_hash = {k: v for k, v in artifact.items() if k != "artifact_hash"}
    recomputed = compute_hex_hash(canonical_json(art_for_hash))
    if h != recomputed:
        errors.append(f"ART_HASH_MISMATCH[{aid}]")

    # Tags
    tags = artifact.get("tags", [])
    if UNVERIFIED_TAG not in tags:
        errors.append(f"ART_MISSING_TAG[{aid}]: {UNVERIFIED_TAG}")

    # grok_report_type must be valid
    grt = artifact.get("grok_report_type", "")
    if grt not in VALID_GROK_REPORT_TYPES:
        errors.append(f"ART_INVALID_GROK_REPORT_TYPE[{aid}]: {grt}")

    return errors


def validate_category_counts(bundle: dict) -> list:
    errors = []
    artifacts = bundle.get("artifacts", [])

    actual = {}
    for a in artifacts:
        cat = a.get("grok_report_type", "UNKNOWN")
        actual[cat] = actual.get(cat, 0) + 1

    if len(actual) != 4:
        errors.append(f"CATEGORIES: expected 4, got {len(actual)}: {list(actual.keys())}")

    for cat in VALID_GROK_REPORT_TYPES:
        if cat not in actual:
            errors.append(f"CATEGORY_MISSING: {cat}")
        elif actual[cat] == 0:
            errors.append(f"CATEGORY_EMPTY: {cat}")

    return errors


def validate_bundle(bundle: dict) -> list:
    """Run all validations and return list of error strings. Empty list = all passed."""
    all_errors = []
    all_errors.extend(validate_top_level(bundle))
    all_errors.extend(validate_artifact_hash(bundle))
    artifacts = bundle.get("artifacts", [])
    for idx, art in enumerate(artifacts):
        all_errors.extend(validate_artifact_fields(art, idx))
    all_errors.extend(validate_category_counts(bundle))
    return all_errors
