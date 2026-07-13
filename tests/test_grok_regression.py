"""
test_grok_regression.py

Regression tests for MIMO-EXT-002: processing the real GROK-INTEL-001 bundle.

All tests MUST read from the actual G:\Quant test\... path.
"""

from __future__ import annotations

import hashlib
import json
import os
import sys
import unittest

# Ensure importable
sys.path.insert(0, r"G:\Quant test")
from AlphaHive_V3.harness.lib.external_evidence_normalizer import (
    SCHEMA_VERSION,
    UNVERIFIED_TAG,
    normalize_grok_bundle,
    validate_bundle,
    _sha256_64,
    _canonical_json,
)

GROK_INPUT = r"G:\Quant test\alpha_hive\results\research_jobs\GROK-INTEL-001\grok_intel_001_bundle.json"
MIMO_OUTPUT = r"G:\Quant test\alpha_hive\results\research_jobs\MIMO-EXT-002\external_intel_bundle_v2.json"

# --- Fixtures loaded once at module level ---
_raw = None
_bundle = None


def _load_raw():
    global _raw
    if _raw is None:
        with open(GROK_INPUT, "r", encoding="utf-8") as f:
            _raw = json.load(f)
    return _raw


def _load_bundle():
    global _bundle
    if _bundle is None:
        with open(MIMO_OUTPUT, "r", encoding="utf-8") as f:
            _bundle = json.load(f)
    return _bundle


# ===========================================================================
# 1. Input file existence
# ===========================================================================
class TestInputExists(unittest.TestCase):
    def test_grok_input_file_exists(self):
        self.assertTrue(os.path.isfile(GROK_INPUT), f"Grok input not found: {GROK_INPUT}")

    def test_mimo_output_file_exists(self):
        self.assertTrue(os.path.isfile(MIMO_OUTPUT), f"MIMO output not found: {MIMO_OUTPUT}")


# ===========================================================================
# 2. Artifact count > 0
# ===========================================================================
class TestArtifactCount(unittest.TestCase):
    def test_output_has_artifacts(self):
        bundle = _load_bundle()
        self.assertGreater(len(bundle["artifacts"]), 0, "Output must have at least 1 artifact")


# ===========================================================================
# 3. No NVIDIA / H200 content
# ===========================================================================
class TestNoNvidiaContent(unittest.TestCase):
    def test_no_nvidia_in_output(self):
        bundle = _load_bundle()
        full_text = json.dumps(bundle)
        self.assertNotIn("NVIDIA", full_text, "Output must not contain NVIDIA")
        self.assertNotIn("H200", full_text, "Output must not contain H200")
        self.assertNotIn("GPU", full_text, "Output must not contain GPU")


# ===========================================================================
# 4. performance_eligible is false
# ===========================================================================
class TestPerformanceEligible(unittest.TestCase):
    def test_performance_eligible_false(self):
        bundle = _load_bundle()
        self.assertFalse(
            bundle.get("performance_eligible"),
            "performance_eligible must be False",
        )


# ===========================================================================
# 5. source_job_id == GROK-INTEL-001
# ===========================================================================
class TestSourceJobId(unittest.TestCase):
    def test_source_job_id(self):
        bundle = _load_bundle()
        self.assertEqual(bundle["handoff"]["source_job_id"], "GROK-INTEL-001")


# ===========================================================================
# 6. Hash recomputation matches
# ===========================================================================
class TestHashRecomputation(unittest.TestCase):
    def test_artifact_hashes_recomputable(self):
        bundle = _load_bundle()
        for i, art in enumerate(bundle["artifacts"]):
            stored = art["artifact_hash"]
            # Recompute: remove artifact_hash, hash the rest
            art_copy = {k: v for k, v in art.items() if k != "artifact_hash"}
            recomputed = _sha256_64(_canonical_json(art_copy))
            self.assertEqual(
                stored, recomputed,
                f"artifact[{i}] ({art.get('artifact_id')}): stored hash != recomputed",
            )

    def test_bundle_hash_recomputable(self):
        bundle = _load_bundle()
        stored = bundle["artifact_hash"]
        bundle_copy = {k: v for k, v in bundle.items() if k != "artifact_hash"}
        recomputed = _sha256_64(_canonical_json(bundle_copy))
        self.assertEqual(stored, recomputed, "Bundle hash mismatch on recomputation")

    def test_all_hashes_are_64_chars(self):
        bundle = _load_bundle()
        self.assertEqual(len(bundle["artifact_hash"]), 64)
        for i, art in enumerate(bundle["artifacts"]):
            self.assertEqual(
                len(art["artifact_hash"]), 64,
                f"artifact[{i}] hash is {len(art['artifact_hash'])} chars",
            )


# ===========================================================================
# 7. All 4 Grok artifact types preserved or mapped
# ===========================================================================
class TestGrokReportTypes(unittest.TestCase):
    def test_all_four_types_present(self):
        bundle = _load_bundle()
        present = bundle["handoff"]["grok_report_types_present"]
        for expected in [
            "ThemeDiscoveryReport",
            "ExternalResearchEvidence",
            "CaseStudyReport",
            "RedTeamReport",
        ]:
            self.assertIn(expected, present, f"Missing Grok report type: {expected}")

    def test_theme_artifacts_exist(self):
        bundle = _load_bundle()
        themes = [a for a in bundle["artifacts"] if a.get("grok_report_type") == "ThemeDiscoveryReport"]
        self.assertGreater(len(themes), 0, "No ThemeDiscoveryReport artifacts found")

    def test_evidence_artifacts_exist(self):
        bundle = _load_bundle()
        evs = [a for a in bundle["artifacts"] if a.get("grok_report_type") == "ExternalResearchEvidence"]
        self.assertGreater(len(evs), 0, "No ExternalResearchEvidence artifacts found")

    def test_case_artifacts_exist(self):
        bundle = _load_bundle()
        cases = [a for a in bundle["artifacts"] if a.get("grok_report_type") == "CaseStudyReport"]
        self.assertGreater(len(cases), 0, "No CaseStudyReport artifacts found")

    def test_redteam_artifacts_exist(self):
        bundle = _load_bundle()
        rts = [a for a in bundle["artifacts"] if a.get("grok_report_type") == "RedTeamReport"]
        self.assertGreater(len(rts), 0, "No RedTeamReport artifacts found")


# ===========================================================================
# 8. Specific crypto content preserved
# ===========================================================================
class TestCryptoContentPreserved(unittest.TestCase):
    def _full_text(self):
        return json.dumps(_load_bundle())

    def test_bonk_1000bonkusdt(self):
        t = self._full_text()
        self.assertIn("BONK", t)
        self.assertIn("1000BONKUSDT", t)

    def test_xlm(self):
        t = self._full_text()
        self.assertIn("XLM", t)

    def test_ada_l1(self):
        t = self._full_text()
        self.assertIn("ADA", t)

    def test_no_trade_flags_preserved(self):
        bundle = _load_bundle()
        arts_with_flags = [a for a in bundle["artifacts"] if a.get("no_trade_flags")]
        self.assertGreater(len(arts_with_flags), 0, "no_trade_flags missing from all artifacts")

    def test_cutoff_relation_preserved(self):
        bundle = _load_bundle()
        arts_with_cutoff = [a for a in bundle["artifacts"] if a.get("cutoff_relation")]
        self.assertGreater(len(arts_with_cutoff), 0, "cutoff_relation missing from all artifacts")

    def test_source_url_preserved(self):
        bundle = _load_bundle()
        arts_with_url = [a for a in bundle["artifacts"] if a.get("source_url")]
        self.assertGreater(len(arts_with_url), 0, "source_url missing from all artifacts")

    def test_published_at_utc_preserved(self):
        bundle = _load_bundle()
        arts_with_pub = [a for a in bundle["artifacts"] if a.get("published_at_utc")]
        self.assertGreater(len(arts_with_pub), 0, "published_at_utc missing from all artifacts")


# ===========================================================================
# 9. All artifacts tagged UNVERIFIED_EXTERNAL_EVIDENCE
# ===========================================================================
class TestUnverifiedTagging(unittest.TestCase):
    def test_all_artifacts_tagged(self):
        bundle = _load_bundle()
        for i, art in enumerate(bundle["artifacts"]):
            self.assertIn(
                UNVERIFIED_TAG, art.get("tags", []),
                f"artifact[{i}] ({art.get('artifact_id')}): missing UNVERIFIED tag",
            )


# ===========================================================================
# 10. No Long/Short conclusions
# ===========================================================================
class TestNoDirection(unittest.TestCase):
    def test_no_direction_field_in_bundle(self):
        """No artifact or top-level field should have a directional conclusion."""
        bundle = _load_bundle()
        self.assertNotIn("direction", bundle)
        self.assertNotIn("position", bundle)
        self.assertNotIn("recommendation", bundle)

    def test_no_direction_in_artifacts(self):
        """No artifact should have conclusion=LONG or SHORT."""
        bundle = _load_bundle()
        for art in bundle["artifacts"]:
            conclusion = art.get("conclusion", "")
            self.assertNotEqual(conclusion, "LONG", f"{art['artifact_id']} has LONG conclusion")
            self.assertNotEqual(conclusion, "SHORT", f"{art['artifact_id']} has SHORT conclusion")

    def test_no_paper_plan(self):
        bundle = _load_bundle()
        self.assertNotIn("paper_plan", bundle)
        self.assertNotIn("PaperPlan", json.dumps(bundle))


# ===========================================================================
# 11. Bundle validation passes
# ===========================================================================
class TestValidation(unittest.TestCase):
    def test_validate_bundle_passes(self):
        bundle = _load_bundle()
        errors = validate_bundle(bundle)
        self.assertEqual(errors, [], f"Validation errors: {errors}")


# ===========================================================================
# 12. Deterministic normalization
# ===========================================================================
class TestDeterminism(unittest.TestCase):
    def test_same_input_same_output(self):
        raw = _load_raw()
        raw_task_id = raw.get("task_id", "UNKNOWN")
        job_id = f"MIMO-EXT-{raw_task_id.replace('GROK-INTEL-', '')}"
        producer = "mimo-ext-002"
        source_job_id = raw_task_id
        observed = "2026-07-12T12:30:00Z"
        b1 = normalize_grok_bundle(raw, observed, task_id=job_id, job_id=job_id,
                                   producer=producer, source_job_id=source_job_id)
        b2 = normalize_grok_bundle(raw, observed, task_id=job_id, job_id=job_id,
                                   producer=producer, source_job_id=source_job_id)
        self.assertEqual(b1["artifact_hash"], b2["artifact_hash"])
        self.assertEqual(len(b1["artifacts"]), len(b2["artifacts"]))
        for a1, a2 in zip(b1["artifacts"], b2["artifacts"]):
            self.assertEqual(a1["artifact_hash"], a2["artifact_hash"])


if __name__ == "__main__":
    unittest.main()
