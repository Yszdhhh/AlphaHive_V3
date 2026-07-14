"""G1-G6 regression fixtures for the scanner and bounded gates."""
from __future__ import annotations

import hashlib
import importlib.util
import json
import tempfile
import unittest
from pathlib import Path

import pandas as pd
import yaml

PROJECT_ROOT = Path(__file__).resolve().parents[1]


def _load_scanner_module():
    path = PROJECT_ROOT / "scripts" / "02_scan_anomalies.py"
    spec = importlib.util.spec_from_file_location("alpha_hive_scan_anomalies", path)
    module = importlib.util.module_from_spec(spec)
    assert spec.loader is not None
    spec.loader.exec_module(module)
    return module


scanner = _load_scanner_module()

from harness.lib.cutoff import filter_completed_bars  # noqa: E402
from harness.lib.deep_research_package import (  # noqa: E402
    _evaluate_identity_gate,
    _evaluate_liquidity_gate,
    _resolve_paper_eligibility,
)
from harness.lib.derivative_metrics import compute_metric_summary  # noqa: E402
from harness.lib.derivative_metrics import coverage_status  # noqa: E402
from harness.lib.funding_normalize import (  # noqa: E402
    normalize_funding,
    normalized_funding_abs_max,
    raw_funding_hard_bounds,
)
from harness.lib.turnover import turnover_24h_effective  # noqa: E402


class TestScannerCutoffAndInventory(unittest.TestCase):
    def test_data_contract_declares_completed_bar_semantics(self):
        contract = yaml.safe_load(
            (PROJECT_ROOT / "config" / "data_contracts.yaml").read_text(encoding="utf-8")
        )
        semantics = contract["timestamp"]["completed_bar_semantics"]
        self.assertEqual(semantics["resolution"], "1h")
        self.assertEqual(semantics["rule"], "bar_open + 1h <= effective_cutoff")

    def test_completed_bar_excludes_forming_bar(self):
        hour = 60 * 60 * 1000
        frame = pd.DataFrame({"timestamp": [0, hour, 2 * hour], "close": [1.0, 2.0, 3.0]})
        kept, audit = filter_completed_bars(frame, effective_cutoff_ms=2 * hour)
        self.assertEqual(kept["timestamp"].tolist(), [0, hour])
        self.assertEqual(audit["filtered_incomplete_or_future_rows"], 1)
        self.assertEqual(audit["completed_bar_violations"], 0)
        self.assertEqual(audit["max_kept_bar_end_ms"], 2 * hour)

    def test_inventory_contains_hash_rows_range_and_step(self):
        frame = pd.DataFrame({"time": [0, 60 * 60 * 1000, 2 * 60 * 60 * 1000]})
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "fixture.parquet"
            path.write_bytes(b"inventory-fixture")
            entry = scanner._input_inventory_entry(path, frame, "fixture", "ETHUSDT", "time")
        self.assertEqual(entry["row_count"], 3)
        self.assertEqual(entry["earliest_time_ms"], 0)
        self.assertEqual(entry["latest_time_ms"], 2 * 60 * 60 * 1000)
        self.assertEqual(entry["median_time_step_ms"], 60 * 60 * 1000)
        self.assertEqual(entry["content_sha256"], hashlib.sha256(b"inventory-fixture").hexdigest())

    def test_derivatives_are_live_disabled_and_replay_is_date_bounded(self):
        rules = yaml.safe_load((PROJECT_ROOT / "config" / "scan_rules.yaml").read_text(encoding="utf-8"))
        policy = rules["derivatives"]["historical_replay"]
        self.assertEqual(scanner.derivative_use_mode(None, policy["max_scan_time_utc"]), "LIVE_DISABLED")
        self.assertEqual(
            scanner.derivative_use_mode("2026-05-11T12:00:00Z", policy["max_scan_time_utc"]),
            "HISTORICAL_REPLAY",
        )
        with self.assertRaises(ValueError):
            scanner.derivative_use_mode("2026-06-01T00:00:00Z", policy["max_scan_time_utc"])

    def test_live_disabled_merge_keeps_inventory_but_blanks_derivative_values(self):
        inventory = []
        base = pd.DataFrame({"timestamp": [0], "close": [1.0]})
        merged, summaries = scanner.merge_derivatives(
            base,
            "__NO_SUCH_SYMBOL__",
            effective_cutoff_ms=60 * 60 * 1000,
            lookback_hours=24,
            input_inventory=inventory,
            derivative_mode="LIVE_DISABLED",
        )
        self.assertEqual(summaries["oi"]["status"], "NOT_COMPUTED")
        self.assertEqual(summaries["oi"]["reason"], "LIVE_DERIVATIVE_USE_DISABLED")
        self.assertTrue(merged["oi_change_pct_24h"].isna().all())
        self.assertEqual({item["input_type"] for item in inventory}, {"funding_ohlc", "oi_ohlc"})


class TestFundingGuard(unittest.TestCase):
    def test_contract_has_one_hard_raw_bound_and_derived_normalized_max(self):
        self.assertEqual(raw_funding_hard_bounds(), (0.0008, 3.0))
        self.assertEqual(normalized_funding_abs_max(), 0.03)

    def test_normal_and_unit_error_fixtures(self):
        normal = pd.Series([0.005, -0.006, 0.004, -0.005, 0.003])
        normalized = normalize_funding(normal)
        self.assertAlmostEqual(float(normalized.abs().median()), float(normal.abs().median()) / 100.0)
        for bad in (
            pd.Series([0.00001] * 5),  # low 100x
            pd.Series([4.0] * 5),      # high 100x / contract overflow
            pd.Series([], dtype=float),
            pd.Series([0.0] * 5),
        ):
            with self.assertRaises(AssertionError):
                normalize_funding(bad)


class TestOpenInterestContract(unittest.TestCase):
    def test_change_is_unit_independent_ratio_and_absolute_unit_undeclared(self):
        contract = yaml.safe_load(
            (PROJECT_ROOT / "config" / "data_contracts.yaml").read_text(encoding="utf-8")
        )
        oi = contract["validations"]["open_interest"]
        change = oi["change_24h_pct"]
        self.assertEqual(change["field"], "oi_change_pct_24h")
        self.assertEqual(change["semantics"], "ratio_percent")
        self.assertTrue(change["unit_independent"])
        self.assertEqual(oi["absolute_value_status"], "NOT_DECLARED")
        self.assertEqual(oi["absolute_value_unit"], "NOT_DECLARED")


class TestSchemaV2Compatibility(unittest.TestCase):
    def test_v2_contract_is_additive_and_accepts_v1_consumers(self):
        contract = yaml.safe_load(
            (PROJECT_ROOT / "config" / "data_contracts.yaml").read_text(encoding="utf-8")
        )
        self.assertEqual(contract["schema_version"], "v2")
        self.assertEqual(contract["compatibility"]["previous_schema_versions"], ["v1"])
        self.assertEqual(contract["compatibility"]["unknown_fields"], "ignore")

        anomaly_schema = yaml.safe_load(
            (PROJECT_ROOT / "harness" / "schemas" / "anomaly_ledger_schema.yaml").read_text(encoding="utf-8")
        )
        self.assertEqual(anomaly_schema["schema_version"], "v2")
        self.assertEqual(anomaly_schema["compatibility"]["accepted_versions"], ["v1", "v2"])
        for field in ("oi_status", "funding_status", "input_inventory_status"):
            self.assertIn(field, anomaly_schema["fields"])


class TestKnownListV1(unittest.TestCase):
    def test_existing_universe_is_known_list_v1_with_bounded_selection(self):
        universe = json.loads((PROJECT_ROOT / "config" / "universe.json").read_text(encoding="utf-8"))
        known_list = universe["known_list"]
        self.assertEqual(known_list["version"], "v1")
        self.assertEqual(known_list["migration_history_status"], "NOT_AVAILABLE")
        selection = known_list["selection"]
        for symbol in universe["symbols"]:
            self.assertGreaterEqual(symbol["rank"], selection["rank_min"])
            self.assertLessEqual(symbol["rank"], selection["rank_max"])
            self.assertGreaterEqual(symbol["turnover_24h_usd"], selection["min_turnover_24h_usd"])


class TestTurnoverAndDerivativeStatus(unittest.TestCase):
    def test_partial_turnover_never_passes_valid_bar_gate(self):
        frame = pd.DataFrame({
            "timestamp": range(10),
            "close": [1.0] * 10,
            "volume": [1.0] * 10,
            "quote_volume": [500000.0] * 10,
        })
        result = turnover_24h_effective(frame, min_valid_bars=18, min_effective_turnover_usd=10_000_000)
        self.assertTrue(result.threshold_pass)
        self.assertFalse(result.valid_bar_pass)
        self.assertEqual(result.confidence, "partial")
        self.assertIn("VALID_BARS_BELOW_MINIMUM", result.reason)

    def test_derivative_status_is_not_computed_below_partial_coverage(self):
        hour = 60 * 60 * 1000
        frame = pd.DataFrame({
            "time": [i * hour for i in range(49)],
            "value": [1000.0 + i for i in range(49)],
        })
        summary, series = compute_metric_summary(
            frame, "oi_change_24h", "time", "value", effective_cutoff_ms=50 * hour,
            lookback_hours=2160, derive_24h_change=True,
        )
        self.assertEqual(summary["status"], "NOT_COMPUTED")
        self.assertGreater(summary["n_valid"], 0)
        self.assertIsNotNone(summary["quantile"])
        self.assertTrue((series["timestamp"] <= 50 * hour).all())

    def test_90d_coverage_policy_fixture(self):
        fixture = json.loads(
            (PROJECT_ROOT / "tests" / "fixtures" / "derivative_coverage_status.json").read_text(encoding="utf-8")
        )
        policy = fixture["coverage_policy"]
        for case in fixture["cases"]:
            coverage = case["valid_points"] / fixture["lookback_hours"]
            status, _ = coverage_status(coverage, policy)
            self.assertEqual(status, case["expected_status"], case["name"])

    def test_derivative_status_can_be_computed_with_sufficient_history(self):
        hour = 60 * 60 * 1000
        n_points = 1440
        frame = pd.DataFrame({
            "time": [i * hour for i in range(n_points)],
            "value": [1000.0 + i for i in range(n_points)],
        })
        summary, series = compute_metric_summary(
            frame, "funding", "time", "value", effective_cutoff_ms=2160 * hour,
            lookback_hours=2160, coverage_policy={"computed_min": 0.60, "partial_min": 0.30},
        )
        self.assertEqual(summary["status"], "COMPUTED")
        self.assertGreaterEqual(summary["coverage"], 0.60)
        self.assertTrue((series["timestamp"] <= 2160 * hour).all())

    def test_derivative_degenerate_and_nonmonotonic_are_not_computed(self):
        hour = 60 * 60 * 1000
        constant = pd.DataFrame({"time": [i * hour for i in range(4)], "value": [1.0] * 4})
        summary, _ = compute_metric_summary(constant, "funding", "time", "value", 4 * hour, 2160)
        self.assertEqual(summary["status"], "NOT_COMPUTED")
        self.assertEqual(summary["reason"], "DEGENERATE_CONSTANT_SERIES")
        nonmonotonic = pd.DataFrame({"time": [0, 2 * hour, hour], "value": [1.0, 2.0, 3.0]})
        summary, _ = compute_metric_summary(nonmonotonic, "funding", "time", "value", 3 * hour, 2160)
        self.assertEqual(summary["status"], "NOT_COMPUTED")
        self.assertIn("TIMESTAMP_NOT_MONOTONIC", summary["reason"])


class TestBoundedGates(unittest.TestCase):
    RULES = {"baseline_pool": {
        "min_effective_turnover_usd": 10_000_000,
        "min_valid_turnover_bars_24h": 18,
    }}
    MANIFEST = {
        "bar_resolution": "1h",
        "resolved_effective_cutoff_ms": 123,
        "integrity": {"no_lookahead_attested": True},
    }

    def _candidate(self, **overrides):
        value = {
            "symbol": "ETHUSDT",
            "eligible_for_paper": "yes",
            "history_tier": "Full",
            "turnover_24h_usd": 12_000_000,
        }
        value.update(overrides)
        return value

    def _meta(self, **overrides):
        value = {
            "symbol": "ETHUSDT",
            "contract_identity": "ETHUSDT_PERP",
            "turnover_24h_usd_effective": 12_000_000,
            "n_valid_bars": 22,
        }
        value.update(overrides)
        return value

    def test_bounded_pass_still_review_and_marks_missing_microstructure(self):
        candidate = self._candidate()
        meta = self._meta()
        identity = _evaluate_identity_gate(candidate, meta, known_symbols=["ETHUSDT"])
        liquidity = _evaluate_liquidity_gate(candidate, meta, self.RULES, self.MANIFEST)
        paper = _resolve_paper_eligibility(candidate, identity, liquidity, [], [], [])
        self.assertEqual(identity["status"], "WARN")
        self.assertEqual(liquidity["status"], "WARN")
        self.assertEqual(liquidity["spread_status"], "NOT_AVAILABLE")
        self.assertEqual(liquidity["depth_status"], "NOT_AVAILABLE")
        self.assertEqual(paper["status"], "REVIEW_REQUIRED")
        self.assertFalse(paper["owner_override_allowed"])

    def test_low_turnover_and_unknown_symbol_block(self):
        low = self._candidate(turnover_24h_usd=9_000_000)
        low_meta = self._meta(turnover_24h_usd_effective=9_000_000)
        liquidity = _evaluate_liquidity_gate(low, low_meta, self.RULES, self.MANIFEST)
        self.assertEqual(liquidity["status"], "BLOCK")
        self.assertIn("turnover_below_minimum", liquidity["blockers"])
        unknown = self._candidate(symbol="UNKNOWNUSDT")
        identity = _evaluate_identity_gate(unknown, self._meta(), known_symbols=["ETHUSDT"])
        self.assertEqual(identity["status"], "BLOCK")
        self.assertIn("symbol_not_in_known_list", identity["blockers"])

    def test_missing_identity_field_blocks(self):
        identity = _evaluate_identity_gate(self._candidate(), self._meta(contract_identity=None), known_symbols=["ETHUSDT"])
        self.assertEqual(identity["status"], "BLOCK")
        self.assertIn("missing_contract_identity", identity["blockers"])


if __name__ == "__main__":
    unittest.main()
