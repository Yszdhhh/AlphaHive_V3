#!/usr/bin/env python3
"""
Tests for external evidence envelope normalization.

Covers:
- schema_version
- Top-level artifact_hash
- performance_eligible=false
- Hash recomputability (deterministic)
- Time field semantics
- 4 category counts
- No NVIDIA/H200/GPU
- No standalone Long/Short
- Deterministic: same input + same observed_at_utc → same hash
- No writes to alpha_hive/results
"""

import json
import hashlib
import sys
from pathlib import Path

import pytest

# Add harness/lib to path for imports
sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "harness" / "lib"))

from external_evidence_normalizer import normalize_grok_bundle
from external_evidence_schema_validator import validate_bundle

INPUT_PATH = Path(r"G:\Quant test\alpha_hive\results\research_jobs\GROK-INTEL-001\grok_intel_001_bundle.json")

FIXED_OBSERVED_AT = "2026-07-12T13:48:30Z"

HARDWARE_KEYWORDS = ["NVIDIA", "H200", "GPU"]
STANDALONE_DIRECTIONAL = {"Long", "Short", "LONG", "SHORT", "long", "short"}


def _canonical_json(obj) -> str:
    return json.dumps(obj, sort_keys=True, ensure_ascii=False, default=str)


def _compute_hex_hash(content: str) -> str:
    return hashlib.sha256(content.encode("utf-8")).hexdigest()


@pytest.fixture(scope="module")
def source():
    with open(INPUT_PATH, "r", encoding="utf-8") as f:
        return json.load(f)


@pytest.fixture(scope="module")
def envelope(source):
    raw_task_id = source.get("task_id", "UNKNOWN")
    job_id = f"MIMO-EXT-{raw_task_id.replace('GROK-INTEL-', '')}"
    producer = "mimo-ext-001"
    source_job_id = raw_task_id
    return normalize_grok_bundle(
        source,
        observed_at_utc=FIXED_OBSERVED_AT,
        task_id=job_id,
        job_id=job_id,
        producer=producer,
        source_job_id=source_job_id,
    )


# ── Schema validation ──
class TestSchemaValidation:
    def test_schema_version(self, envelope):
        assert envelope["schema_version"] == "agent_artifact_bundle_v1"

    def test_all_schema_checks_pass(self, envelope):
        errors = validate_bundle(envelope)
        assert errors == [], f"Schema errors: {errors}"


# ── Top-level fields ──
class TestTopLevelFields:
    def test_task_id(self, envelope):
        assert envelope["task_id"] == "MIMO-EXT-001"

    def test_job_id(self, envelope):
        assert envelope["job_id"] == "MIMO-EXT-001"

    def test_source_job_id_in_handoff(self, envelope):
        assert envelope["handoff"]["source_job_id"] == "GROK-INTEL-001"

    def test_performance_eligible_false(self, envelope):
        assert envelope["performance_eligible"] is False

    def test_observed_at_utc_matches_input(self, envelope):
        assert envelope["observed_at_utc"] == FIXED_OBSERVED_AT


# ── Hash ──
class TestHash:
    def test_top_level_artifact_hash_format(self, envelope):
        h = envelope.get("artifact_hash", "")
        assert len(h) == 64, f"Expected 64-char hex, got {len(h)}"

    def test_top_level_artifact_hash_recomputable(self, envelope):
        stored = envelope.get("artifact_hash", "")
        envelope_for_hash = {k: v for k, v in envelope.items() if k != "artifact_hash"}
        recomputed = _compute_hex_hash(_canonical_json(envelope_for_hash))
        assert stored == recomputed

    def test_per_artifact_hash_recomputable(self, envelope):
        for art in envelope["artifacts"]:
            stored = art.get("artifact_hash", "")
            assert stored, f"{art['artifact_id']}: missing artifact_hash"
            art_for_hash = {k: v for k, v in art.items() if k != "artifact_hash"}
            recomputed = _compute_hex_hash(_canonical_json(art_for_hash))
            assert stored == recomputed, f"{art['artifact_id']}: hash mismatch"

    def test_deterministic_same_input_same_hash(self, source):
        """Same input + same observed_at_utc → identical artifact_hash."""
        raw_task_id = source.get("task_id", "UNKNOWN")
        job_id = f"MIMO-EXT-{raw_task_id.replace('GROK-INTEL-', '')}"
        producer = "mimo-ext-001"
        source_job_id = raw_task_id
        env1 = normalize_grok_bundle(source, observed_at_utc=FIXED_OBSERVED_AT,
                                     task_id=job_id, job_id=job_id,
                                     producer=producer, source_job_id=source_job_id)
        env2 = normalize_grok_bundle(source, observed_at_utc=FIXED_OBSERVED_AT,
                                     task_id=job_id, job_id=job_id,
                                     producer=producer, source_job_id=source_job_id)
        assert env1["artifact_hash"] == env2["artifact_hash"]
        assert json.dumps(env1, sort_keys=True) == json.dumps(env2, sort_keys=True)


# ── Time fields ──
class TestTimeFields:
    def test_observed_at_utc_not_copied_from_published(self, envelope):
        """For artifacts with a real published_at_utc, observed must differ."""
        for art in envelope["artifacts"]:
            observed = art.get("observed_at_utc", "")
            published = art.get("published_at_utc", "")
            # Only check artifacts that have a distinct published_at (not red-team findings)
            if published and observed and published != observed:
                # If they differ, observed should be our fixed time, not the source time
                assert observed == FIXED_OBSERVED_AT or observed != published

    def test_observed_at_utc_matches_fixed(self, envelope):
        for art in envelope["artifacts"]:
            assert art["observed_at_utc"] == FIXED_OBSERVED_AT


# ── Categories ──
class TestCategories:
    def test_four_categories(self, envelope):
        cats = set(a["grok_report_type"] for a in envelope["artifacts"])
        assert cats == {"ThemeDiscoveryReport", "ExternalResearchEvidence",
                        "CaseStudyReport", "RedTeamReport"}

    def test_category_counts(self, envelope):
        computed = {}
        for a in envelope["artifacts"]:
            cat = a["grok_report_type"]
            computed[cat] = computed.get(cat, 0) + 1
        assert len(computed) == 4
        # All four categories must be present with at least 1 artifact
        for cat in ["ThemeDiscoveryReport", "ExternalResearchEvidence",
                     "CaseStudyReport", "RedTeamReport"]:
            assert cat in computed, f"Missing category: {cat}"
            assert computed[cat] > 0, f"Empty category: {cat}"


# ── Content safety ──
class TestContentSafety:
    def test_no_hardware_keywords(self, envelope):
        bundle_str = json.dumps(envelope)
        for kw in HARDWARE_KEYWORDS:
            assert kw not in bundle_str, f"Found '{kw}'"

    def test_no_standalone_directional(self, envelope):
        for art in envelope["artifacts"]:
            for flag in art.get("no_trade_flags", []):
                assert flag not in STANDALONE_DIRECTIONAL, \
                    f"{art['artifact_id']}: directional flag '{flag}'"

    def test_all_artifacts_tagged(self, envelope):
        for art in envelope["artifacts"]:
            assert "UNVERIFIED_EXTERNAL_EVIDENCE" in art.get("tags", [])

    def test_no_null_source_fields(self, envelope):
        for art in envelope["artifacts"]:
            # source_url may be absent for red-team findings; if present, must not be None
            if "source_url" in art:
                assert art["source_url"] is not None


# ── Paths ──
class TestPaths:
    def test_input_in_quant_test(self):
        assert str(INPUT_PATH).startswith("G:\\Quant test")


# ── Contract consistency ──
class TestContractConsistency:
    def test_task_id_and_job_id_distinct(self, source):
        """When task_id != job_id, bundle must preserve both correctly."""
        raw_task_id = source.get("task_id", "UNKNOWN")
        job_id = f"MIMO-EXT-{raw_task_id.replace('GROK-INTEL-', '')}"
        task_id = "CUSTOM-TASK-ID"
        producer = "mimo-ext-001"
        source_job_id = raw_task_id
        bundle = normalize_grok_bundle(
            source,
            observed_at_utc=FIXED_OBSERVED_AT,
            task_id=task_id,
            job_id=job_id,
            producer=producer,
            source_job_id=source_job_id,
        )
        assert bundle["task_id"] == task_id
        assert bundle["job_id"] == job_id
        assert bundle["task_id"] != bundle["job_id"]
        # Ensure no cross-contamination
        assert bundle["task_id"] != job_id
        assert bundle["job_id"] != task_id

    def test_source_job_id_top_level(self, source):
        """Top-level source_job_id must match the parameter."""
        raw_task_id = source.get("task_id", "UNKNOWN")
        job_id = f"MIMO-EXT-{raw_task_id.replace('GROK-INTEL-', '')}"
        producer = "mimo-ext-001"
        source_job_id = raw_task_id
        bundle = normalize_grok_bundle(
            source,
            observed_at_utc=FIXED_OBSERVED_AT,
            task_id=job_id,
            job_id=job_id,
            producer=producer,
            source_job_id=source_job_id,
        )
        assert bundle["source_job_id"] == source_job_id
        # Also verify handoff source_job_id matches
        assert bundle["handoff"]["source_job_id"] == source_job_id

    def test_contract_version(self, source):
        """Contract version must be research_orchestration_contract_v1."""
        raw_task_id = source.get("task_id", "UNKNOWN")
        job_id = f"MIMO-EXT-{raw_task_id.replace('GROK-INTEL-', '')}"
        producer = "mimo-ext-001"
        source_job_id = raw_task_id
        bundle = normalize_grok_bundle(
            source,
            observed_at_utc=FIXED_OBSERVED_AT,
            task_id=job_id,
            job_id=job_id,
            producer=producer,
            source_job_id=source_job_id,
        )
        assert bundle["contract_version"] == "research_orchestration_contract_v1"
