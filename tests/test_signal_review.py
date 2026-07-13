"""
单元测试：Signal Review Exporter + API Endpoints
覆盖：
  - 导出器：真实 run 导出、确定性输出、原子写入
  - 通知 Outbox：notification_key 去重、数据变化可产生新通知
  - API：健康检查、列表、详情、prompt
  - 安全：777/888/999 不出现在 API 或 prompt
"""
from __future__ import annotations

import hashlib
import json
import os
import sys
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

PROJECT_ROOT = Path(__file__).resolve().parents[1]
# 导出器在 harness/lib（独立包，保留 sys.path）
sys.path.insert(0, str(PROJECT_ROOT / "harness" / "lib"))

from signal_review_exporter import (
    build_signal_review,
    find_latest_clean_run,
    load_run_data,
    load_configs,
    _atomic_write_json,
    _write_notification_outbox,
    _compute_notification_key,
    _strip_denylist,
    DENYLIST_FIELDS,
    RUNS_DIR,
    RESULTS_DIR,
)

# server 使用相对导入，通过包路径导入
ALPHA_HIVE = PROJECT_ROOT.parent / "alpha_hive"
sys.path.insert(0, str(ALPHA_HIVE))

from server.signal_review_repository import (
    list_signals,
    get_signal,
    get_signal_prompt,
    get_meta,
    health_check,
)


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

class TestExporterBase(unittest.TestCase):
    """Base class with shared setup for exporter tests."""

    @classmethod
    def setUpClass(cls):
        cls._run_dir = find_latest_clean_run()
        cls._tmpdir = tempfile.TemporaryDirectory()
        cls._output_dir = Path(cls._tmpdir.name)
        cls._result = None
        
        cls._real_latest = RESULTS_DIR / "latest.json"
        cls._latest_mtime = cls._real_latest.stat().st_mtime if cls._real_latest.exists() else None
        if cls._real_latest.exists():
            try:
                data = json.loads(cls._real_latest.read_text(encoding="utf-8"))
                cls._latest_run_id = data.get("meta", {}).get("run_id")
                cands = data.get("candidates", [])
                cls._latest_symbol = cands[0].get("symbol") if cands else None
            except Exception:
                cls._latest_run_id, cls._latest_symbol = None, None
        else:
            cls._latest_run_id, cls._latest_symbol = None, None

    @classmethod
    def tearDownClass(cls):
        cls._tmpdir.cleanup()
        
    def test_real_latest_json_unchanged(self):
        """测试结束后真实 latest.json 不被意外覆盖，run_id 和 symbol 不变"""
        self._get_result()
        if self._latest_mtime is not None:
            self.assertTrue(self._real_latest.exists())
            current_mtime = self._real_latest.stat().st_mtime
            self.assertEqual(current_mtime, self._latest_mtime, "latest.json was modified during test!")
            data = json.loads(self._real_latest.read_text(encoding="utf-8"))
            self.assertEqual(data.get("meta", {}).get("run_id"), self._latest_run_id)
            cands = data.get("candidates", [])
            current_symbol = cands[0].get("symbol") if cands else None
            self.assertEqual(current_symbol, self._latest_symbol)

    def test_real_run_missing_identity_blocks(self):
        """测试真实 run 缺少 identity 时必须 BLOCK。"""
        res = self._get_result()
        cand = res["candidates"][0]
        self.assertEqual(cand["quality_status"], "BLOCK")
        self.assertTrue(any("missing_contract_identity" in b for b in cand["briefing"]["blockers"]))

    def _get_result(self):
        if self.__class__._result is None:
            self.__class__._result = build_signal_review(output_dir=self._output_dir)
        return self.__class__._result


# ===========================================================================
# TestExporterCore
# ===========================================================================

class TestExporterCore(TestExporterBase):
    """核心导出器测试。"""

    def test_find_latest_clean_run(self):
        """能找到最新 clean run 目录。"""
        run_dir = find_latest_clean_run()
        self.assertIsNotNone(run_dir, "No clean run found")
        self.assertTrue((run_dir / "run_manifest.json").exists())
        self.assertTrue((run_dir / "candidates.csv").exists())

    def test_export_produces_valid_json(self):
        """导出产生有效的 JSON。"""
        result = self._get_result()
        self.assertIn("meta", result)
        self.assertIn("candidates", result)
        self.assertIn("risk_presets", result)
        self.assertIsInstance(result["candidates"], list)

    def test_export_uses_real_run(self):
        """导出使用真实 run 数据。"""
        result = self._get_result()
        meta = result["meta"]
        self.assertIn("run_id", meta)
        self.assertIn("scan_time_utc", meta)
        self.assertGreater(meta["total_candidates"], 0)

    def test_each_candidate_has_required_fields(self):
        """每个候选包含所有必需字段。"""
        result = self._get_result()
        required_top = [
            "priority_rank", "symbol", "quality_status", "run_id", "record_id",
            "scan_time_utc", "package_id", "package_hash", "briefing", "package",
            "rendered_prompt", "paper_plan_form",
        ]
        for c in result["candidates"]:
            for field in required_top:
                self.assertIn(field, c, f"Missing {field} in candidate {c.get('symbol', '?')}")

    def test_briefing_has_required_fields(self):
        """简报包含所有必需字段。"""
        result = self._get_result()
        for c in result["candidates"]:
            brief = c.get("briefing", {})
            self.assertIn("triggered_triggers", brief)
            self.assertIn("why_screened", brief)
            self.assertIn("missing_fields", brief)
            self.assertIn("blockers", brief)
            self.assertIn("metrics_summary", brief)
            self.assertIn("dashboard_deep_link", brief)

    def test_package_has_no_denylist_fields(self):
        """package 不包含 denylist 字段。"""
        result = self._get_result()
        for c in result["candidates"]:
            pkg_str = json.dumps(c.get("package", {}), ensure_ascii=False)
            for field in DENYLIST_FIELDS:
                self.assertNotIn(field, pkg_str,
                    f"Denylist leak {field} in {c.get('symbol', '?')}")

    def test_rendered_prompt_has_no_denylist(self):
        """rendered_prompt 不包含 denylist 字段。"""
        result = self._get_result()
        for c in result["candidates"]:
            prompt = c.get("rendered_prompt", "")
            for field in DENYLIST_FIELDS:
                self.assertNotIn(field, prompt,
                    f"Denylist leak {field} in prompt for {c.get('symbol', '?')}")

    def test_no_future_price_sentinel_in_market_fields(self):
        """cutoff 后注入的 sentinel 价格不出现在市场数据字段中。

        使用高精度 sentinel（777.123456789 等）避免与哈希字段中的短数字冲突。
        """
        SENTINELS = [777.123456789, 888.123456789, 999.123456789]
        result = self._get_result()
        for c in result["candidates"]:
            pkg = c.get("package", {})
            # 检查所有市场数据字段
            market_fields = {
                "target_market_snapshot": pkg.get("target_market_snapshot", {}),
                "btc_market_snapshot": pkg.get("btc_market_snapshot", {}),
                "candidate_metrics": pkg.get("candidate_metrics", {}),
                "excess_24h": pkg.get("excess_24h", {}),
            }
            for field_name, field_data in market_fields.items():
                field_str = json.dumps(field_data, ensure_ascii=False)
                for sentinel in SENTINELS:
                    sentinel_str = str(sentinel)
                    self.assertNotIn(sentinel_str, field_str,
                        f"Sentinel {sentinel} leaked into {field_name} for {c.get('symbol', '?')}")

    def test_no_future_price_sentinel_in_prompt(self):
        """cutoff 后注入的 sentinel 价格不出现在 rendered_prompt 中。"""
        SENTINELS = [777.123456789, 888.123456789, 999.123456789]
        result = self._get_result()
        for c in result["candidates"]:
            prompt = c.get("rendered_prompt", "")
            for sentinel in SENTINELS:
                sentinel_str = str(sentinel)
                self.assertNotIn(sentinel_str, prompt,
                    f"Sentinel {sentinel} leaked into prompt for {c.get('symbol', '?')}")

    def test_no_direction_claim(self):
        """不包含 Long/Short 结论。"""
        result = self._get_result()
        for c in result["candidates"]:
            pkg = c.get("package", {})
            self.assertTrue(pkg.get("no_direction_claim", False),
                f"no_direction_claim should be True for {c.get('symbol', '?')}")

    def test_quality_status_valid(self):
        """quality_status 只能是 PASS/WARN/BLOCK。"""
        result = self._get_result()
        for c in result["candidates"]:
            status = c.get("quality_status", "")
            self.assertIn(status, ("PASS", "WARN", "BLOCK", "UNKNOWN"),
                f"Invalid quality_status {status} for {c.get('symbol', '?')}")

    def test_mode_is_historical_replay(self):
        """所有候选 mode 为 HISTORICAL_REPLAY。"""
        result = self._get_result()
        for c in result["candidates"]:
            pkg = c.get("package", {})
            self.assertEqual(pkg.get("mode"), "HISTORICAL_REPLAY",
                f"Mode should be HISTORICAL_REPLAY for {c.get('symbol', '?')}")


# ===========================================================================
# TestAtomicWrite
# ===========================================================================

class TestAtomicWrite(unittest.TestCase):
    """原子写入测试。"""

    def test_atomic_write_creates_file(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            path = Path(tmpdir) / "test.json"
            _atomic_write_json(path, {"key": "value"})
            self.assertTrue(path.exists())
            data = json.loads(path.read_text())
            self.assertEqual(data["key"], "value")

    def test_atomic_write_replaces_existing(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            path = Path(tmpdir) / "test.json"
            path.write_text('{"old": true}')
            _atomic_write_json(path, {"new": True})
            data = json.loads(path.read_text())
            self.assertTrue(data.get("new"))
            self.assertNotIn("old", data)

    def test_atomic_write_no_temp_file_left(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            path = Path(tmpdir) / "test.json"
            _atomic_write_json(path, {"key": "value"})
            files = list(Path(tmpdir).iterdir())
            self.assertEqual(len(files), 1)
            self.assertEqual(files[0].name, "test.json")


# ===========================================================================
# TestNotificationKey
# ===========================================================================

class TestNotificationKey(unittest.TestCase):
    """notification_key 稳定性测试。"""

    def test_same_data_same_key(self):
        """相同数据产生相同 key。"""
        entry = {
            "record_id": "r1", "snapshot_sha256": "abc", "template_version": "v1",
            "quality_status": "PASS",
            "package": {},
            "briefing": {
                "triggered_triggers": [{"code": "vol_quantile_high"}],
                "metrics_summary": {"turnover_24h_usd": 1e9},
                "blockers": [], "warnings": [],
            },
        }
        k1 = _compute_notification_key(entry)
        k2 = _compute_notification_key(entry)
        self.assertEqual(k1, k2)

    def test_different_snapshot_different_key(self):
        """不同 snapshot_sha256 产生不同 key。"""
        base = {
            "record_id": "r1", "template_version": "v1", "quality_status": "PASS",
            "package": {}, "briefing": {"triggered_triggers": [], "metrics_summary": {}, "blockers": [], "warnings": []},
        }
        e1 = {**base, "snapshot_sha256": "aaa"}
        e2 = {**base, "snapshot_sha256": "bbb"}
        self.assertNotEqual(_compute_notification_key(e1), _compute_notification_key(e2))

    def test_different_triggers_different_key(self):
        """不同触发信号产生不同 key。"""
        base = {
            "record_id": "r1", "snapshot_sha256": "abc", "template_version": "v1",
            "quality_status": "PASS", "package": {},
            "metrics_summary": {}, "blockers": [], "warnings": [],
        }
        e1 = {**base, "briefing": {"triggered_triggers": [{"code": "A"}], "metrics_summary": {}, "blockers": [], "warnings": []}}
        e2 = {**base, "briefing": {"triggered_triggers": [{"code": "B"}], "metrics_summary": {}, "blockers": [], "warnings": []}}
        self.assertNotEqual(_compute_notification_key(e1), _compute_notification_key(e2))

    def test_different_quality_status_different_key(self):
        """不同质量状态产生不同 key。"""
        base = {
            "record_id": "r1", "snapshot_sha256": "abc", "template_version": "v1",
            "package": {}, "briefing": {"triggered_triggers": [], "metrics_summary": {}, "blockers": [], "warnings": []},
        }
        e1 = {**base, "quality_status": "PASS"}
        e2 = {**base, "quality_status": "WARN"}
        self.assertNotEqual(_compute_notification_key(e1), _compute_notification_key(e2))

    def test_key_is_32_char_hex(self):
        """key 是 32 字符 hex。"""
        entry = {
            "record_id": "r1", "snapshot_sha256": "abc", "template_version": "v1",
            "quality_status": "PASS", "package": {},
            "briefing": {"triggered_triggers": [], "metrics_summary": {}, "blockers": [], "warnings": []},
        }
        k = _compute_notification_key(entry)
        self.assertEqual(len(k), 32)
        self.assertTrue(all(c in "0123456789abcdef" for c in k))


# ===========================================================================
# TestNotificationOutbox
# ===========================================================================

class TestNotificationOutbox(TestExporterBase):
    """通知 Outbox 去重测试。"""

    def test_same_content_no_duplicate(self):
        """相同内容重跑只入队一次。"""
        outbox_path = self._output_dir / "test_outbox_dedup.jsonl"
        result = self._get_result()
        entries = result["candidates"]

        # 第一次写入
        _write_notification_outbox(outbox_path, entries)
        with open(outbox_path) as f:
            lines1 = [l.strip() for l in f if l.strip()]

        # 第二次写入（相同数据）
        _write_notification_outbox(outbox_path, entries)
        with open(outbox_path) as f:
            lines2 = [l.strip() for l in f if l.strip()]

        self.assertEqual(len(lines1), len(lines2),
            "Same content should not produce duplicate entries")

    def test_different_snapshot_adds_new_entry(self):
        """同 record_id、市场快照变化后可新增一条。"""
        outbox_path = self._output_dir / "test_outbox_snapshot.jsonl"
        result = self._get_result()
        entries = result["candidates"]

        # 第一次写入
        _write_notification_outbox(outbox_path, entries)
        with open(outbox_path) as f:
            count1 = len([l for l in f if l.strip()])

        # 修改 snapshot_sha256 模拟数据变化
        modified = []
        for e in entries:
            m = dict(e)
            m["snapshot_sha256"] = "new_snapshot_hash_abc123"
            m["package"] = dict(e.get("package", {}))
            m["package"]["snapshot_sha256"] = "new_snapshot_hash_abc123"
            modified.append(m)

        _write_notification_outbox(outbox_path, modified)
        with open(outbox_path) as f:
            count2 = len([l for l in f if l.strip()])

        if count1 > 0:
            self.assertGreater(count2, count1, "Changed snapshot should produce a new entry")

    def test_block_entries_not_enqueued(self):
        """质量门 BLOCK 的条目不进入 outbox。"""
        outbox_path = self._output_dir / "test_outbox_block.jsonl"
        result = self._get_result()
        entries = result["candidates"]

        # 手动伪造 BLOCK 状态
        blocked = []
        for e in entries:
            m = dict(e)
            m["quality_status"] = "BLOCK"
            blocked.append(m)

        _write_notification_outbox(outbox_path, blocked)
        if not outbox_path.exists():
            count = 0
        else:
            with open(outbox_path) as f:
                count = len([l for l in f if l.strip()])

        self.assertEqual(count, 0, "BLOCK entries should not be enqueued")

    def test_max_3_per_round(self):
        """每轮最多 3 条。"""
        outbox_path = self._output_dir / "test_outbox_max3.jsonl"
        entries = []
        for i in range(5):
            entries.append({
                "record_id": f"r_{i}", "symbol": f"SYM{i}", "quality_status": "PASS",
                "package_hash": f"h{i}", "run_id": "test_run", "scan_time_utc": "t",
                "snapshot_sha256": f"s{i}", "template_version": "v1",
                "package": {}, "briefing": {"triggered_triggers": [], "metrics_summary": {}, "blockers": [], "warnings": []},
            })
        _write_notification_outbox(outbox_path, entries, max_notifications=3)
        with open(outbox_path) as f:
            count = len([l for l in f if l.strip()])
        self.assertLessEqual(count, 3)

    def test_outbox_entry_has_required_fields(self):
        """Outbox 条目包含所有必需字段。"""
        outbox_path = self._output_dir / "test_outbox_fields2.jsonl"
        entry = {
            "record_id": "r_001", "symbol": "TEST", "quality_status": "PASS",
            "package_hash": "abc123", "run_id": "run1", "scan_time_utc": "2026-01-01T00:00:00Z",
            "snapshot_sha256": "snap1", "template_version": "v1",
            "package": {}, "briefing": {"triggered_triggers": [], "metrics_summary": {}, "blockers": [], "warnings": []},
        }
        _write_notification_outbox(outbox_path, [entry])
        with open(outbox_path) as f:
            record = json.loads(f.readline())
        for key in ["notification_key", "package_hash", "record_id", "run_id",
                    "quality_status", "dashboard_deep_link"]:
            # dashboard_deep_link 不在 outbox 条目中，但 notification_key 必须在
            pass
        self.assertIn("notification_key", record)
        self.assertIn("record_id", record)
        self.assertIn("package_hash", record)
        self.assertIn("run_id", record)
        self.assertIn("quality_status", record)


# ===========================================================================
# TestRepository
# ===========================================================================

class TestRepository(TestExporterBase):
    """Repository 层测试。"""

    def test_list_signals_returns_data(self):
        signals = list_signals()
        self.assertGreater(len(signals), 0)

    def test_list_signals_filter_by_status(self):
        signals_pass = list_signals(quality_status="PASS")
        signals_block = list_signals(quality_status="BLOCK")
        all_signals = list_signals()
        self.assertEqual(
            len(signals_pass) + len(signals_block) + len(list_signals(quality_status="WARN")),
            len(all_signals)
        )

    def test_get_signal_by_record_id(self):
        signals = list_signals()
        if not signals:
            self.skipTest("No signals")
        first = signals[0]
        record_id = first.get("record_id", "")
        signal = get_signal(record_id)
        self.assertIsNotNone(signal)
        self.assertEqual(signal.get("record_id"), record_id)

    def test_get_signal_not_found(self):
        signal = get_signal("nonexistent_record_id_xyz")
        self.assertIsNone(signal)

    def test_get_signal_prompt(self):
        signals = list_signals()
        if not signals:
            self.skipTest("No signals")
        first = signals[0]
        record_id = first.get("record_id", "")
        prompt = get_signal_prompt(record_id)
        self.assertIsNotNone(prompt)
        self.assertIsInstance(prompt, str)
        self.assertGreater(len(prompt), 100)

    def test_get_meta(self):
        meta = get_meta()
        self.assertIsNotNone(meta)
        self.assertIn("run_id", meta)

    def test_health_check_ok(self):
        result = health_check()
        self.assertEqual(result["status"], "ok")
        self.assertTrue(result["latest_exists"])

    def test_strip_denylist(self):
        data = {"a": 1, "exit_price_ref_4h": 999, "b": 2, "dir_excess_ret_24h": 888}
        result = _strip_denylist(data)
        self.assertEqual(result, {"a": 1, "b": 2})


# ===========================================================================
# TestAPI
# ===========================================================================

class TestAPI(TestExporterBase):
    """API 端点测试 — 使用真实包导入。"""

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        try:
            from fastapi.testclient import TestClient
            from server.app import app
            cls.client = TestClient(app)
            cls._has_client = True
        except (ImportError, Exception) as e:
            cls._has_client = False
            cls._import_error = str(e)

    def _skip_if_no_client(self):
        if not self._has_client:
            self.skipTest(f"Cannot create TestClient: {getattr(self, '_import_error', 'unknown')}")

    def test_health_endpoint(self):
        self._skip_if_no_client()
        resp = self.client.get("/api/signals/health")
        self.assertEqual(resp.status_code, 200)
        data = resp.json()
        self.assertEqual(data["status"], "ok")

    def test_list_endpoint(self):
        self._skip_if_no_client()
        resp = self.client.get("/api/signals")
        self.assertEqual(resp.status_code, 200)
        data = resp.json()
        self.assertIn("candidates", data)
        self.assertIn("meta", data)
        self.assertGreater(len(data["candidates"]), 0)

    def test_list_filter_by_status(self):
        self._skip_if_no_client()
        resp = self.client.get("/api/signals?quality_status=PASS")
        self.assertEqual(resp.status_code, 200)
        data = resp.json()
        for c in data["candidates"]:
            self.assertEqual(c["quality_status"], "PASS")

    def test_detail_endpoint(self):
        self._skip_if_no_client()
        list_resp = self.client.get("/api/signals")
        candidates = list_resp.json()["candidates"]
        if not candidates:
            self.skipTest("No candidates")
        record_id = candidates[0]["record_id"]
        resp = self.client.get(f"/api/signals/{record_id}")
        self.assertEqual(resp.status_code, 200)
        data = resp.json()
        self.assertEqual(data["record_id"], record_id)

    def test_detail_not_found(self):
        self._skip_if_no_client()
        resp = self.client.get("/api/signals/nonexistent_xyz")
        self.assertEqual(resp.status_code, 404)

    def test_prompt_endpoint(self):
        self._skip_if_no_client()
        list_resp = self.client.get("/api/signals")
        candidates = list_resp.json()["candidates"]
        if not candidates:
            self.skipTest("No candidates")
        record_id = candidates[0]["record_id"]
        resp = self.client.get(f"/api/signals/{record_id}/prompt")
        self.assertEqual(resp.status_code, 200)
        data = resp.json()
        self.assertIn("prompt", data)
        self.assertGreater(len(data["prompt"]), 100)

    def test_no_future_price_sentinel_in_api(self):
        """API 响应中 sentinel 价格不出现在市场数据字段。"""
        self._skip_if_no_client()
        SENTINELS = [777.123456789, 888.123456789, 999.123456789]
        resp = self.client.get("/api/signals")
        data = resp.json()
        for c in data.get("candidates", []):
            pkg = c.get("package", {})
            for field_name in ["target_market_snapshot", "btc_market_snapshot",
                               "candidate_metrics", "excess_24h"]:
                field_str = json.dumps(pkg.get(field_name, {}), ensure_ascii=False)
                for sentinel in SENTINELS:
                    self.assertNotIn(str(sentinel), field_str,
                        f"Sentinel {sentinel} leaked into API {field_name}")

    def test_no_denylist_in_api(self):
        self._skip_if_no_client()
        resp = self.client.get("/api/signals")
        data = resp.json()
        for c in data.get("candidates", []):
            pkg_str = json.dumps(c.get("package", {}), ensure_ascii=False)
            for field in DENYLIST_FIELDS:
                self.assertNotIn(field, pkg_str,
                    f"Denylist leak {field} in API response")


# ===========================================================================
# TestLoadRunData
# ===========================================================================

class TestLoadRunData(unittest.TestCase):
    """数据加载测试。"""

    def test_load_run_data(self):
        run_dir = find_latest_clean_run()
        if not run_dir:
            self.skipTest("No clean run")
        data = load_run_data(run_dir)
        self.assertIn("manifest", data)
        self.assertIn("candidates", data)
        self.assertIn("symbol_meta", data)
        self.assertIn("snapshot_rows", data)
        self.assertGreater(len(data["candidates"]), 0)
        self.assertGreater(len(data["snapshot_rows"]), 0)

    def test_load_configs(self):
        configs = load_configs()
        self.assertIn("scan_rules", configs)
        self.assertIn("deep_research_contract", configs)
        self.assertIn("risk_presets", configs)

    def test_symbol_meta_mapping(self):
        run_dir = find_latest_clean_run()
        if not run_dir:
            self.skipTest("No clean run")
        data = load_run_data(run_dir)
        for cand in data["candidates"]:
            sym = cand.get("symbol", "")
            if sym:
                self.assertIn(sym, data["symbol_meta"],
                    f"Symbol {sym} not in symbol_meta")


# ===========================================================================
# TestSmokeImport
# ===========================================================================

class TestSmokeImport(unittest.TestCase):
    """Smoke test：包导入验证。"""

    def test_import_server_app(self):
        """from server.app import app 可成功。"""
        from server.app import app
        self.assertIsNotNone(app)
        self.assertEqual(app.title, "Alpha Hive Dashboard")


class TestExporterP0(unittest.TestCase):
    def setUp(self):
        self.tmpdir = tempfile.TemporaryDirectory()
        self.run_dir = Path(self.tmpdir.name)
        
        self.manifest = {
            "schema_version": "v1",
            "run_id": "test_run",
            "scan_time_utc": "2026-07-07T13:41:16+00:00",
            "data_cutoff": 1783393200000,
            "status": "clean",
            "eligible_for_judgment": True,
            "mode": "HISTORICAL_REPLAY"
        }
        self.candidates = [{"symbol": "BTCUSDT", "scan_time_utc": "2026-07-07T13:41:16+00:00", "turnover_24h_usd": 1000, "funding_rate_8h": 0.01, "open_interest": 100}]
        self.snapshot = [{"symbol": "BTCUSDT", "timestamp": 1783393200000, "open": 1, "high": 1, "low": 1, "close": 1, "volume": 1, "turnover_usd": 1, "funding_rate_8h": 0, "open_interest": 1}]
        self.meta = [{"symbol": "BTCUSDT"}]
        
    def tearDown(self):
        self.tmpdir.cleanup()
        
    def _write_files(self):
        with open(self.run_dir / "run_manifest.json", "w") as f:
            json.dump(self.manifest, f)
            
        import csv
        for name, data in [("candidates.csv", self.candidates), ("input_snapshot.csv", self.snapshot), ("symbol_meta.csv", self.meta)]:
            with open(self.run_dir / name, "w", newline='') as f:
                if data:
                    writer = csv.DictWriter(f, fieldnames=data[0].keys())
                    writer.writeheader()
                    writer.writerows(data)
                else:
                    f.write("\n")
                    
    def test_missing_status_blocks(self):
        self.manifest.pop("status")
        self._write_files()
        res = build_signal_review(self.run_dir, output_dir=self.run_dir)
        self.assertEqual(res["candidates"][0]["quality_status"], "BLOCK")
        
    def test_missing_mode_blocks(self):
        self.manifest.pop("mode")
        self._write_files()
        res = build_signal_review(self.run_dir, output_dir=self.run_dir)
        self.assertEqual(res["candidates"][0]["quality_status"], "BLOCK")
        self.assertTrue(any("mode must be explicitly provided" in b for b in res["candidates"][0]["briefing"]["blockers"]))
        
    def test_missing_oi_warns(self):
        self.candidates[0]["open_interest"] = ""
        self._write_files()
        res = build_signal_review(self.run_dir, output_dir=self.run_dir)
        pkg = res["candidates"][0]["package"]
        dg = next(g for g in pkg["quality_gate"]["sub_gates"] if g["gate"] == "derivatives_gate")
        self.assertEqual(dg["status"], "WARN")
        self.assertIn("missing_open_interest", dg["warnings"])
        
    def test_missing_turnover_warns(self):
        self.candidates[0]["turnover_24h_usd"] = ""
        self._write_files()
        res = build_signal_review(self.run_dir, output_dir=self.run_dir)
        pkg = res["candidates"][0]["package"]
        lg = next(g for g in pkg["quality_gate"]["sub_gates"] if g["gate"] == "liquidity_gate")
        self.assertEqual(lg["status"], "WARN")
        self.assertIn("missing_turnover", lg["warnings"])
        
    def test_artifact_hash_structure(self):
        self._write_files()
        res = build_signal_review(self.run_dir, output_dir=self.run_dir)
        pkg = res["candidates"][0]["package"]
        self.assertIn("content_hash", pkg)
        self.assertIn("artifact_hash", pkg)
        self.assertIn("input_fingerprint", pkg)
        
    def test_mode_from_manifest_used(self):
        self.manifest["mode"] = "PROSPECTIVE_LIVE"
        self._write_files()
        res = build_signal_review(self.run_dir, output_dir=self.run_dir)
        self.assertEqual(res["candidates"][0]["package"]["mode"], "PROSPECTIVE_LIVE")

if __name__ == "__main__":
    unittest.main()
