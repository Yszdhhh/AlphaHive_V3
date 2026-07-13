#!/usr/bin/env python3
"""
Tests for MIMO-EXT-008 bundle.

Loads the real output file and verifies required fields.
"""

import json
import hashlib
import sys
from pathlib import Path

import pytest

# Add harness/lib to path for imports (if needed for validation)
sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "harness" / "lib"))

BUNDLE_PATH = Path(r"G:\Quant test\alpha_hive\results\research_jobs\MIMO-EXT-008\mimo_ext_008_bundle.json")

HARDWARE_KEYWORDS = ["NVIDIA", "H200", "GPU"]
STANDALONE_DIRECTIONAL = {"Long", "Short", "LONG", "SHORT", "long", "short"}


def _canonical_json(obj) -> str:
    return json.dumps(obj, sort_keys=True, ensure_ascii=False, default=str)


def _compute_hex_hash(content: str) -> str:
    return hashlib.sha256(content.encode("utf-8")).hexdigest()


@pytest.fixture(scope="module")
def bundle():
    with open(BUNDLE_PATH, "r", encoding="utf-8") as f:
        return json.load(f)


# ── Basic fields ──
class TestBasicFields:
    def test_schema_version(self, bundle):
        assert bundle["schema_version"] == "agent_artifact_bundle_v1"

    def test_task_id(self, bundle):
        assert bundle["task_id"] == "MIMO-EXT-008-TASK"

    def test_job_id(self, bundle):
        assert bundle["job_id"] == "MIMO-EXT-008-JOB"

    def test_source_job_id(self, bundle):
        assert bundle["source_job_id"] == "GROK-INTEL-001"

    def test_source_job_id_in_handoff(self, bundle):
        assert bundle["handoff"]["source_job_id"] == "GROK-INTEL-001"

    def test_producer(self, bundle):
        assert bundle["producer"] == "mimo-ext-008"

    def test_contract_version(self, bundle):
        assert bundle["contract_version"] == "research_orchestration_contract_v1"

    def test_performance_eligible_false(self, bundle):
        assert bundle["performance_eligible"] is False


# ── Hash recomputability ──
class TestHashRecomputability:
    def test_top_level_artifact_hash_recomputable(self, bundle):
        stored = bundle.get("artifact_hash", "")
        assert len(stored) == 64, f"Expected 64-char hex, got {len(stored)}"
        bundle_for_hash = {k: v for k, v in bundle.items() if k != "artifact_hash"}
        recomputed = _compute_hex_hash(_canonical_json(bundle_for_hash))
        assert stored == recomputed, "Top-level artifact_hash mismatch"

    def test_per_artifact_hash_recomputable(self, bundle):
        for art in bundle["artifacts"]:
            stored = art.get("artifact_hash", "")
            assert stored, f"{art['artifact_id']}: missing artifact_hash"
            art_for_hash = {k: v for k, v in art.items() if k != "artifact_hash"}
            recomputed = _compute_hex_hash(_canonical_json(art_for_hash))
            assert stored == recomputed, f"{art['artifact_id']}: hash mismatch"


# ── Artifact count ──
class TestArtifactCount:
    def test_thirty_five_artifacts(self, bundle):
        assert len(bundle["artifacts"]) == 35, f"Expected 35 artifacts, got {len(bundle['artifacts'])}"


# ── Categories ──
class TestCategories:
    def test_four_categories_present(self, bundle):
        cats = set(a["grok_report_type"] for a in bundle["artifacts"])
        expected = {"ThemeDiscoveryReport", "ExternalResearchEvidence",
                    "CaseStudyReport", "RedTeamReport"}
        assert cats == expected, f"Missing categories: {expected - cats}"

    def test_each_category_has_at_least_one_artifact(self, bundle):
        counts = {}
        for a in bundle["artifacts"]:
            cat = a["grok_report_type"]
            counts[cat] = counts.get(cat, 0) + 1
        for cat in ["ThemeDiscoveryReport", "ExternalResearchEvidence",
                     "CaseStudyReport", "RedTeamReport"]:
            assert cat in counts, f"Missing category: {cat}"
            assert counts[cat] > 0, f"Empty category: {cat}"


# ── Content safety ──
class TestContentSafety:
    def test_no_hardware_keywords(self, bundle):
        bundle_str = json.dumps(bundle)
        for kw in HARDWARE_KEYWORDS:
            assert kw not in bundle_str, f"Found '{kw}' in bundle"

    def test_no_standalone_directional(self, bundle):
        for art in bundle["artifacts"]:
            for flag in art.get("no_trade_flags", []):
                assert flag not in STANDALONE_DIRECTIONAL, \
                    f"{art['artifact_id']}: directional flag '{flag}'"


# ── Summary output ──
class TestSummaryOutput:
    def test_print_summary(self, bundle, capsys):
        """Print required summary for verification."""
        artifact_count = len(bundle["artifacts"])
        summary = (
            f"task_id={bundle['task_id']}, "
            f"job_id={bundle['job_id']}, "
            f"producer={bundle['producer']}, "
            f"artifact_count={artifact_count}"
        )
        with capsys.disabled():
            print("\n" + summary)
