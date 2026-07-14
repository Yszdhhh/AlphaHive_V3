"""
单元测试：DeepResearchPromptPackage v1（第二轮返工）
覆盖：
  - P0: 有效 cutoff 严格语义
  - P0: manifest cutoff > scan → BLOCK，但 effective 仍取 scan
  - P0: cutoff == scan → 合法
  - P0: 无 manifest cutoff → effective = scan，cutoff 后行 BLOCK
  - P0: 所有 snapshot 行必须 <= effective_cutoff_ms
  - P0: 未来价格 999 在包/prompt 中 0 次出现
  - P1: 稳定的 candidate_metrics
  - P1: 固定 trigger UI 契约
  - P1: scan_time 非法时 fail closed
  - 真实 run 只读探针
"""
from __future__ import annotations

import builtins
import hashlib
import json
import os
import sys
import time
import unittest
from datetime import datetime, timezone
from pathlib import Path
from unittest.mock import patch

PROJECT_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(PROJECT_ROOT))

from harness.lib.deep_research_package import (  # noqa: E402
    SCHEMA_VERSION,
    TEMPLATE_VERSION,
    GENERATOR_VERSION,
    VALID_MODES,
    DENYLIST_FIELDS,
    ALLOWED_CANDIDATE_FIELDS,
    ALLOWED_MARKET_SNAPSHOT_FIELDS,
    ALLOWED_CANDIDATE_METRICS_FIELDS,
    TRIGGER_CATALOG,
    _parse_ts_to_ms,
    _normalize_snapshot_row,
    _resolve_effective_cutoff,
    _enforce_cutoff,
    _safe_float,
    _is_missing,
    _funding_display,
    _market_snapshot_from_safe_rows,
    _build_candidate_metrics,
    build_signal_explanations,
    evaluate_quality_gate,
    build_prompt_package,
    render_research_prompt,
    hash_prompt_package,
)

# ---------------------------------------------------------------------------
# Fixtures（来自真实 contract + scan_rules + presets）
# ---------------------------------------------------------------------------

SCAN_RULES = {
    "triggers": {
        "vol_quantile_high": 0.90,
        "vol_quantile_low": 0.10,
        "oi_change_quantile_high": 0.90,
        "funding_quantile_high": 0.90,
        "funding_quantile_low": 0.10,
    },
    "large_move": {
        "large_move_threshold_abs_pct_24h": 10.0,
        "large_move_threshold_excess_pct_24h": 7.0,
    },
}

DEEP_RESEARCH_CONTRACT = {
    "schema_version": "deep_research_prompt_package_v1",
    "mandatory_research_sections": [
        "instrument_identity_and_contract_status",
        "data_integrity_and_cross_market_consistency",
        "cutoff_safe_event_timeline",
        "btc_and_sector_beta_assessment",
        "derivatives_positioning_and_missing_data",
        "liquidity_and_execution_risk",
        "continuation_hypothesis",
        "reversal_hypothesis",
        "mean_reversion_hypothesis",
        "data_artifact_hypothesis",
        "no_trade_evidence",
        "falsifiable_conditions",
        "missing_evidence",
        "citations",
        "owner_checklist",
    ],
    "prohibited_actions": [
        "place_or_prepare_live_order",
        "treat_anomaly_as_validated_alpha",
        "invent_missing_oi_funding_spread_or_depth",
        "use_post_cutoff_market_performance_as_evidence",
        "infer_direction_from_funding_sign_alone",
        "override_local_risk_limits",
        "不得复活 GRAVEYARD.md 所列已证伪方向（carry/庄家-费率/跟随聪明钱/机械方向择时）作为交易机制建议",
    ],
    "expected_output": {
        "overall_evidence": {"allowed": ["CONTINUATION_EVIDENCE_STRONGER", "REVERSAL_EVIDENCE_STRONGER", "MEAN_REVERSION_EVIDENCE_STRONGER", "DATA_ARTIFACT_LIKELY", "MIXED", "NO_TRADE_BLOCKER", "INSUFFICIENT_EVIDENCE"]},
        "required_fields": {},
    },
}

RISK_PRESETS = {
    "schema_version": "paper_execution_presets_v1",
    "preset_version": "v0.1.0-draft",
    "status": "DRAFT",
    "scope": "PAPER_ONLY",
    "presets": {
        "conservative": {},
        "standard": {},
        "exploratory": {},
    },
}

CLEAN_RUN = {
    "run_id": "20260511_1200_utc_replay",
    "status": "clean",
    "eligible_for_judgment": True,
    "hashes": {},
}

DIRTY_RUN = {
    "run_id": "20260707_0346_utc",
    "status": "dirty",
    "eligible_for_judgment": False,
    "hashes": {},
}

QUARANTINED_RUN = {
    "run_id": "20260707_0912_utc",
    "status": "quarantined",
    "eligible_for_judgment": False,
    "hashes": {"input_snapshot_sha256": "28f5f90f196a5de5de9b28a62b929647b4bc4fc3ad1a1da8608e528503ba37c2"},
}

# ---------------------------------------------------------------------------
# 真实 manifest 数据（来自 run_manifest.json）
# scan_time_utc = 2026-05-11T12:00:00+00:00 → scan_ms = 1778500800000
# data_cutoff = 1778497200000 = 2026-05-11T11:00:00+00:00（cutoff < scan，合法）
# snapshot max ts = 1778497200000（cutoff 前最后一根）
# ---------------------------------------------------------------------------
REAL_SCAN_TIME_UTC = "2026-05-11T12:00:00+00:00"
REAL_SCAN_MS = 1778500800000
REAL_CUTOFF_MS = 1778497200000  # cutoff < scan
REAL_SNAPSHOT_MAX_TS = 1778497200000

CLEAN_MANIFEST = {
    "run_id": "20260511_1200_utc_replay",
    "scan_time_utc": REAL_SCAN_TIME_UTC,
    "data_cutoff": REAL_CUTOFF_MS,
    "snapshot_sha256": "98a0b581ff813164ba10019fc8cb0858f4e3c9cae6468c4d92d37d828b3d3d6c",
    "symbol_meta_sha256": "test_meta",
    "return_tape_sha256": "1969bd4a593bb24c8680ce5e1910225a564d0e9dd166fabbfab4489c67ff8c74",
    "benchmark_symbol": "BTCUSDT",
    "benchmark_frozen_in_snapshot": True,
    "candidate_count": 19,
    "integrity": {"no_lookahead_attested": True, "snapshot_is_90d_long_table": True},
}

# cutoff > scan（未来数据嫌疑）
MANIFEST_CUTOFF_AFTER_SCAN = {
    **CLEAN_MANIFEST,
    "data_cutoff": 1778515200000,  # scan+2h
}

# cutoff == scan（合法）
MANIFEST_CUTOFF_EQUALS_SCAN = {
    **CLEAN_MANIFEST,
    "data_cutoff": REAL_SCAN_MS,
}

# 无 cutoff
MANIFEST_NO_CUTOFF = {
    **CLEAN_MANIFEST,
    "data_cutoff": None,
}

MANIFEST_HASH_MISMATCH = {
    **CLEAN_MANIFEST,
    "snapshot_sha256": "deadbeefdeadbeefdeadbeefdeadbeefdeadbeefdeadbeefdeadbeefdeadbeef",
}

SYMBOL_META = {
    "symbol": "ETHUSDT",
    "contract_identity": "ETHUSDT_PERP",
    "turnover_24h_usd_effective": 12500000000.0,
    "n_valid_bars": 22,
    "confidence": 0.9,
}

CANDIDATE_ALL_TRIGGERS = {
    "schema_version": "v1",
    "run_id": "20260511_1200_utc_replay",
    "record_id": "20260511_1200_utc_replay_0001",
    "scan_time_utc": REAL_SCAN_TIME_UTC,
    "symbol": "ETHUSDT",
    "rank": 1,
    "turnover_24h_usd": 12500000000.0,
    "history_tier": "Full",
    "eligible_for_paper": "yes",
    "trigger_reason": "vol_quantile_high|large_move_abs|large_move_excess",
    "trigger_metric": "vol_24h",
    "trigger_value": 0.045,
    "trigger_quantile": 0.95,
    "large_move_flag_24h": True,
    "abs_move_pct_24h": 12.5,
    "excess_move_pct_24h": 8.3,
    "funding_sign": "positive",
    "funding_rate_8h": 0.00025,
    "open_interest": 1000000.0,
    "oi_change_pct_24h": None,
    "is_top_candidate": True,
    "decision": "Watch",
    "direction": "",
    "direction_sign": 0,
}

# 快照行（时间戳均 <= REAL_CUTOFF_MS = 1778497200000 = 2026-05-11T11:00:00Z）
SNAPSHOT_ROWS = [
    {"timestamp": 1778476800000, "open": 3200.0, "high": 3250.0, "low": 3180.0,
     "close": 3220.0, "volume": 150000.0, "turnover_usd": 483000000.0,
     "funding_rate_8h": 0.00015, "open_interest": 5000000.0, "symbol": "ETHUSDT"},
    {"timestamp_utc": 1778480400000, "open": 3220.0, "high": 3280.0, "low": 3210.0,
     "close": 3260.0, "volume": 160000.0, "turnover_usd": 521600000.0,
     "funding_rate_8h": 0.00018, "open_interest": 5100000.0, "symbol": "ETHUSDT"},
    {"timestamp": 1778493600000, "open": 3480.0, "high": 3520.0, "low": 3450.0,
     "close": 3500.0, "volume": 190000.0, "turnover_usd": 665000000.0,
     "funding_rate_8h": 0.00022, "open_interest": 5400000.0, "symbol": "ETHUSDT"},
    # BTCUSDT 基准
    {"timestamp_utc": 1778493600000, "open": 64800.0, "high": 65200.0, "low": 64400.0,
     "close": 65000.0, "volume": 5000.0, "turnover_usd": 325000000.0,
     "funding_rate_8h": 0.00005, "open_interest": 12000000.0, "symbol": "BTCUSDT"},
]

GENERATED_AT = "2026-07-11T00:00:00Z"


# ---------------------------------------------------------------------------
# 辅助
# ---------------------------------------------------------------------------

def _build_default(
    candidate=None,
    run_info=None,
    manifest=None,
    snapshot_rows=None,
    mode="HISTORICAL_REPLAY",
    generated_at_utc=None,
):
    cand = candidate or CANDIDATE_ALL_TRIGGERS.copy()
    ri = run_info or CLEAN_RUN.copy()
    mf = manifest or CLEAN_MANIFEST.copy()
    rows = snapshot_rows or SNAPSHOT_ROWS.copy()
    return build_prompt_package(
        cand, ri, mf, SYMBOL_META,
        SCAN_RULES, DEEP_RESEARCH_CONTRACT, RISK_PRESETS,
        rows, mode=mode, generated_at_utc=generated_at_utc or GENERATED_AT,
    )


# ===========================================================================
# TestEffectiveCutoff（P0 核心）
# ===========================================================================

class TestEffectiveCutoff(unittest.TestCase):

    def test_cutoff_less_than_scan(self):
        """cutoff < scan → effective = cutoff，合法不 BLOCK。"""
        pkg = _build_default(manifest=CLEAN_MANIFEST)
        self.assertEqual(pkg["market_data_cutoff"], REAL_CUTOFF_MS)
        self.assertEqual(pkg["effective_market_data_cutoff"], REAL_CUTOFF_MS)
        self.assertEqual(pkg["quality_gate"]["status"], "WARN")

    def test_cutoff_equals_scan(self):
        """cutoff == scan → 合法，不产生 cutoff-after-scan blocker。"""
        pkg = _build_default(manifest=MANIFEST_CUTOFF_EQUALS_SCAN)
        self.assertEqual(pkg["effective_market_data_cutoff"], REAL_SCAN_MS)
        blockers = pkg["quality_gate"]["blockers"]
        self.assertFalse(
            any("cutoff_after_scan" in b for b in blockers),
            f"cutoff==scan should not block, got: {blockers}"
        )

    def test_cutoff_greater_than_scan_blocks(self):
        """cutoff > scan → BLOCK，但 effective cutoff 仍取 scan_ms。"""
        pkg = _build_default(manifest=MANIFEST_CUTOFF_AFTER_SCAN, mode="HISTORICAL_REPLAY")
        self.assertEqual(pkg["quality_gate"]["status"], "BLOCK")
        self.assertTrue(
            any("cutoff_after_scan" in b for b in pkg["quality_gate"]["blockers"]),
            f"Expected cutoff blocker, got: {pkg['quality_gate']['blockers']}"
        )
        # effective 仍取 scan_ms
        self.assertEqual(pkg["effective_market_data_cutoff"], REAL_SCAN_MS)

    def test_no_manifest_cutoff_uses_scan(self):
        """无 manifest cutoff → effective = scan_ms，cutoff 后行 BLOCK。"""
        pkg = _build_default(manifest=MANIFEST_NO_CUTOFF)
        self.assertEqual(pkg["effective_market_data_cutoff"], REAL_SCAN_MS)
        # SNAPSHOT_ROWS 全部 <= REAL_CUTOFF_MS < REAL_SCAN_MS，应全部通过
        self.assertIsNotNone(pkg["target_market_snapshot"]["last_close"])

    def test_scan_time_unparseable_fails_closed(self):
        """scan_time_utc 无法解析 → fail closed，抛 ValueError。"""
        bad_candidate = {**CANDIDATE_ALL_TRIGGERS, "scan_time_utc": "not-a-time"}
        with self.assertRaises(ValueError):
            _build_default(candidate=bad_candidate)

    def test_post_cutoff_row_triggers_block(self):
        """snapshot 中出现 cutoff 后行 → 该行被过滤 + quality BLOCK。"""
        future_ts = REAL_SCAN_MS + 3600000  # scan + 1h
        future_row = {
            "timestamp": future_ts,
            "open": 3300.0, "high": 3350.0, "low": 3290.0, "close": 3330.0,
            "volume": 100000.0, "turnover_usd": 333000000.0,
            "funding_rate_8h": 0.0002, "open_interest": 5200000.0,
            "symbol": "ETHUSDT",
        }
        rows = SNAPSHOT_ROWS + [future_row]
        pkg = _build_default(snapshot_rows=rows)
        # 未来行被过滤
        pkg_str = json.dumps(pkg, ensure_ascii=False)
        self.assertNotIn(str(future_ts), pkg_str)
        # quality BLOCK
        self.assertEqual(pkg["quality_gate"]["status"], "BLOCK")
        self.assertTrue(
            any("post_cutoff" in b for b in pkg["quality_gate"]["blockers"]),
            f"Expected post_cutoff blocker, got: {pkg['quality_gate']['blockers']}"
        )

    def test_post_cutoff_data_not_in_package(self):
        """cutoff 后价格、funding、OI 不得进入 package。"""
        future_ts = REAL_SCAN_MS + 7200000
        future_row = {
            "timestamp": future_ts,
            "open": 9999.0, "high": 9999.0, "low": 9999.0, "close": 9999.0,
            "volume": 99999.0, "turnover_usd": 999999.0,
            "funding_rate_8h": 0.999, "open_interest": 99999.0,
            "symbol": "ETHUSDT",
        }
        pkg = _build_default(snapshot_rows=SNAPSHOT_ROWS + [future_row])
        pkg_str = json.dumps(pkg, ensure_ascii=False)
        self.assertNotIn("9999", pkg_str)
        self.assertNotIn("0.999", pkg_str)
        # 合法数据仍在
        self.assertIn("3500.0", pkg_str)

    def test_post_cutoff_data_not_in_prompt(self):
        """cutoff 后数据不得进入 rendered prompt。"""
        future_ts = REAL_SCAN_MS + 7200000
        future_row = {
            "timestamp": future_ts,
            "open": 9999.0, "high": 9999.0, "low": 9999.0, "close": 9999.0,
            "volume": 99999.0, "turnover_usd": 999999.0,
            "funding_rate_8h": 0.999, "open_interest": 99999.0,
            "symbol": "ETHUSDT",
        }
        pkg = _build_default(snapshot_rows=SNAPSHOT_ROWS + [future_row])
        prompt = render_research_prompt(pkg)
        self.assertNotIn("9999", prompt)
        self.assertNotIn("0.999", prompt)


class TestNoCutoff999Injection(unittest.TestCase):
    """场景 1：无 manifest cutoff，注入 scan 后价格 999。"""

    def test_999_not_in_package_no_cutoff(self):
        ts_future = REAL_SCAN_MS + 86400000
        rows = SNAPSHOT_ROWS + [{
            "timestamp": ts_future, "open": 999.0, "high": 999.0, "low": 999.0,
            "close": 999.0, "volume": 1.0, "turnover_usd": 999.0,
            "funding_rate_8h": 0.0, "open_interest": 0.0, "symbol": "ETHUSDT",
        }]
        pkg = _build_default(snapshot_rows=rows, manifest=MANIFEST_NO_CUTOFF)
        self.assertNotIn("999", json.dumps(pkg))
        self.assertEqual(pkg["quality_gate"]["status"], "BLOCK")

    def test_999_not_in_prompt_no_cutoff(self):
        ts_future = REAL_SCAN_MS + 86400000
        rows = SNAPSHOT_ROWS + [{
            "timestamp": ts_future, "open": 999.0, "high": 999.0, "low": 999.0,
            "close": 999.0, "volume": 1.0, "turnover_usd": 999.0,
            "funding_rate_8h": 0.0, "open_interest": 0.0, "symbol": "ETHUSDT",
        }]
        pkg = _build_default(snapshot_rows=rows, manifest=MANIFEST_NO_CUTOFF)
        prompt = render_research_prompt(pkg)
        self.assertNotIn("999", prompt)


class TestLiveCutoffAfterScan(unittest.TestCase):
    """场景 2：Live mode，manifest cutoff = scan + 2h，注入 scan + 1h 价格 777。"""

    def test_777_not_in_package_live(self):
        ts_future = REAL_SCAN_MS + 3600000  # scan + 1h
        rows = SNAPSHOT_ROWS + [{
            "timestamp": ts_future, "open": 777.0, "high": 777.0, "low": 777.0,
            "close": 777.0, "volume": 1.0, "turnover_usd": 777.0,
            "funding_rate_8h": 0.0, "open_interest": 0.0, "symbol": "ETHUSDT",
        }]
        live_manifest = {**MANIFEST_CUTOFF_AFTER_SCAN, "data_cutoff": REAL_SCAN_MS + 7200000}
        pkg = build_prompt_package(
            CANDIDATE_ALL_TRIGGERS, CLEAN_RUN, live_manifest, SYMBOL_META,
            SCAN_RULES, DEEP_RESEARCH_CONTRACT, RISK_PRESETS,
            rows, mode="PROSPECTIVE_LIVE", generated_at_utc=GENERATED_AT,
        )
        self.assertNotIn("777", json.dumps(pkg))
        self.assertEqual(pkg["quality_gate"]["status"], "BLOCK")
        self.assertEqual(pkg["effective_market_data_cutoff"], REAL_SCAN_MS)

    def test_777_not_in_prompt_live(self):
        ts_future = REAL_SCAN_MS + 3600000
        rows = SNAPSHOT_ROWS + [{
            "timestamp": ts_future, "open": 777.0, "high": 777.0, "low": 777.0,
            "close": 777.0, "volume": 1.0, "turnover_usd": 777.0,
            "funding_rate_8h": 0.0, "open_interest": 0.0, "symbol": "ETHUSDT",
        }]
        live_manifest = {**MANIFEST_CUTOFF_AFTER_SCAN, "data_cutoff": REAL_SCAN_MS + 7200000}
        pkg = build_prompt_package(
            CANDIDATE_ALL_TRIGGERS, CLEAN_RUN, live_manifest, SYMBOL_META,
            SCAN_RULES, DEEP_RESEARCH_CONTRACT, RISK_PRESETS,
            rows, mode="PROSPECTIVE_LIVE", generated_at_utc=GENERATED_AT,
        )
        prompt = render_research_prompt(pkg)
        self.assertNotIn("777", prompt)


class TestCutoffEqualsScan(unittest.TestCase):
    """场景 3：manifest cutoff == scan → 不产生 cutoff-after-scan blocker。"""

    def test_cutoff_equals_scan_no_blocker(self):
        pkg = _build_default(manifest=MANIFEST_CUTOFF_EQUALS_SCAN)
        blockers = pkg["quality_gate"]["blockers"]
        self.assertFalse(
            any("cutoff_after_scan" in b for b in blockers),
            f"cutoff==scan should not produce blocker, got: {blockers}"
        )
        self.assertEqual(pkg["effective_market_data_cutoff"], REAL_SCAN_MS)


class TestNormalCutoffPostFilter(unittest.TestCase):
    """场景 4：正常 cutoff 后出现任意一行 → 被过滤 + BLOCK。"""

    def test_post_cutoff_row_filtered_and_block(self):
        future_ts = REAL_CUTOFF_MS + 600000  # cutoff + 10min
        future_row = {
            "timestamp": future_ts,
            "open": 4000.0, "high": 4050.0, "low": 3990.0, "close": 4020.0,
            "volume": 100000.0, "turnover_usd": 402000000.0,
            "funding_rate_8h": 0.0003, "open_interest": 5600000.0,
            "symbol": "ETHUSDT",
        }
        pkg = _build_default(snapshot_rows=SNAPSHOT_ROWS + [future_row])
        pkg_str = json.dumps(pkg, ensure_ascii=False)
        self.assertNotIn(str(future_ts), pkg_str)
        self.assertEqual(pkg["quality_gate"]["status"], "BLOCK")
        self.assertIsNotNone(pkg["target_market_snapshot"]["last_close"])

    def test_post_cutoff_filtered_exactly_once(self):
        """post_cutoff_rows_filtered 在 blockers 中恰好出现一次（不重复）。"""
        future_ts = REAL_CUTOFF_MS + 600000
        future_row = {
            "timestamp": future_ts,
            "open": 4000.0, "high": 4050.0, "low": 3990.0, "close": 4020.0,
            "volume": 100000.0, "turnover_usd": 402000000.0,
            "funding_rate_8h": 0.0003, "open_interest": 5600000.0,
            "symbol": "ETHUSDT",
        }
        pkg = _build_default(snapshot_rows=SNAPSHOT_ROWS + [future_row])
        blockers = pkg["quality_gate"]["blockers"]
        count = sum(1 for b in blockers if "post_cutoff_rows_filtered" in b)
        self.assertEqual(count, 1, f"post_cutoff_rows_filtered appears {count} times, expected exactly 1: {blockers}")
        # future row's timestamp not in package
        pkg_str = json.dumps(pkg, ensure_ascii=False)
        self.assertNotIn(str(future_ts), pkg_str)
        self.assertEqual(pkg["quality_gate"]["status"], "BLOCK")


class TestScanTimeInvalid(unittest.TestCase):
    """场景 5：scan_time 非法 → fail closed。"""

    def test_unparseable_scan_time_raises(self):
        bad = {**CANDIDATE_ALL_TRIGGERS, "scan_time_utc": "garbage"}
        with self.assertRaises(ValueError):
            _build_default(candidate=bad)

    def test_none_scan_time_raises(self):
        bad = {**CANDIDATE_ALL_TRIGGERS, "scan_time_utc": None}
        with self.assertRaises(ValueError):
            _build_default(candidate=bad)


class TestReplayLiveSameCutoff(unittest.TestCase):
    """场景 6：replay/live 使用完全相同的市场数据截断规则。"""

    def test_same_effective_cutoff_both_modes(self):
        rows = SNAPSHOT_ROWS + [{
            "timestamp": REAL_SCAN_MS + 3600000,
            "close": 9999.0, "symbol": "ETHUSDT", "open": 9999.0,
            "high": 9999.0, "low": 9999.0, "volume": 1.0,
            "turnover_usd": 1.0, "funding_rate_8h": 0.999, "open_interest": 1.0,
        }]
        pkg_replay = build_prompt_package(
            CANDIDATE_ALL_TRIGGERS, CLEAN_RUN, CLEAN_MANIFEST, SYMBOL_META,
            SCAN_RULES, DEEP_RESEARCH_CONTRACT, RISK_PRESETS,
            rows, mode="HISTORICAL_REPLAY", generated_at_utc=GENERATED_AT,
        )
        pkg_live = build_prompt_package(
            CANDIDATE_ALL_TRIGGERS, CLEAN_RUN, CLEAN_MANIFEST, SYMBOL_META,
            SCAN_RULES, DEEP_RESEARCH_CONTRACT, RISK_PRESETS,
            rows, mode="PROSPECTIVE_LIVE", generated_at_utc=GENERATED_AT,
        )
        self.assertEqual(
            pkg_replay["effective_market_data_cutoff"],
            pkg_live["effective_market_data_cutoff"]
        )
        self.assertEqual(pkg_replay["quality_gate"]["status"], "BLOCK")
        self.assertEqual(pkg_live["quality_gate"]["status"], "BLOCK")


# ===========================================================================
# TestDeepResearchPackage（原有测试，更新断言）
# ===========================================================================

class TestDeepResearchPackage(unittest.TestCase):

    def test_schema_version_contract(self):
        self.assertEqual(SCHEMA_VERSION, "deep_research_prompt_package_v1")

    def test_template_version(self):
        self.assertEqual(TEMPLATE_VERSION, "v1")

    def test_generator_version(self):
        self.assertIn("deep_research_package", GENERATOR_VERSION)

    def test_package_required_fields(self):
        pkg = _build_default()
        for key in [
            "schema_version", "package_id", "template_version", "generator_version",
            "generated_at_utc", "package_hash",
            "run_id", "record_id", "symbol", "scan_time_utc",
            "market_data_cutoff", "effective_market_data_cutoff", "snapshot_sha256",
            "mode", "run_status", "eligible_for_judgment", "eligible_for_paper",
            "quality_gate", "ranking_method", "trigger_items", "no_direction_claim",
            "target_market_snapshot", "btc_market_snapshot", "excess_24h",
            "candidate_metrics",
            "mandatory_research_sections", "competition_hypotheses",
            "prohibited_actions", "expected_output_schema",
            "risk_policy_reference", "checkpoint_hash",
            "historical_replay_qualitative_only",
        ]:
            self.assertIn(key, pkg, f"missing: {key}")

    def test_no_direction_claim_true(self):
        pkg = _build_default()
        self.assertTrue(pkg["no_direction_claim"])

    def test_ranking_method(self):
        pkg = _build_default()
        self.assertIn("excess_move_pct_24h", pkg["ranking_method"])

    def test_future_price_999_not_in_package(self):
        ts_future = REAL_SCAN_MS + 86400000
        rows_with_999 = SNAPSHOT_ROWS + [{
            "timestamp": ts_future, "open": 999.0, "high": 999.0, "low": 999.0,
            "close": 999.0, "volume": 1.0, "turnover_usd": 999.0,
            "funding_rate_8h": 0.0, "open_interest": 0.0, "symbol": "ETHUSDT",
        }]
        pkg = _build_default(snapshot_rows=rows_with_999)
        self.assertNotIn("999", json.dumps(pkg))

    def test_future_price_999_not_in_prompt(self):
        ts_future = REAL_SCAN_MS + 86400000
        rows_with_999 = SNAPSHOT_ROWS + [{
            "timestamp": ts_future, "open": 999.0, "high": 999.0, "low": 999.0,
            "close": 999.0, "volume": 1.0, "turnover_usd": 999.0,
            "funding_rate_8h": 0.0, "open_interest": 0.0, "symbol": "ETHUSDT",
        }]
        pkg = _build_default(snapshot_rows=rows_with_999)
        prompt = render_research_prompt(pkg)
        self.assertNotIn("999", prompt)

    def test_post_cutoff_in_prompt_filtered(self):
        future_ts = REAL_SCAN_MS + 86400000
        future_row = {
            "timestamp": future_ts, "open": 9999.0, "close": 9999.0,
            "high": 9999.0, "low": 9999.0, "volume": 1.0,
            "turnover_usd": 1.0, "funding_rate_8h": 0.999,
            "open_interest": 1.0, "symbol": "ETHUSDT",
        }
        pkg = _build_default(snapshot_rows=SNAPSHOT_ROWS + [future_row])
        prompt = render_research_prompt(pkg)
        self.assertNotIn("9999", prompt)
        self.assertNotIn("0.999", prompt)

    def test_cutoff_after_scan_blocks_in_replay(self):
        """cutoff > scan → BLOCK (not ValueError). effective cutoff = scan_ms."""
        pkg = _build_default(manifest=MANIFEST_CUTOFF_AFTER_SCAN, mode="HISTORICAL_REPLAY")
        self.assertEqual(pkg["quality_gate"]["status"], "BLOCK")
        self.assertEqual(pkg["effective_market_data_cutoff"], REAL_SCAN_MS)
        # scan-time data (SNAPSHOT_ROWS) still enters package since effective cutoff = scan_ms
        self.assertIsNotNone(pkg["target_market_snapshot"]["last_close"])

    def test_cutoff_after_scan_blocks_in_live_too(self):
        pkg = _build_default(manifest=MANIFEST_CUTOFF_AFTER_SCAN, mode="PROSPECTIVE_LIVE")
        self.assertEqual(pkg["quality_gate"]["status"], "BLOCK")
        self.assertTrue(
            any("cutoff" in b.lower() or "future" in b.lower()
                for b in pkg["quality_gate"]["blockers"]),
        )

    def test_cutoff_in_package(self):
        pkg = _build_default()
        self.assertEqual(pkg["market_data_cutoff"], REAL_CUTOFF_MS)
        self.assertEqual(pkg["effective_market_data_cutoff"], REAL_CUTOFF_MS)

    def test_denylist_in_package(self):
        pkg = _build_default()
        pkg_str = json.dumps(pkg, ensure_ascii=False)
        for field in DENYLIST_FIELDS:
            self.assertNotIn(field, pkg_str, f"denylist leak: {field}")

    def test_denylist_in_prompt(self):
        pkg = _build_default()
        prompt = render_research_prompt(pkg)
        for field in DENYLIST_FIELDS:
            self.assertNotIn(field, prompt, f"denylist leak in prompt: {field}")

    def test_different_mode_different_hash(self):
        p1 = _build_default(mode="HISTORICAL_REPLAY")
        p2 = _build_default(mode="PROSPECTIVE_LIVE")
        self.assertNotEqual(p1["package_hash"], p2["package_hash"])

    def test_excess_24h(self):
        pkg = _build_default()
        exc = pkg["excess_24h"]
        self.assertIsNotNone(exc["excess_move_pct_24h"])
        self.assertIsNotNone(exc["target_ret_24h_pct"])
        self.assertIsNotNone(exc["btc_ret_24h_pct"])
        self.assertIn("异常审查", exc["note"])

    def test_excess_return_zero_not_missing(self):
        cand = {**CANDIDATE_ALL_TRIGGERS, "excess_move_pct_24h": 0.0}
        pkg = _build_default(candidate=cand)
        qg = pkg["quality_gate"]
        self.assertNotIn("excess_move_pct_24h", qg["missing_fields"])

    def test_expected_output_schema(self):
        pkg = _build_default()
        schema = pkg["expected_output_schema"]
        self.assertIn("sections", schema)
        self.assertTrue(schema["source_urls_required"])

    def test_explicit_mode_in_package(self):
        pkg = _build_default(mode="PROSPECTIVE_LIVE")
        self.assertEqual(pkg["mode"], "PROSPECTIVE_LIVE")

    def test_funding_zero_not_missing(self):
        cand = {**CANDIDATE_ALL_TRIGGERS, "funding_rate_8h": 0.0, "oi_change_pct_24h": 0.0}
        pkg = _build_default(candidate=cand)
        qg = pkg["quality_gate"]
        self.assertNotIn("funding_rate_8h", qg["missing_fields"])
        self.assertNotIn("oi_change_pct_24h", qg["missing_fields"])

    def test_last_complete_bar_from_snapshot(self):
        pkg = _build_default()
        ts = pkg["target_market_snapshot"]
        self.assertIsNotNone(ts.get("last_complete_bar_timestamp_utc"))
        # SNAPSHOT_ROWS 中 ETHUSDT 最后一行时间戳
        self.assertEqual(ts["last_complete_bar_timestamp_utc"], 1778493600000)

    def test_triggered_vs_computed_separated(self):
        explanations = build_signal_explanations(CANDIDATE_ALL_TRIGGERS, SCAN_RULES)
        by_code = {t["code"]: t for t in explanations}

        self.assertTrue(by_code["vol_quantile_high"]["triggered"])
        self.assertEqual(by_code["vol_quantile_high"]["implementation_status"], "COMPUTED")
        self.assertTrue(by_code["large_move_abs"]["triggered"])
        self.assertEqual(by_code["large_move_abs"]["implementation_status"], "COMPUTED")
        self.assertTrue(by_code["large_move_excess"]["triggered"])
        self.assertEqual(by_code["large_move_excess"]["implementation_status"], "COMPUTED")

        self.assertFalse(by_code["vol_quantile_low"]["triggered"])
        self.assertEqual(by_code["vol_quantile_low"]["implementation_status"], "NOT_COMPUTED")

        for code in ("oi_change_quantile_high", "funding_quantile_high", "funding_quantile_low"):
            self.assertFalse(by_code[code]["triggered"])
            self.assertEqual(by_code[code]["implementation_status"], "NOT_COMPUTED")

    def test_all_7_triggers_present(self):
        explanations = build_signal_explanations(CANDIDATE_ALL_TRIGGERS, SCAN_RULES)
        self.assertEqual(len(explanations), 7)
        codes = {t["code"] for t in explanations}
        expected = {
            "vol_quantile_high", "vol_quantile_low",
            "large_move_abs", "large_move_excess",
            "oi_change_quantile_high",
            "funding_quantile_high", "funding_quantile_low",
        }
        self.assertEqual(codes, expected)

    def test_byte_stable_package(self):
        p1 = _build_default()
        p2 = _build_default()
        self.assertEqual(json.dumps(p1, sort_keys=True), json.dumps(p2, sort_keys=True))

    def test_byte_stable_prompt(self):
        pkg = _build_default()
        self.assertEqual(render_research_prompt(pkg), render_research_prompt(pkg))

    def test_package_hash_recomputable(self):
        pkg = _build_default()
        pkg_copy = {k: v for k, v in pkg.items() if k not in ["package_hash", "content_hash", "artifact_hash"]}
        self.assertEqual(hash_prompt_package(pkg_copy), pkg["package_hash"])

    def test_quality_gate_clean_pass(self):
        pkg = _build_default()
        self.assertEqual(pkg["quality_gate"]["status"], "WARN")

    def test_quality_gate_dirty_block(self):
        pkg = _build_default(run_info=DIRTY_RUN)
        self.assertEqual(pkg["quality_gate"]["status"], "BLOCK")
        self.assertIn("run_status=dirty", pkg["quality_gate"]["blockers"])

    def test_quality_gate_hash_mismatch_block(self):
        run = {**CLEAN_RUN, "hashes": {"input_snapshot_sha256": "aaa" * 10}}
        pkg = _build_default(run_info=run)
        self.assertEqual(pkg["quality_gate"]["status"], "BLOCK")

    def test_quality_gate_partial_warn(self):
        partial = {**CANDIDATE_ALL_TRIGGERS, "record_id": "partial_001", "eligible_for_paper": "No", "history_tier": "Partial"}
        pkg = _build_default(candidate=partial)
        self.assertEqual(pkg["quality_gate"]["status"], "WARN")

    def test_quality_gate_quarantined_block(self):
        pkg = _build_default(run_info=QUARANTINED_RUN)
        self.assertEqual(pkg["quality_gate"]["status"], "BLOCK")

    def test_prompt_chinese(self):
        pkg = _build_default()
        prompt = render_research_prompt(pkg)
        self.assertIn("标的", prompt)
        self.assertIn("触发信号解释", prompt)
        self.assertIn("竞争假设", prompt)

    def test_pure_function_no_file_io(self):
        original_open = builtins.open
        def mock_open(*args, **kwargs):
            if "yaml" in str(args[0]).lower() or "scan_rules" in str(args[0]):
                raise FileNotFoundError("No file access allowed")
            return original_open(*args, **kwargs)
        with patch.object(builtins, "open", mock_open):
            pkg = _build_default()
        self.assertIsNotNone(pkg["package_hash"])
        self.assertEqual(pkg["mode"], "HISTORICAL_REPLAY")

    def test_snapshot_sha256_in_package(self):
        pkg = _build_default()
        self.assertEqual(pkg["snapshot_sha256"], CLEAN_MANIFEST["snapshot_sha256"])

    def test_trigger_items_have_triggered_field(self):
        items = _build_default()["trigger_items"]
        for item in items:
            self.assertIn("triggered", item)
            self.assertIn("implementation_status", item)
            self.assertIn("code", item)
            self.assertIn("label_zh", item)
            self.assertIn("explanation_zh", item)
            self.assertIn("limitation_zh", item)

    def test_risk_policy_reference(self):
        pkg = _build_default()
        ref = pkg["risk_policy_reference"]
        self.assertEqual(ref["preset_version"], "v0.1.0-draft")
        self.assertEqual(ref["status"], "DRAFT")
        self.assertEqual(ref["scope"], "PAPER_ONLY")

    def test_package_id_format(self):
        pkg = _build_default()
        self.assertTrue(pkg["package_id"].startswith("drp_"))

    def test_all_output_fields_present(self):
        pkg = _build_default()
        for key in [
            "schema_version", "package_id", "package_hash",
            "template_version", "generator_version", "generated_at_utc",
            "mode", "run_id", "record_id", "symbol",
            "scan_time_utc", "market_data_cutoff", "effective_market_data_cutoff",
            "snapshot_sha256",
            "run_status", "eligible_for_judgment", "eligible_for_paper",
            "quality_gate", "ranking_method", "trigger_items",
            "no_direction_claim", "target_market_snapshot",
            "btc_market_snapshot", "excess_24h", "candidate_metrics",
            "mandatory_research_sections", "prohibited_actions",
            "expected_output_schema", "risk_policy_reference",
        ]:
            self.assertIn(key, pkg, f"Missing top-level field: {key}")

    def test_historical_replay_qualitative_only(self):
        pkg = _build_default(mode="HISTORICAL_REPLAY")
        self.assertTrue(pkg["historical_replay_qualitative_only"])

    def test_prospective_live_not_qualitative_only(self):
        pkg = _build_default(mode="PROSPECTIVE_LIVE")
        self.assertFalse(pkg["historical_replay_qualitative_only"])

    def test_denylist_in_prompt(self):
        pkg = _build_default()
        prompt = render_research_prompt(pkg)
        for pattern in ["exit_price_ref", "btc_exit_price", "dir_excess_ret",
                        "friction_bps", "falsified", "return_tape"]:
            self.assertNotIn(pattern, prompt)

    def test_prompt_no_denylist_patterns(self):
        pkg = _build_default()
        prompt = render_research_prompt(pkg)
        for pattern in ["exit_price_ref", "btc_exit_price", "dir_excess_ret",
                        "friction_bps", "return_tape"]:
            self.assertNotIn(pattern, prompt)

    def test_only_new_files_exist(self):
        allowed = {
            "harness/lib/deep_research_package.py",
            "prompts/deep_research_template_v1.md",
            "tests/test_deep_research_package.py",
        }
        for path in allowed:
            self.assertTrue((PROJECT_ROOT / path).exists(), f"Missing: {path}")


# ===========================================================================
# TestCandidateMetrics（P1）
# ===========================================================================

class TestCandidateMetrics(unittest.TestCase):

    def test_candidate_metrics_present(self):
        pkg = _build_default()
        self.assertIn("candidate_metrics", pkg)
        cm = pkg["candidate_metrics"]
        for key in ALLOWED_CANDIDATE_METRICS_FIELDS:
            self.assertIn(key, cm, f"candidate_metrics missing: {key}")

    def test_symbol_return_from_abs_move(self):
        pkg = _build_default()
        cm = pkg["candidate_metrics"]
        self.assertEqual(cm["symbol_return_24h_pct"], 12.5)

    def test_excess_return_from_candidate(self):
        pkg = _build_default()
        cm = pkg["candidate_metrics"]
        self.assertEqual(cm["excess_return_24h_pct"], 8.3)

    def test_btc_return_computed(self):
        pkg = _build_default()
        cm = pkg["candidate_metrics"]
        # BTC return = symbol - excess = 12.5 - 8.3 = 4.2
        self.assertAlmostEqual(cm["btc_return_24h_pct"], 4.2, places=6)

    def test_realized_vol_from_trigger_value(self):
        pkg = _build_default()
        cm = pkg["candidate_metrics"]
        self.assertEqual(cm["realized_vol_24h_decimal"], 0.045)
        self.assertEqual(cm["realized_vol_quantile"], 0.95)

    def test_funding_fields_populated(self):
        pkg = _build_default()
        cm = pkg["candidate_metrics"]
        self.assertEqual(cm["funding_rate_8h_decimal"], 0.00025)
        self.assertIsNotNone(cm["funding_rate_8h_percent"])
        self.assertEqual(cm["funding_sign"], "positive")

    def test_missing_metrics_are_null_not_zero(self):
        cand = {**CANDIDATE_ALL_TRIGGERS, "oi_change_pct_24h": None}
        pkg = _build_default(candidate=cand)
        cm = pkg["candidate_metrics"]
        self.assertIsNone(cm["oi_change_24h_pct"])

    def test_turnover_from_candidate(self):
        pkg = _build_default()
        cm = pkg["candidate_metrics"]
        self.assertEqual(cm["turnover_24h_usd"], 12500000000.0)

    def test_last_bar_from_snapshot(self):
        pkg = _build_default()
        cm = pkg["candidate_metrics"]
        self.assertEqual(cm["last_complete_bar_timestamp_utc"], 1778493600000)


# ===========================================================================
# TestTriggerUIContract（固定 trigger UI 契约）
# ===========================================================================

class TestTriggerUIContract(unittest.TestCase):

    def test_each_trigger_has_required_fields(self):
        explanations = build_signal_explanations(CANDIDATE_ALL_TRIGGERS, SCAN_RULES)
        required = {"code", "label_zh", "explanation_zh", "limitation_zh",
                     "implementation_status", "triggered", "observation",
                     "threshold", "unit"}
        for item in explanations:
            missing = required - item.keys()
            self.assertEqual(missing, set(), f"{item['code']} missing: {missing}")

    def test_no_description_in_output(self):
        """description 可以内部保留，但前端规范字段是 explanation_zh / limitation_zh。"""
        explanations = build_signal_explanations(CANDIDATE_ALL_TRIGGERS, SCAN_RULES)
        # 字段存在，但前端应使用 explanation_zh 而非 description
        for item in explanations:
            self.assertIn("explanation_zh", item)
            self.assertIn("limitation_zh", item)


# ===========================================================================
# TestCutoffEnforcement（P0 专项）
# ===========================================================================

class TestCutoffEnforcement(unittest.TestCase):

    def test_post_cutoff_rows_filtered_count(self):
        scan_ms = REAL_SCAN_MS
        cutoff_ms = REAL_CUTOFF_MS
        future_ts = cutoff_ms + 3600000
        rows = [
            {"timestamp_utc": scan_ms - 86400000, "close": 100.0, "symbol": "ETHUSDT"},
            {"timestamp_utc": future_ts, "close": 200.0, "symbol": "ETHUSDT"},
        ]
        clean, blockers = _enforce_cutoff(rows, cutoff_ms)
        self.assertEqual(len(clean), 1)
        self.assertEqual(clean[0]["close"], 100.0)
        self.assertTrue(any("post_cutoff" in b for b in blockers))

    def test_all_rows_before_cutoff(self):
        rows = [{"timestamp_utc": REAL_CUTOFF_MS - 3600000, "close": 100.0, "symbol": "ETHUSDT"}]
        clean, blockers = _enforce_cutoff(rows, REAL_CUTOFF_MS)
        self.assertEqual(len(clean), 1)
        self.assertFalse(any("post_cutoff" in b for b in blockers))

    def test_unparseable_timestamp_fails_closed(self):
        rows = [{"timestamp_utc": None, "close": 100.0, "symbol": "ETHUSDT"}]
        clean, blockers = _enforce_cutoff(rows, REAL_CUTOFF_MS)
        self.assertEqual(len(clean), 0)
        self.assertTrue(any("unparseable" in b for b in blockers))

    def test_future_price_999_excluded(self):
        ts_now = int(time.time() * 1000)
        ts_future = ts_now + 86400000
        rows = [
            {"timestamp_utc": ts_now - 3600000, "close": 100.0, "symbol": "ETHUSDT"},
            {"timestamp_utc": ts_future, "close": 999.0, "symbol": "ETHUSDT"},
        ]
        clean, _ = _enforce_cutoff(rows, ts_now)
        closes = [r["close"] for r in clean]
        self.assertNotIn(999.0, closes)
        self.assertIn(100.0, closes)


# ===========================================================================
# TestTimeNormalization
# ===========================================================================

class TestTimeNormalization(unittest.TestCase):

    def test_unix_ms(self):
        self.assertEqual(_parse_ts_to_ms(1778493600000), 1778493600000)

    def test_unix_seconds(self):
        self.assertEqual(_parse_ts_to_ms(1778493600), 1778493600000)

    def test_iso_string(self):
        self.assertEqual(_parse_ts_to_ms("2026-05-11T11:00:00Z"), REAL_CUTOFF_MS)

    def test_numeric_string_ms(self):
        self.assertEqual(_parse_ts_to_ms("1778493600000"), 1778493600000)

    def test_none(self):
        self.assertIsNone(_parse_ts_to_ms(None))

    def test_invalid_string(self):
        self.assertIsNone(_parse_ts_to_ms("not_a_timestamp"))

    def test_normalize_timestamp_field(self):
        row = {"timestamp": 1778493600000, "close": 100.0}
        result = _normalize_snapshot_row(row)
        self.assertEqual(result["timestamp_utc"], 1778493600000)

    def test_normalize_timestamp_utc_field(self):
        row = {"timestamp_utc": 1778493600000, "close": 100.0}
        result = _normalize_snapshot_row(row)
        self.assertEqual(result["timestamp_utc"], 1778493600000)

    def test_normalize_both_fields_same(self):
        row = {"timestamp": 1778493600000, "timestamp_utc": 1778493600000, "close": 100.0}
        result = _normalize_snapshot_row(row)
        self.assertEqual(result["timestamp_utc"], 1778493600000)

    def test_normalize_both_fields_conflict(self):
        row = {"timestamp": 1778493600000, "timestamp_utc": 1778493800000, "close": 100.0}
        with self.assertRaises(ValueError):
            _normalize_snapshot_row(row)

    def test_normalize_neither_field(self):
        row = {"close": 100.0}
        result = _normalize_snapshot_row(row)
        self.assertIsNone(result["timestamp_utc"])


class TestMissingValues(unittest.TestCase):

    def test_none_is_missing(self):
        self.assertTrue(_is_missing(None))

    def test_empty_string_is_missing(self):
        self.assertTrue(_is_missing(""))
        self.assertTrue(_is_missing("   "))

    def test_zero_is_not_missing(self):
        self.assertFalse(_is_missing(0))
        self.assertFalse(_is_missing(0.0))

    def test_nan_is_missing(self):
        self.assertTrue(_is_missing(float("nan")))

    def test_safe_float_none(self):
        self.assertIsNone(_safe_float(None))

    def test_safe_float_empty(self):
        self.assertIsNone(_safe_float(""))

    def test_safe_float_zero(self):
        self.assertEqual(_safe_float(0), 0.0)
        self.assertEqual(_safe_float(0.0), 0.0)

    def test_safe_float_valid(self):
        self.assertEqual(_safe_float("12.5"), 12.5)

    def test_safe_float_invalid(self):
        self.assertIsNone(_safe_float("abc"))


class TestTriggerCatalog(unittest.TestCase):

    def test_all_7_codes_present(self):
        self.assertEqual(set(TRIGGER_CATALOG.keys()), {
            "vol_quantile_high", "vol_quantile_low",
            "large_move_abs", "large_move_excess",
            "oi_change_quantile_high",
            "funding_quantile_high", "funding_quantile_low",
        })

    def test_computed_triggers(self):
        for code in ("vol_quantile_high", "large_move_abs", "large_move_excess"):
            self.assertEqual(TRIGGER_CATALOG[code]["implementation_status"], "COMPUTED")

    def test_not_computed_triggers(self):
        for code in ("vol_quantile_low", "oi_change_quantile_high",
                     "funding_quantile_high", "funding_quantile_low"):
            self.assertEqual(TRIGGER_CATALOG[code]["implementation_status"], "NOT_COMPUTED")

    def test_triggered_false_when_not_in_reason(self):
        cand = {"trigger_reason": "vol_quantile_high", "trigger_quantile": 0.92}
        items = build_signal_explanations(cand, SCAN_RULES)
        by_code = {t["code"]: t for t in items}
        self.assertFalse(by_code["large_move_abs"]["triggered"])
        self.assertEqual(by_code["large_move_abs"]["implementation_status"], "COMPUTED")


class TestFundingDisplay(unittest.TestCase):

    def test_none(self):
        r = _funding_display(None)
        self.assertIsNone(r["funding_rate_8h_decimal"])
        self.assertIsNone(r["funding_rate_8h_percent"])
        self.assertEqual(r["validation_status"], "not_provided")

    def test_zero(self):
        r = _funding_display(0.0)
        self.assertEqual(r["funding_rate_8h_decimal"], 0.0)
        self.assertEqual(r["funding_rate_8h_percent"], 0.0)

    def test_decimal_to_percent(self):
        r = _funding_display(0.00025)
        self.assertAlmostEqual(r["funding_rate_8h_percent"], 0.025, places=6)

    def test_low_rate_is_not_a_second_hard_stop(self):
        r = _funding_display(0.000005)
        self.assertEqual(r["validation_status"], "within_normal_range")

    def test_above_abs_max(self):
        r = _funding_display(0.05)
        self.assertIn("above_abs_max", r["validation_status"])

    def test_normal_range(self):
        r = _funding_display(0.0001)
        self.assertIn("within_normal", r["validation_status"])


class TestMarketSnapshot(unittest.TestCase):

    def test_empty_rows(self):
        r = _market_snapshot_from_safe_rows([])
        self.assertIsNone(r["last_close"])

    def test_with_rows(self):
        rows = [{"timestamp_utc": 1778493600000, "open": 3500.0, "high": 3600.0,
                 "low": 3450.0, "close": 3550.0, "volume": 200000.0,
                 "turnover_usd": 710000000.0, "funding_rate_8h": 0.00025,
                 "open_interest": 5500000.0, "symbol": "ETHUSDT"}]
        r = _market_snapshot_from_safe_rows(rows, "ETHUSDT")
        self.assertEqual(r["last_close"], 3550.0)
        self.assertEqual(r["last_complete_bar_timestamp_utc"], 1778493600000)

    def test_symbol_filter(self):
        rows = [
            {"timestamp_utc": 100, "close": 100.0, "symbol": "BTCUSDT"},
            {"timestamp_utc": 200, "close": 200.0, "symbol": "ETHUSDT"},
        ]
        r = _market_snapshot_from_safe_rows(rows, "ETHUSDT")
        self.assertEqual(r["last_close"], 200.0)

    def test_last_complete_bar_from_snapshot(self):
        pkg = _build_default()
        ts = pkg["target_market_snapshot"]
        self.assertIsNotNone(ts.get("last_complete_bar_timestamp_utc"))
        self.assertEqual(ts["last_complete_bar_timestamp_utc"], 1778493600000)


class TestSchemaTopLevel(unittest.TestCase):

    def test_top_schema_contract_version(self):
        pkg = _build_default()
        self.assertEqual(pkg["schema_version"], "deep_research_prompt_package_v1")

    def test_package_hash_format(self):
        pkg = _build_default()
        h = pkg["package_hash"]
        self.assertEqual(len(h), 64)
        self.assertTrue(all(c in "0123456789abcdef" for c in h))

    def test_explicit_mode_field(self):
        pkg = _build_default(mode="PROSPECTIVE_LIVE")
        self.assertEqual(pkg["mode"], "PROSPECTIVE_LIVE")

    def test_denylist_pattern_exit_price(self):
        pkg = _build_default()
        self.assertNotIn("exit_price_ref", json.dumps(pkg))

    def test_denylist_pattern_btc_exit(self):
        pkg = _build_default()
        self.assertNotIn("btc_exit_price", json.dumps(pkg))

    def test_denylist_pattern_dir_excess(self):
        pkg = _build_default()
        self.assertNotIn("dir_excess_ret", json.dumps(pkg))


# ===========================================================================
# TestRealRunProbe（只读真实数据探针）
# ===========================================================================

class TestRealRunProbe(unittest.TestCase):
    """只读探针：使用真实 harness/runs/20260511_1200_utc_replay/ 数据。"""

    @classmethod
    def setUpClass(cls):
        cls._run_dir = PROJECT_ROOT / "harness/runs/20260511_1200_utc_replay"
        cls._manifest = None
        cls._candidates = []
        cls._snapshot_rows = []
        cls._symbol_meta = {}

        if cls._run_dir.exists():
            import csv as _csv
            # manifest
            with open(cls._run_dir / "run_manifest.json") as f:
                cls._manifest = json.load(f)
            # candidates
            with open(cls._run_dir / "candidates.csv") as f:
                reader = _csv.DictReader(f)
                for row in reader:
                    cls._candidates.append(row)
            # snapshot
            with open(cls._run_dir / "input_snapshot.csv") as f:
                reader = _csv.DictReader(f)
                for row in reader:
                    cls._snapshot_rows.append({
                        "timestamp": int(row["timestamp"]),
                        "open": float(row["open"]),
                        "high": float(row["high"]),
                        "low": float(row["low"]),
                        "close": float(row["close"]),
                        "volume": float(row["volume"]),
                        "turnover_usd": float(row["turnover_usd"]),
                        "funding_rate_8h": float(row["funding_rate_8h"]),
                        "open_interest": float(row["open_interest"]),
                        "symbol": row["symbol"],
                    })
            # symbol_meta
            with open(cls._run_dir / "symbol_meta.csv") as f:
                reader = _csv.DictReader(f)
                for row in reader:
                    cls._symbol_meta[row["symbol"]] = row

    def test_real_manifest_cutoff_less_than_scan(self):
        """真实 run: cutoff < scan → 合法。"""
        if self._manifest is None:
            self.skipTest("No real run available")
        self.assertIsNotNone(self._manifest)
        cutoff_ms = self._manifest.get("data_cutoff")
        scan_utc = self._manifest.get("scan_time_utc", "")
        scan_ms = _parse_ts_to_ms(scan_utc)
        self.assertIsNotNone(scan_ms)
        self.assertLess(cutoff_ms, scan_ms, "真实 run: cutoff 应小于 scan")

    def test_real_snapshot_max_at_cutoff(self):
        """真实 run: snapshot 最大时间戳 = cutoff。"""
        if not self._snapshot_rows:
            self.skipTest("无 snapshot 文件")
        max_ts = max(r["timestamp"] for r in self._snapshot_rows)
        cutoff = self._manifest.get("data_cutoff")
        self.assertEqual(max_ts, cutoff, "真实 run: snapshot max 应等于 cutoff")

    def test_real_snapshot_no_post_cutoff(self):
        """真实 run: snapshot 中无 cutoff 后行。"""
        if not self._snapshot_rows:
            self.skipTest("无 snapshot 文件")
        cutoff = self._manifest.get("data_cutoff")
        post = [r for r in self._snapshot_rows if r["timestamp"] > cutoff]
        self.assertEqual(len(post), 0, f"真实 run 有 {len(post)} 行 cutoff 后数据")

    def test_real_snapshot_symbols_parsed(self):
        """真实 run: snapshot 中所有 symbol 可解析。"""
        if not self._snapshot_rows:
            self.skipTest("无 snapshot 文件")
        symbols = set(r["symbol"] for r in self._snapshot_rows)
        self.assertGreater(len(symbols), 0)
        self.assertIn("BTCUSDT", symbols)

    def test_real_candidate_first_row(self):
        """真实 run: 第一个 candidate 有 trigger_reason。"""
        if not self._candidates:
            self.skipTest("无 candidates 文件")
        c0 = self._candidates[0]
        self.assertIn("trigger_reason", c0)
        self.assertNotEqual(c0["trigger_reason"].strip(), "")


# ===========================================================================
# TestEndToEndCutoffIntegrity（端到端 cutoff 完整性测试）
# ===========================================================================

class TestEndToEndCutoffIntegrity(unittest.TestCase):
    """端到端测试：经过 build_prompt_package 的完整 cutoff/integrity 流程。"""

    def test_timestamp_conflict_blocks(self):
        """timestamp 和 timestamp_utc 冲突 → BLOCK, 不抛异常。"""
        conflict_row = {
            "timestamp": REAL_SCAN_MS - 3600000,
            "timestamp_utc": REAL_SCAN_MS - 7200000,  # 冲突
            "close": 3300.0, "open": 3300.0, "high": 3350.0, "low": 3250.0,
            "volume": 100.0, "turnover_usd": 330000.0,
            "funding_rate_8h": 0.0001, "open_interest": 5000000.0,
            "symbol": "ETHUSDT",
        }
        rows = SNAPSHOT_ROWS + [conflict_row]
        pkg = _build_default(snapshot_rows=rows)
        self.assertEqual(pkg["quality_gate"]["status"], "BLOCK")
        blockers = pkg["quality_gate"]["blockers"]
        self.assertTrue(
            any("conflict" in b.lower() for b in blockers),
            f"Expected conflict blocker, got: {blockers}"
        )

    def test_unparseable_timestamp_blocks(self):
        """timestamp 无法解析 → BLOCK, 不抛异常, blocker 合法数据保留。"""
        bad_row = {
            "timestamp": "not-a-number",
            "close": 3300.0, "open": 3300.0, "high": 3350.0, "low": 3250.0,
            "volume": 100.0, "turnover_usd": 330000.0,
            "funding_rate_8h": 0.0001, "open_interest": 5000000.0,
            "symbol": "ETHUSDT",
        }
        rows = SNAPSHOT_ROWS + [bad_row]
        pkg = _build_default(snapshot_rows=rows)
        prompt = render_research_prompt(pkg)
        pkg_str = json.dumps(pkg, ensure_ascii=False)

        # BLOCK status
        self.assertEqual(pkg["quality_gate"]["status"], "BLOCK")
        # blocker contains timestamp_unparseable
        blockers = pkg["quality_gate"]["blockers"]
        self.assertTrue(
            any("timestamp_unparseable" in b for b in blockers),
            f"Expected timestamp_unparseable blocker, got: {blockers}"
        )
        # bad value not in package or prompt
        self.assertNotIn("not-a-number", pkg_str)
        self.assertNotIn("not-a-number", prompt)
        # valid snapshot data still present
        self.assertIsNotNone(pkg["target_market_snapshot"]["last_close"])

    def test_mixed_valid_invalid_rows_block(self):
        """同时存在有效行和无效行 → 有效快照可保留，但质量状态 BLOCK。"""
        future_ts = REAL_SCAN_MS + 3600000
        invalid_row = {
            "timestamp": future_ts,
            "close": 888.0, "open": 888.0, "high": 888.0, "low": 888.0,
            "volume": 1.0, "turnover_usd": 888.0,
            "funding_rate_8h": 0.0, "open_interest": 0.0,
            "symbol": "ETHUSDT",
        }
        rows = SNAPSHOT_ROWS + [invalid_row]
        pkg = _build_default(snapshot_rows=rows)
        # Invalid row is filtered out (post-cutoff), BLOCK
        self.assertEqual(pkg["quality_gate"]["status"], "BLOCK")
        # Valid data still present
        self.assertIsNotNone(pkg["target_market_snapshot"]["last_close"])
        # 888 not in package
        pkg_str = json.dumps(pkg, ensure_ascii=False)
        self.assertNotIn("888", pkg_str)

    def test_special_prices_777_888_999_not_in_package_or_prompt(self):
        """冲突/无效行中的特殊价格 777/888/999 不得出现在 package 和 prompt。"""
        rows_with_special = SNAPSHOT_ROWS + [
            # future row with 777
            {"timestamp": REAL_SCAN_MS + 1000, "close": 777.0, "open": 777.0,
             "high": 777.0, "low": 777.0, "volume": 1.0, "turnover_usd": 777.0,
             "funding_rate_8h": 0.0, "open_interest": 0.0, "symbol": "ETHUSDT"},
            # future row with 888
            {"timestamp": REAL_SCAN_MS + 2000, "close": 888.0, "open": 888.0,
             "high": 888.0, "low": 888.0, "volume": 1.0, "turnover_usd": 888.0,
             "funding_rate_8h": 0.0, "open_interest": 0.0, "symbol": "ETHUSDT"},
            # future row with 999
            {"timestamp": REAL_SCAN_MS + 3000, "close": 999.0, "open": 999.0,
             "high": 999.0, "low": 999.0, "volume": 1.0, "turnover_usd": 999.0,
             "funding_rate_8h": 0.0, "open_interest": 0.0, "symbol": "ETHUSDT"},
        ]
        pkg = _build_default(snapshot_rows=rows_with_special)
        prompt = render_research_prompt(pkg)
        # Hash digests are opaque and may coincidentally contain a decimal
        # substring; inspect semantic package fields for leaked prices.
        semantic_pkg = {
            key: value for key, value in pkg.items()
            if key not in {"checkpoint_hash", "input_fingerprint", "content_hash", "artifact_hash", "package_hash"}
        }
        pkg_str = json.dumps(semantic_pkg, ensure_ascii=False)
        for special in ["777", "888", "999"]:
            self.assertNotIn(special, pkg_str, f"Special price {special} leaked into package")
            self.assertNotIn(special, prompt, f"Special price {special} leaked into prompt")
        self.assertEqual(pkg["quality_gate"]["status"], "BLOCK")

    def test_cutoff_equals_scan_no_false_block(self):
        """cutoff == scan time → 合法，不得误判为晚于 scan。"""
        pkg = _build_default(manifest=MANIFEST_CUTOFF_EQUALS_SCAN)
        blockers = pkg["quality_gate"]["blockers"]
        self.assertFalse(
            any("cutoff_after_scan" in b or "cutoff > scan" in b for b in blockers),
            f"cutoff==scan should not produce cutoff-after-scan blocker, got: {blockers}"
        )
        self.assertEqual(pkg["effective_market_data_cutoff"], REAL_SCAN_MS)

    def test_no_manifest_cutoff_fallback_to_scan(self):
        """manifest 未提供 cutoff → 有效 cutoff 回退到 scan time。"""
        pkg = _build_default(manifest=MANIFEST_NO_CUTOFF)
        self.assertEqual(pkg["effective_market_data_cutoff"], REAL_SCAN_MS)
        # market_data_cutoff should be None (no manifest cutoff)
        self.assertIsNone(pkg["market_data_cutoff"])


if __name__ == "__main__":
    unittest.main()

class TestAntiP0Regression(unittest.TestCase):
    def test_run_info_missing_status_blocks(self):
        """P0-1: run_info 缺失 status 产生 BLOCK。"""
        pkg = _build_default(run_info={"status": None, "eligible_for_judgment": True, "hashes": {}})
        self.assertEqual(pkg["quality_gate"]["status"], "BLOCK")
        self.assertIn("run_status=None", pkg["quality_gate"]["blockers"])

    def test_run_info_missing_eligible_blocks(self):
        """P0-1: run_info 缺失 eligible_for_judgment 产生 BLOCK。"""
        pkg = _build_default(run_info={"status": "clean", "hashes": {}})
        self.assertEqual(pkg["quality_gate"]["status"], "BLOCK")
        self.assertIn("eligible_for_judgment=false", pkg["quality_gate"]["blockers"])
        
    def test_run_info_missing_hashes_does_not_crash(self):
        """P0-1: run_info 缺失 hashes 不会崩溃，如果不需要比较的话。"""
        pkg = _build_default(run_info={"status": "clean", "eligible_for_judgment": True})
        self.assertEqual(pkg["quality_gate"]["status"], "WARN")

    def test_quality_gate_returns_all_six_gates(self):
        """P0-2: 返回 6 个确定的 sub_gates。"""
        pkg = _build_default()
        qg = pkg["quality_gate"]
        gates = {g["gate"]: g["status"] for g in qg["sub_gates"]}
        self.assertEqual(len(gates), 6)
        self.assertIn("integrity_gate", gates)
        self.assertIn("identity_gate", gates)
        self.assertIn("history_gate", gates)
        self.assertIn("derivatives_gate", gates)
        self.assertIn("liquidity_gate", gates)
        self.assertIn("paper_eligibility_gate", gates)

    def test_history_gate_warns_on_partial(self):
        """P0-2: history_tier=Partial 触发 history_gate WARN。"""
        candidate = {**CANDIDATE_ALL_TRIGGERS, "history_tier": "Partial"}
        pkg = _build_default(candidate=candidate)
        qg = pkg["quality_gate"]
        hg = next(g for g in qg["sub_gates"] if g["gate"] == "history_gate")
        self.assertEqual(hg["status"], "WARN")
        self.assertIn("history_tier=Partial", hg["warnings"])

    def test_derivatives_gate_warns_on_missing_funding(self):
        """P0-2: funding_rate_8h 缺失触发 derivatives_gate WARN。"""
        candidate = {**CANDIDATE_ALL_TRIGGERS, "funding_rate_8h": None}
        pkg = _build_default(candidate=candidate)
        qg = pkg["quality_gate"]
        dg = next(g for g in qg["sub_gates"] if g["gate"] == "derivatives_gate")
        self.assertEqual(dg["status"], "WARN")
        self.assertIn("missing_funding_rate", dg["warnings"])

    def test_paper_eligibility_allow_policy_is_parked(self):
        """G6: bounded gates never ALLOW while the Owner policy is parked."""
        candidate = {**CANDIDATE_ALL_TRIGGERS, "eligible_for_paper": "yes"}
        pkg = _build_default(candidate=candidate)
        pe = pkg["quality_gate"]["paper_eligibility"]
        self.assertEqual(pe["status"], "REVIEW_REQUIRED")
        self.assertIn("PAPER_ALLOW_POLICY_PARKED", pe["reason_codes"])
        self.assertNotEqual(pe["status"], "ALLOW")

    def test_identity_and_liquidity_gates_are_bounded_partial_checks(self):
        pkg = _build_default()
        qg = pkg["quality_gate"]
        identity_gate = next(g for g in qg["sub_gates"] if g["gate"] == "identity_gate")
        liquidity_gate = next(g for g in qg["sub_gates"] if g["gate"] == "liquidity_gate")
        self.assertEqual(identity_gate["status"], "WARN")
        self.assertIn("migration_history_status=NOT_AVAILABLE", identity_gate["warnings"])
        self.assertEqual(liquidity_gate["status"], "WARN")
        self.assertIn("spread_status=NOT_AVAILABLE", liquidity_gate["warnings"])
        self.assertIn("depth_status=NOT_AVAILABLE", liquidity_gate["warnings"])

        checks = {check["code"]: check for check in qg["required_human_checks"]}
        self.assertFalse(checks["IDENTITY_MIGRATION_HISTORY_NOT_AVAILABLE"]["blocking"])
        self.assertFalse(checks["LIQUIDITY_SPREAD_NOT_AVAILABLE"]["blocking"])
        self.assertFalse(checks["LIQUIDITY_DEPTH_NOT_AVAILABLE"]["blocking"])

    def test_graveyard_prohibition_is_rendered(self):
        prompt = render_research_prompt(_build_default())
        self.assertIn(
            "不得复活 GRAVEYARD.md 所列已证伪方向（carry/庄家-费率/跟随聪明钱/机械方向择时）作为交易机制建议",
            prompt,
        )

    def test_paper_eligibility_review_for_partial(self):
        """P0-3: history_tier=partial 时 paper_eligibility 状态为 REVIEW_REQUIRED。"""
        candidate = {**CANDIDATE_ALL_TRIGGERS, "eligible_for_paper": "no", "history_tier": "partial"}
        pkg = _build_default(candidate=candidate)
        pe = pkg["quality_gate"]["paper_eligibility"]
        self.assertEqual(pe["status"], "REVIEW_REQUIRED")
        self.assertIn("PARTIAL_HISTORY", pe["reason_codes"])

    def test_paper_eligibility_block_for_none(self):
        """P0-3: 其他情况 paper_eligibility 为 BLOCK。"""
        candidate = {**CANDIDATE_ALL_TRIGGERS, "eligible_for_paper": "no", "history_tier": "none"}
        pkg = _build_default(candidate=candidate)
        pe = pkg["quality_gate"]["paper_eligibility"]
        self.assertEqual(pe["status"], "BLOCK")

    def test_turnover_metrics_separated(self):
        """P0-5: 拆分三种 turnover。"""
        pkg = _build_default()
        metrics = pkg["candidate_metrics"]
        self.assertIn("last_bar_turnover_usd", metrics)
        self.assertIn("turnover_24h_usd", metrics)
        self.assertIn("turnover_valid_bars_24h", metrics)

    def test_human_checks_is_object_list(self):
        """P0-7: human_checks 为对象结构。"""
        candidate = {**CANDIDATE_ALL_TRIGGERS, "history_tier": "Partial"}
        pkg = _build_default(candidate=candidate)
        checks = pkg["quality_gate"]["required_human_checks"]
        self.assertTrue(len(checks) > 0)
        self.assertIsInstance(checks[0], dict)
        self.assertIn("code", checks[0])
        self.assertIn("item", checks[0])

    def test_mode_invalid_causes_block(self):
        """P0-8: mode 不合法直接 BLOCK。"""
        from harness.lib.deep_research_package import build_prompt_package
        with self.assertRaises(Exception):
             # Wait, _build_default passes valid mode. Let's force an invalid mode by calling build_prompt_package directly
             build_prompt_package(
                 candidate=VALID_CANDIDATE,
                 run_info=CLEAN_RUN,
                 manifest=MANIFEST,
                 symbol_meta=SYMBOL_META,
                 scan_rules={"trigger_catalog": {}},
                 deep_research_contract=DEEP_RESEARCH_CONTRACT,
                 risk_presets=RISK_PRESETS,
                 snapshot_rows=SNAPSHOT_ROWS,
                 mode="INVALID_MODE"
             )

    def test_hash_separation(self):
        """P0-9: 分离 content_hash, artifact_hash, input_fingerprint。"""
        pkg = _build_default()
        self.assertIn("content_hash", pkg)
        self.assertIn("artifact_hash", pkg)
        self.assertIn("input_fingerprint", pkg)
        self.assertNotEqual(pkg["content_hash"], pkg["input_fingerprint"])
        self.assertNotEqual(pkg["content_hash"], pkg["artifact_hash"])

class TestGatesP0(unittest.TestCase):
    def test_identity_gate_missing_symbol(self):
        cand = {**CANDIDATE_ALL_TRIGGERS}
        cand.pop("symbol", None)
        pkg = _build_default(candidate=cand)
        self.assertEqual(pkg["quality_gate"]["status"], "BLOCK")
        self.assertTrue(any("missing_symbol" in b for b in pkg["quality_gate"]["blockers"]))

    def test_identity_gate_missing_symbol_meta(self):
        pkg = build_prompt_package(
            CANDIDATE_ALL_TRIGGERS, CLEAN_RUN, CLEAN_MANIFEST, {},
            SCAN_RULES, DEEP_RESEARCH_CONTRACT, RISK_PRESETS,
            SNAPSHOT_ROWS, mode="HISTORICAL_REPLAY", generated_at_utc=GENERATED_AT,
        )
        self.assertEqual(pkg["quality_gate"]["status"], "BLOCK")
        self.assertTrue(any("missing_symbol_meta" in b for b in pkg["quality_gate"]["blockers"]))

    def test_paper_eligibility_derivatives_warn(self):
        cand = {**CANDIDATE_ALL_TRIGGERS, "eligible_for_paper": "yes", "open_interest": None}
        pkg = _build_default(candidate=cand)
        peg = next(g for g in pkg["quality_gate"]["sub_gates"] if g["gate"] == "paper_eligibility_gate")
        self.assertEqual(peg["status"], "WARN")
        self.assertEqual(pkg["quality_gate"]["paper_eligibility"]["status"], "REVIEW_REQUIRED")
        self.assertIn("DERIVATIVES_WARN", pkg["quality_gate"]["paper_eligibility"]["reason_codes"])

    def test_paper_eligibility_liquidity_warn(self):
        cand = {**CANDIDATE_ALL_TRIGGERS, "eligible_for_paper": "yes", "turnover_24h_usd": None}
        pkg = _build_default(candidate=cand)
        peg = next(g for g in pkg["quality_gate"]["sub_gates"] if g["gate"] == "paper_eligibility_gate")
        self.assertEqual(peg["status"], "WARN")
        self.assertEqual(pkg["quality_gate"]["paper_eligibility"]["status"], "REVIEW_REQUIRED")
        self.assertIn("LIQUIDITY_WARN", pkg["quality_gate"]["paper_eligibility"]["reason_codes"])
class TestIntegrityGateHashes(unittest.TestCase):
    def test_integrity_gate_hash_mismatch(self):
        run_info = {
            "status": "clean",
            "eligible_for_judgment": True,
            "hashes": {
                "input_snapshot_sha256": "wrong_snap",
                "symbol_meta_sha256": "wrong_meta",
                "return_tape_sha256": "wrong_tape",
            }
        }
        manifest = {
            "snapshot_sha256": "correct_snap",
            "symbol_meta_sha256": "correct_meta",
            "return_tape_sha256": "correct_tape",
        }
        
        pkg = _build_default(run_info=run_info, manifest=manifest)
        self.assertEqual(pkg["quality_gate"]["status"], "BLOCK")
        ig = next(g for g in pkg["quality_gate"]["sub_gates"] if g["gate"] == "integrity_gate")
        self.assertEqual(ig["status"], "BLOCK")
        self.assertIn("snapshot_sha256_hash_mismatch", ig["blockers"])
        self.assertIn("symbol_meta_sha256_hash_mismatch", ig["blockers"])
        self.assertIn("return_tape_sha256_hash_mismatch", ig["blockers"])
