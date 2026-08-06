"""
单元测试：Research Jobs API MVP 001A (Fixed R1)
"""
import sys
import tempfile
import unittest
import json
import hashlib
import uuid
import os
import concurrent.futures
from pathlib import Path
from unittest.mock import patch
import yaml

PROJECT_ROOT = Path(__file__).resolve().parents[1]
ALPHA_HIVE = PROJECT_ROOT.parent / "alpha_hive"
sys.path.insert(0, str(ALPHA_HIVE))

from server.app import app
from fastapi.testclient import TestClient
import server.research_job_repository as repo
import server.signal_review_repository as sr_repo
from server.research_job_service import _preset_hash
from harness.lib.paper_plan_engine import preset_hash as paper_plan_preset_hash

def _run_client_post(record_id: str, results_dir: str):
    # This runs in a separate process
    # We must patch RESULTS_DIR in this process as well
    with patch("server.research_job_repository.RESULTS_DIR", Path(results_dir)):
        # Mock signal_review_repository.get_signal
        mock_cand = {
            "record_id": record_id,
            "quality_status": "PASS",
            "package_hash": "hash_pass_123",
            "mode": "HISTORICAL_REPLAY",
            "scan_time_utc": "2026-07-07T13:41:16+00:00",
            "package": {"symbol": "BTC", "price": 50000}
        }
        with patch("server.research_job_service.signal_review_repository.get_signal", return_value=mock_cand):
            client = TestClient(app)
            resp = client.post("/api/research/jobs", json={"record_id": record_id})
            return resp.status_code, resp.json()

def _run_client_import(job_id: str, bundle: dict, results_dir: str):
    with patch("server.research_job_repository.RESULTS_DIR", Path(results_dir)):
        client = TestClient(app)
        response = client.post(f"/api/research/jobs/{job_id}/evidence/import", json=bundle)
        return response.status_code, response.json()

def _run_client_report(kind: str, job_id: str, report: dict, results_dir: str):
    with patch("server.research_job_repository.RESULTS_DIR", Path(results_dir)):
        client = TestClient(app)
        response = client.post(f"/api/research/jobs/{job_id}/{kind}", json=report)
        return response.status_code, response.json()

def _run_client_owner_decision(job_id: str, decision: dict, results_dir: str):
    with patch("server.research_job_repository.RESULTS_DIR", Path(results_dir)):
        client = TestClient(app)
        response = client.post(f"/api/research/jobs/{job_id}/owner_decision", json=decision)
        return response.status_code, response.json()

def _schema_hash(value):
    return hashlib.sha256(
        json.dumps(value, sort_keys=True, ensure_ascii=False, default=str).encode("utf-8")
    ).hexdigest()

def _rehash_bundle(bundle):
    for artifact in bundle.get("artifacts", []):
        artifact.pop("artifact_hash", None)
        artifact["artifact_hash"] = _schema_hash(artifact)
    bundle.pop("artifact_hash", None)
    bundle["artifact_hash"] = _schema_hash(bundle)
    return bundle

def _valid_bundle(job_id, record_id="rec_001", published_at="2026-07-06T12:00:00+00:00", claim="claim-a"):
    return _rehash_bundle({
        "schema_version": "agent_artifact_bundle_v1",
        "task_id": "external-task-001",
        "job_id": job_id,
        "producer": "manual-test-provider",
        "contract_version": "research_orchestration_contract_v1",
        "input_fingerprint": "f" * 64,
        "observed_at_utc": "2026-07-17T00:00:00+00:00",
        "artifacts": [{
            "artifact_id": "evidence-001",
            "artifact_type": "external_evidence",
            "record_id": record_id,
            "published_at_utc": published_at,
            "source_url": "https://example.invalid/source",
            "claim": claim,
            "tags": ["UNVERIFIED_EXTERNAL_EVIDENCE"],
        }],
        "handoff": {"source_job_id": "provider-neutral-source"},
        "performance_eligible": False,
    })

def _report_hash(payload):
    payload.pop("artifact_hash", None)
    payload["artifact_hash"] = _schema_hash(payload)
    return payload

def _valid_verification(job_id):
    context = repo.get_report_binding_context(job_id, "verification")
    return _report_hash({
        "schema_version": "research_job_verification_v1",
        "job_id": job_id,
        "record_id": context["record_id"],
        "candidate_package_hash": context["candidate_package_hash"],
        "evidence_set_hash": context["evidence_set_hash"],
        "predecessor_hash": context["evidence_import_event_hash"],
        "findings": {
            "source_integrity": "UNVERIFIED",
            "cutoff_adherence": "PASS",
            "duplication": "NONE",
            "prompt_injection_flags": [],
        },
    })

def _valid_assessment(job_id):
    context = repo.get_report_binding_context(job_id, "assessment")
    return _report_hash({
        "schema_version": "research_job_assessment_v1",
        "job_id": job_id,
        "record_id": context["record_id"],
        "candidate_package_hash": context["candidate_package_hash"],
        "evidence_set_hash": context["evidence_set_hash"],
        "verification_hash": context["verification_hash"],
        "predecessor_hash": context["verification_event_hash"],
        "synthesis_findings": {"summary": "Evidence is retained for research review only."},
        "performance_eligible": False,
    })

def _valid_owner_decision(job_id, decision="WATCH"):
    context = repo.get_owner_decision_binding_context(job_id)
    payload = {
        "schema_version": "research_job_owner_decision_v1",
        "job_id": job_id,
        "record_id": context["record_id"],
        "candidate_package_hash": context["candidate_package_hash"],
        "evidence_set_hash": context["evidence_set_hash"],
        "verification_hash": context["verification_hash"],
        "assessment_hash": context["assessment_hash"],
        "predecessor_hash": context["assessment_event_hash"],
        "decision": decision,
        "direction": "NONE" if decision != "APPROVE_PAPER" else "LONG",
        "owner_id": "local_owner_10639",
        "authentication_context": "interactive_owner_confirmation_in_Codex",
        "confirmation_text_version": "owner_decision_confirmation_v1",
        "owner_confirmation": (
            "I confirm that a future, separately identified prospective ResearchJob may enter the "
            "deterministic PaperPlan review path only after all bound evidence, verification, assessment, "
            "eligibility, and risk checks have passed. This is not permission for live trading, trigger "
            "ignition, external notification, or any action for a historical-replay or BLOCK-quality job."
        ),
        "decision_time_utc": "2026-07-18T12:00:00+00:00",
    }
    if decision == "APPROVE_PAPER":
        payload.update({"selected_preset_version": "v0.1.0-draft", "selected_preset_hash": "a" * 64})
    return _report_hash(payload)

class TestResearchJobsMVPR1(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.client = TestClient(app)

    def setUp(self):
        self.tmpdir = tempfile.TemporaryDirectory()
        self.results_dir = Path(self.tmpdir.name)
        
        self.patcher = patch("server.research_job_repository.RESULTS_DIR", self.results_dir)
        self.patcher.start()

        self.mock_candidate_pass = {
            "record_id": "rec_001",
            "quality_status": "PASS",
            "package_hash": "hash_pass_123",
            "mode": "HISTORICAL_REPLAY",
            "scan_time_utc": "2026-07-07T13:41:16+00:00",
            "package": {"symbol": "BTC", "price": 50000}
        }
        
        self.mock_candidate_block = {
            "record_id": "rec_block",
            "quality_status": "BLOCK",
            "package_hash": "hash_block_456",
            "mode": "HISTORICAL_REPLAY",
            "scan_time_utc": "2026-07-07T13:41:16+00:00",
            "package": {"symbol": "ETH", "price": 3000, "quality_status": "BLOCK"}
        }

        def fake_get_signal(record_id: str):
            if record_id == "rec_001":
                return self.mock_candidate_pass
            if record_id == "rec_block":
                return self.mock_candidate_block
            return None

        self.sr_patcher = patch("server.research_job_service.signal_review_repository.get_signal", side_effect=fake_get_signal)
        self.sr_patcher.start()

    def tearDown(self):
        self.patcher.stop()
        self.sr_patcher.stop()
        self.tmpdir.cleanup()

    def test_create_and_read_job(self):
        resp = self.client.post("/api/research/jobs", json={"record_id": "rec_001", "job_id": "client_provided_should_be_ignored"})
        self.assertEqual(resp.status_code, 201)
        data = resp.json()
        job_id = data["job_id"]
        self.assertTrue(job_id.startswith("job_"))
        self.assertEqual(data["record_id"], "rec_001")
        self.assertEqual(data["status"], "AWAITING_EVIDENCE")

        resp_get = self.client.get(f"/api/research/jobs/{job_id}")
        self.assertEqual(resp_get.status_code, 200)
        self.assertEqual(resp_get.json()["job_id"], job_id)

    def test_missing_candidate(self):
        resp = self.client.post("/api/research/jobs", json={"record_id": "rec_not_exist"})
        self.assertEqual(resp.status_code, 404)

    def test_invalid_record_id(self):
        resp = self.client.post("/api/research/jobs", json={"record_id": "../rec_001"})
        self.assertEqual(resp.status_code, 400)
        
        # Windows reserved names
        for name in ["CON", "prn.txt", "AUX", "nul", "COM1", "LPT9"]:
            resp = self.client.post("/api/research/jobs", json={"record_id": name})
            self.assertEqual(resp.status_code, 400, f"Failed blocking Windows reserved name {name}")

    def test_invalid_job_id_format(self):
        resp = self.client.get("/api/research/jobs/job_12345")
        self.assertEqual(resp.status_code, 400)
        
        resp = self.client.get("/api/research/jobs/job_..\\..\\etc\\passwd")
        self.assertEqual(resp.status_code, 400)
        
        resp = self.client.get("/api/research/jobs/not-a-uuid-string")
        self.assertEqual(resp.status_code, 400)

    def test_idempotent_creation(self):
        resp1 = self.client.post("/api/research/jobs", json={"record_id": "rec_001"})
        self.assertEqual(resp1.status_code, 201)
        job_id_1 = resp1.json()["job_id"]

        resp2 = self.client.post("/api/research/jobs", json={"record_id": "rec_001"})
        self.assertEqual(resp2.status_code, 200) 
        self.assertTrue(resp2.json().get("idempotent_replay"))
        self.assertEqual(resp2.json()["job_id"], job_id_1)
        
        # Verify only 1 directory exists + _index
        subdirs = [x for x in self.results_dir.iterdir() if x.is_dir() and x.name != "_index"]
        self.assertEqual(len(subdirs), 1)

    def test_cross_process_concurrency(self):
        # Cross-process concurrency test using ProcessPoolExecutor
        # This truly tests the file system lock using O_EXCL
        with concurrent.futures.ProcessPoolExecutor(max_workers=5) as executor:
            futures = [executor.submit(_run_client_post, "rec_001", str(self.results_dir)) for _ in range(5)]
            responses = [f.result() for f in concurrent.futures.as_completed(futures)]
            
        status_201_count = sum(1 for status, _ in responses if status == 201)
        status_200_count = sum(1 for status, _ in responses if status == 200)
        
        self.assertEqual(status_201_count, 1)
        self.assertEqual(status_200_count, 4)
        
        # All should have the exact same job_id
        job_ids = set(data["job_id"] for _, data in responses)
        self.assertEqual(len(job_ids), 1)
        
        subdirs = [x for x in self.results_dir.iterdir() if x.is_dir() and x.name != "_index"]
        self.assertEqual(len(subdirs), 1)

    def test_block_candidate_capabilities(self):
        resp = self.client.post("/api/research/jobs", json={"record_id": "rec_block"})
        self.assertEqual(resp.status_code, 201)
        job_id = resp.json()["job_id"]
        
        job_json_path = self.results_dir / job_id / "job.json"
        job_data = json.loads(job_json_path.read_text())
        caps = job_data["capabilities"]
        self.assertEqual(caps["paper_plan_capability"], "BLOCK")
        self.assertEqual(caps["research_capability"], "ALLOW")

    def test_event_chain_format_and_sequence(self):
        resp = self.client.post("/api/research/jobs", json={"record_id": "rec_001"})
        job_id = resp.json()["job_id"]
        
        events_path = self.results_dir / job_id / "events.jsonl"
        events = [json.loads(line) for line in events_path.read_text().splitlines() if line.strip()]
        
        self.assertEqual(len(events), 2)
        evt1, evt2 = events[0], events[1]
        
        self.assertEqual(evt1["sequence"], 1)
        self.assertEqual(evt1["event_type"], "RESEARCH_JOB_CREATED")
        self.assertIsNone(evt1["previous_state"])
        self.assertEqual(evt1["new_state"], "RESEARCH_JOB_CREATED")
        self.assertIsNone(evt1["previous_event_hash"])
        self.assertIn("event_hash", evt1)
        
        self.assertEqual(evt2["sequence"], 2)
        self.assertEqual(evt2["event_type"], "STATE_TRANSITION")
        self.assertEqual(evt2["previous_state"], "RESEARCH_JOB_CREATED")
        self.assertEqual(evt2["new_state"], "AWAITING_EVIDENCE")
        self.assertEqual(evt2["previous_event_hash"], evt1["event_hash"])
        self.assertIn("event_hash", evt2)

        pointers = json.loads((self.results_dir / job_id / "pointers.json").read_text())
        for name in ("candidate_package.json", "job.json", "events.jsonl"):
            path = self.results_dir / job_id / name
            self.assertEqual(pointers["file_sizes"][name], path.stat().st_size)

    def test_atomic_write_failure_no_temp_dir_left(self):
        with patch("os.replace", side_effect=Exception("Simulated Replace Failure")):
            resp = self.client.post("/api/research/jobs", json={"record_id": "rec_001"})
            self.assertEqual(resp.status_code, 500)
        
        subdirs = [x for x in self.results_dir.iterdir() if x.is_dir() and x.name != "_index"]
        self.assertEqual(len(subdirs), 0)

    def test_get_rejects_missing_file(self):
        resp = self.client.post("/api/research/jobs", json={"record_id": "rec_001"})
        job_id = resp.json()["job_id"]
        
        (self.results_dir / job_id / "events.jsonl").unlink()
        resp_get = self.client.get(f"/api/research/jobs/{job_id}")
        self.assertEqual(resp_get.status_code, 404)

    def test_get_rejects_tampered_job_json(self):
        resp = self.client.post("/api/research/jobs", json={"record_id": "rec_001"})
        job_id = resp.json()["job_id"]
        
        job_path = self.results_dir / job_id / "job.json"
        job_data = json.loads(job_path.read_text())
        job_data["status"] = "FAKE_STATUS"
        job_path.write_text(json.dumps(job_data))
        
        # Should fail pointer file hash validation
        resp_get = self.client.get(f"/api/research/jobs/{job_id}")
        self.assertEqual(resp_get.status_code, 404)

    def test_get_rejects_tampered_event_chain(self):
        resp = self.client.post("/api/research/jobs", json={"record_id": "rec_001"})
        job_id = resp.json()["job_id"]
        
        events_path = self.results_dir / job_id / "events.jsonl"
        original_content = events_path.read_text()
        
        required_fields = ["event_id", "sequence", "actor_type", "actor_id", "job_id", 
                           "previous_state", "new_state", "input_hashes", "output_hashes", 
                           "previous_event_hash", "timestamp_utc", "event_hash"]
        
        for field in required_fields:
            events = [json.loads(line) for line in original_content.splitlines()]
            # test deletion
            del events[0][field]
            events_path.write_text("\n".join(json.dumps(e) for e in events) + "\n")
            
            resp_get = self.client.get(f"/api/research/jobs/{job_id}")
            self.assertEqual(resp_get.status_code, 404, f"Failed to reject missing field {field}")
            
            # test tampering
            events = [json.loads(line) for line in original_content.splitlines()]
            if field == "sequence":
                events[0][field] = 999
            else:
                events[0][field] = "TAMPERED"
            events_path.write_text("\n".join(json.dumps(e) for e in events) + "\n")
            
            resp_get = self.client.get(f"/api/research/jobs/{job_id}")
            self.assertEqual(resp_get.status_code, 404, f"Failed to reject tampered field {field}")
            
        # Restore
        events_path.write_text(original_content)
        
    def test_get_rejects_tampered_pointers(self):
        resp = self.client.post("/api/research/jobs", json={"record_id": "rec_001"})
        job_id = resp.json()["job_id"]
        
        pointers_path = self.results_dir / job_id / "pointers.json"
        pointers = json.loads(pointers_path.read_text())
        pointers["latest_event_hash"] = "fake_hash_123"
        pointers_path.write_text(json.dumps(pointers))
        
        resp_get = self.client.get(f"/api/research/jobs/{job_id}")
        self.assertEqual(resp_get.status_code, 404)


    def test_write_file_failures(self):
        # candidate_package.json write fail
        with patch("server.research_job_repository._canonical_json", side_effect=[b"ok", Exception("Fail write pkg")]):
            resp = self.client.post("/api/research/jobs", json={"record_id": "rec_001"})
            self.assertEqual(resp.status_code, 500)
        
        # job.json write fail
        with patch("server.research_job_repository.uuid.uuid4", return_value=uuid.UUID(int=1)):
            with patch("builtins.open", side_effect=Exception("Fail write open")):
                resp = self.client.post("/api/research/jobs", json={"record_id": "rec_001"})
                self.assertEqual(resp.status_code, 500)

    def test_staging_validation_failure(self):
        with patch("server.research_job_repository.validate_job_directory", return_value=False):
            resp = self.client.post("/api/research/jobs", json={"record_id": "rec_001"})
            self.assertEqual(resp.status_code, 500)
            
    def test_pending_index_recovery(self):
        # We simulate a true process crash (e.g. power loss) where index is written but replace didn't happen.
        job_id = "job_00000000-0000-0000-0000-000000000001"
        tmp_dir = self.results_dir / f"tmp_{job_id}_test"
        
        # We need a valid tmp_dir for validation to pass
        # Let's just create a valid job first, then copy it to tmp_dir
        resp = self.client.post("/api/research/jobs", json={"record_id": "rec_001"})
        valid_job_id = resp.json()["job_id"]
        valid_job_dir = self.results_dir / valid_job_id
        
        # Actually, we can just rename the valid_job_dir to tmp_dir
        # But we need its events and json to match the expected_job_id, which is valid_job_id.
        # So we'll let index point to valid_job_id!
        # The crash state is: tmp_dir exists (with valid files for valid_job_id), index points to it, but valid_job_dir doesn't exist.
        import shutil
        shutil.move(str(valid_job_dir), str(tmp_dir))
        
        # Now create the pending index
        pkg_hash = hashlib.sha256(repo._canonical_json(self.mock_candidate_pass)).hexdigest()
        index_dir = self.results_dir / "_index"
        idx_file = index_dir / f"rec_001_{pkg_hash}.txt"
        
        # Overwrite index to point to our tmp_dir and valid_job_id
        idx_file.write_text(f"{tmp_dir.name}:{valid_job_id}")
        
        # Now do the second POST. It should recover it!
        resp2 = self.client.post("/api/research/jobs", json={"record_id": "rec_001"})
        self.assertEqual(resp2.status_code, 200) # idempotent
        self.assertTrue(resp2.json()["idempotent_replay"])
            
    def test_published_job_but_index_unfinished_recovery(self):
        # We test that if index is there but points to a successfully published job (because os.replace succeeded previously but index wasn't updated - which we don't do, index is never updated, but we can verify it correctly reads it anyway)
        job_id = "job_00000000-0000-0000-0000-000000000002"
        # Just create the job normally
        resp = self.client.post("/api/research/jobs", json={"record_id": "rec_001"})
        
        # Even if we change index manually
        index_dir = self.results_dir / "_index"
        idx_file = list(index_dir.iterdir())[0]
        # modify index to simulate the pending state again
        idx_file.write_text(f"tmp_missing_123:{resp.json()['job_id']}")
        
        # The next POST should see job_id exists and just return it
        resp2 = self.client.post("/api/research/jobs", json={"record_id": "rec_001"})
        self.assertEqual(resp2.status_code, 200)
        self.assertEqual(resp2.json()["job_id"], resp.json()["job_id"])

    def _create_job(self):
        response = self.client.post("/api/research/jobs", json={"record_id": "rec_001"})
        self.assertEqual(response.status_code, 201)
        return response.json()["job_id"]

    def _create_repository_job(self, record_id, mode="HISTORICAL_REPLAY", scan_time="2026-07-07T13:41:16+00:00"):
        candidate = {
            "record_id": record_id,
            "quality_status": "PASS",
            "package_hash": f"hash_{record_id}",
            "mode": mode,
            "scan_time_utc": scan_time,
            "package": {"symbol": "BTC", "price": 50000},
        }
        job, replay = repo.create_job_atomic(record_id, candidate)
        self.assertFalse(replay)
        return job["job_id"]

    def test_import_accepted_atomic_and_provider_neutral(self):
        job_id = self._create_job()
        response = self.client.post(
            f"/api/research/jobs/{job_id}/evidence/import",
            json=_valid_bundle(job_id),
        )
        self.assertEqual(response.status_code, 201)
        result = response.json()
        self.assertEqual(result["status"], "ACCEPTED")
        self.assertEqual(result["new_job_state"], "EVIDENCE_IMPORTED")

        job_dir = self.results_dir / job_id
        evidence = list((job_dir / "evidence").glob("*.json"))
        attempts = list((job_dir / "imports").glob("*.json"))
        self.assertEqual(len(evidence), 1)
        self.assertEqual(len(attempts), 1)
        self.assertEqual(evidence[0].stem, result["content_hash"])
        self.assertFalse((self.results_dir / "_incoming" / "quarantine" / result["import_id"]).exists())

        events = [json.loads(line) for line in (job_dir / "events.jsonl").read_text().splitlines()]
        self.assertEqual(events[-1]["event_type"], "EVIDENCE_IMPORTED")
        self.assertEqual(events[-1]["import_status"], "ACCEPTED")
        get_response = self.client.get(f"/api/research/jobs/{job_id}")
        self.assertEqual(get_response.status_code, 200)
        self.assertEqual(get_response.json()["status"], "EVIDENCE_IMPORTED")
        self.assertEqual(get_response.json()["capabilities"]["research_capability"], "ALLOW")

    def test_import_schema_rejection_is_persisted_without_state_change(self):
        job_id = self._create_job()
        bundle = _valid_bundle(job_id)
        bundle["schema_version"] = "wrong"
        response = self.client.post(f"/api/research/jobs/{job_id}/evidence/import", json=bundle)
        self.assertEqual(response.status_code, 400)
        self.assertEqual(response.json()["status"], "REJECTED_SCHEMA")

        job_dir = self.results_dir / job_id
        self.assertFalse((job_dir / "evidence").exists())
        attempt = json.loads(next((job_dir / "imports").glob("*.json")).read_text())
        self.assertEqual(attempt["status"], "REJECTED_SCHEMA")
        events = [json.loads(line) for line in (job_dir / "events.jsonl").read_text().splitlines()]
        self.assertEqual(events[-1]["event_type"], "EVIDENCE_IMPORT_REJECTED")
        self.assertEqual(events[-1]["previous_state"], "AWAITING_EVIDENCE")
        self.assertEqual(events[-1]["new_state"], "AWAITING_EVIDENCE")
        self.assertEqual(self.client.get(f"/api/research/jobs/{job_id}").json()["status"], "AWAITING_EVIDENCE")

    def test_import_rejection_statuses_individually(self):
        job_id = self._create_job()
        cases = []
        tampered = _valid_bundle(job_id)
        tampered["artifacts"][0]["claim"] = "tampered"
        cases.append((tampered, "REJECTED_HASH"))
        wrong_job = _valid_bundle(job_id)
        wrong_job["job_id"] = "job_00000000-0000-0000-0000-000000000000"
        _rehash_bundle(wrong_job)
        cases.append((wrong_job, "REJECTED_RECORD_MISMATCH"))
        cases.append((_valid_bundle(job_id, record_id="rec_other"), "REJECTED_RECORD_MISMATCH"))
        cases.append((_valid_bundle(job_id, published_at="2026-07-08T00:00:00+00:00"), "REJECTED_CUTOFF"))
        contradicted_cutoff = _valid_bundle(job_id)
        contradicted_cutoff["artifacts"][0]["cutoff_relation"] = "AFTER_CUTOFF"
        _rehash_bundle(contradicted_cutoff)
        cases.append((contradicted_cutoff, "REJECTED_CUTOFF"))

        for bundle, expected in cases:
            with self.subTest(expected=expected):
                response = self.client.post(f"/api/research/jobs/{job_id}/evidence/import", json=bundle)
                self.assertEqual(response.status_code, 400)
                self.assertEqual(response.json()["status"], expected)

    def test_import_malformed_json_and_path_like_content_hash(self):
        job_id = self._create_job()
        response = self.client.post(
            f"/api/research/jobs/{job_id}/evidence/import",
            content=b'{not-json',
            headers={"content-type": "application/json"},
        )
        self.assertEqual(response.status_code, 400)
        self.assertEqual(response.json()["status"], "REJECTED_SCHEMA")

        duplicate_key = (
            '{"job_id":"' + job_id + '","job_id":"' + job_id + '"}'
        ).encode("utf-8")
        response = self.client.post(
            f"/api/research/jobs/{job_id}/evidence/import",
            content=duplicate_key,
            headers={"content-type": "application/json"},
        )
        self.assertEqual(response.status_code, 400)
        self.assertEqual(response.json()["status"], "REJECTED_SCHEMA")

        response = self.client.post(
            f"/api/research/jobs/{job_id}/evidence/import",
            content=b'{"non_finite":NaN}',
            headers={"content-type": "application/json"},
        )
        self.assertEqual(response.status_code, 400)
        self.assertEqual(response.json()["status"], "REJECTED_SCHEMA")

        bundle = _valid_bundle(job_id)
        bundle["artifacts"][0]["content_hash"] = "../escape"
        _rehash_bundle(bundle)
        response = self.client.post(f"/api/research/jobs/{job_id}/evidence/import", json=bundle)
        self.assertEqual(response.status_code, 400)
        self.assertEqual(response.json()["status"], "REJECTED_SCHEMA")
        self.assertFalse((self.results_dir.parent / "escape.json").exists())

        oversized = _valid_bundle(job_id)
        oversized["padding"] = "x" * (2 * 1024 * 1024)
        response = self.client.post(f"/api/research/jobs/{job_id}/evidence/import", json=oversized)
        self.assertEqual(response.status_code, 400)
        self.assertEqual(response.json()["status"], "REJECTED_SCHEMA")

    def test_import_duplicate_and_concurrent_same_content(self):
        job_id = self._create_job()
        bundle = _valid_bundle(job_id)
        with concurrent.futures.ProcessPoolExecutor(max_workers=5) as executor:
            futures = [
                executor.submit(_run_client_import, job_id, bundle, str(self.results_dir))
                for _ in range(5)
            ]
            responses = [future.result() for future in concurrent.futures.as_completed(futures)]
        self.assertEqual(sum(status == 201 for status, _ in responses), 1)
        self.assertEqual(sum(status == 400 for status, _ in responses), 4)
        self.assertEqual(
            sum(data.get("status") == "DUPLICATE" for _, data in responses),
            4,
        )
        job_dir = self.results_dir / job_id
        self.assertEqual(len(list((job_dir / "evidence").glob("*.json"))), 1)
        self.assertEqual(len(list((job_dir / "imports").glob("*.json"))), 5)
        self.assertEqual(self.client.get(f"/api/research/jobs/{job_id}").status_code, 200)

        replay = _valid_bundle(job_id)
        replay["observed_at_utc"] = "2026-07-18T00:00:00+00:00"
        _rehash_bundle(replay)
        replay_response = self.client.post(f"/api/research/jobs/{job_id}/evidence/import", json=replay)
        self.assertEqual(replay_response.status_code, 400)
        self.assertEqual(replay_response.json()["status"], "DUPLICATE")
        self.assertEqual(len(list((job_dir / "evidence").glob("*.json"))), 1)
        self.assertEqual(len(list((job_dir / "imports").glob("*.json"))), 6)

        novel = _valid_bundle(job_id, claim="novel-evidence")
        novel_response = self.client.post(f"/api/research/jobs/{job_id}/evidence/import", json=novel)
        self.assertEqual(novel_response.status_code, 409)
        self.assertEqual(len(list((job_dir / "imports").glob("*.json"))), 6)

    def test_import_crash_recovery_from_quarantine(self):
        job_id = self._create_job()
        original = repo._atomic_replace_bytes
        failed = {"value": False}

        def fail_once(path, data):
            if path.name == "events.jsonl" and not failed["value"]:
                failed["value"] = True
                raise OSError("simulated crash after quarantine publication")
            return original(path, data)

        with patch("server.research_job_repository._atomic_replace_bytes", side_effect=fail_once):
            response = self.client.post(
                f"/api/research/jobs/{job_id}/evidence/import",
                json=_valid_bundle(job_id),
            )
        self.assertEqual(response.status_code, 500)
        quarantine = self.results_dir / "_incoming" / "quarantine"
        self.assertEqual(len(list(quarantine.glob("imp_*"))), 1)

        recovered = self.client.get(f"/api/research/jobs/{job_id}")
        self.assertEqual(recovered.status_code, 200)
        self.assertEqual(recovered.json()["status"], "EVIDENCE_IMPORTED")
        self.assertEqual(len(list(quarantine.glob("imp_*"))), 0)

    def test_import_tampered_immutable_artifacts_fail_closed(self):
        job_id = self._create_job()
        response = self.client.post(
            f"/api/research/jobs/{job_id}/evidence/import",
            json=_valid_bundle(job_id),
        )
        self.assertEqual(response.status_code, 201)
        job_dir = self.results_dir / job_id
        evidence_path = next((job_dir / "evidence").glob("*.json"))
        evidence_path.write_bytes(evidence_path.read_bytes() + b" ")
        self.assertEqual(self.client.get(f"/api/research/jobs/{job_id}").status_code, 404)

        block_response = self.client.post("/api/research/jobs", json={"record_id": "rec_block"})
        self.assertEqual(block_response.status_code, 201)
        block_job_id = block_response.json()["job_id"]
        accepted = self.client.post(
            f"/api/research/jobs/{block_job_id}/evidence/import",
            json=_valid_bundle(block_job_id, record_id="rec_block"),
        )
        self.assertEqual(accepted.status_code, 201)
        attempt_path = next((self.results_dir / block_job_id / "imports").glob("*.json"))
        attempt = json.loads(attempt_path.read_text())
        attempt["status"] = "ACCEPTED_TAMPERED"
        attempt_path.write_text(json.dumps(attempt))
        self.assertEqual(self.client.get(f"/api/research/jobs/{block_job_id}").status_code, 404)

    def test_import_deep_payload_rejected_and_signal_review_unchanged(self):
        job_id = self._create_job()
        signal_path = Path(sr_repo.RESULTS_DIR) / "latest.json"
        before = hashlib.sha256(signal_path.read_bytes()).hexdigest() if signal_path.exists() else None
        bundle = _valid_bundle(job_id)
        nested = {"leaf": True}
        for _ in range(40):
            nested = {"next": nested}
        bundle["extra"] = nested
        response = self.client.post(f"/api/research/jobs/{job_id}/evidence/import", json=bundle)
        self.assertEqual(response.status_code, 400)
        self.assertEqual(response.json()["status"], "REJECTED_SCHEMA")
        after = hashlib.sha256(signal_path.read_bytes()).hexdigest() if signal_path.exists() else None
        self.assertEqual(before, after)

    def test_import_missing_cutoff_policies_fail_closed(self):
        missing_job_id = self._create_repository_job("rec_missing_cutoff", mode="", scan_time=None)
        missing = self.client.post(
            f"/api/research/jobs/{missing_job_id}/evidence/import",
            json=_valid_bundle(missing_job_id, record_id="rec_missing_cutoff"),
        )
        self.assertEqual(missing.status_code, 400)
        self.assertEqual(missing.json()["status"], "REJECTED_CUTOFF")

        prospective_job_id = self._create_repository_job("rec_prospective", mode="PROSPECTIVE_LIVE")
        prospective = self.client.post(
            f"/api/research/jobs/{prospective_job_id}/evidence/import",
            json=_valid_bundle(prospective_job_id, record_id="rec_prospective"),
        )
        self.assertEqual(prospective.status_code, 400)
        self.assertEqual(prospective.json()["status"], "REJECTED_CUTOFF")

    def test_import_schema_limits_and_timestamp_requirements(self):
        job_id = self._create_job()
        invalid_source = _valid_bundle(job_id)
        invalid_source["artifacts"][0]["source_url"] = None
        _rehash_bundle(invalid_source)

        invalid_timestamp = _valid_bundle(job_id)
        invalid_timestamp["artifacts"][0]["published_at_utc"] = "not-a-timestamp"
        _rehash_bundle(invalid_timestamp)

        invalid_tags = _valid_bundle(job_id)
        invalid_tags["artifacts"][0]["tags"] = "UNVERIFIED_EXTERNAL_EVIDENCE"
        _rehash_bundle(invalid_tags)

        invalid_fingerprint = _valid_bundle(job_id)
        invalid_fingerprint["input_fingerprint"] = "not-a-hash"
        _rehash_bundle(invalid_fingerprint)

        too_many = _valid_bundle(job_id)
        template = dict(too_many["artifacts"][0])
        template.pop("artifact_hash")
        too_many["artifacts"] = []
        for index in range(1001):
            artifact = dict(template)
            artifact["artifact_id"] = f"evidence-{index:04d}"
            artifact["artifact_hash"] = _schema_hash(artifact)
            too_many["artifacts"].append(artifact)
        too_many.pop("artifact_hash")
        too_many["artifact_hash"] = _schema_hash(too_many)

        cases = (invalid_source, invalid_timestamp, invalid_tags, invalid_fingerprint, too_many, [])
        for payload in cases:
            with self.subTest(payload_type=type(payload).__name__):
                response = self.client.post(f"/api/research/jobs/{job_id}/evidence/import", json=payload)
                self.assertEqual(response.status_code, 400)
                self.assertEqual(response.json()["status"], "REJECTED_SCHEMA")
        self.assertEqual(self.client.get(f"/api/research/jobs/{job_id}").json()["status"], "AWAITING_EVIDENCE")

    def test_import_failure_before_manifest_leaves_no_authoritative_artifact(self):
        job_id = self._create_job()
        original = repo._write_and_fsync

        def fail_manifest(path, data):
            if path.name == "manifest.json":
                raise OSError("simulated failure before manifest publication")
            return original(path, data)

        with patch("server.research_job_repository._write_and_fsync", side_effect=fail_manifest):
            response = self.client.post(
                f"/api/research/jobs/{job_id}/evidence/import",
                json=_valid_bundle(job_id),
            )
        self.assertEqual(response.status_code, 500)
        job_dir = self.results_dir / job_id
        self.assertFalse((job_dir / "imports").exists())
        self.assertFalse((job_dir / "evidence").exists())
        quarantine = self.results_dir / "_incoming" / "quarantine"
        self.assertEqual(list(quarantine.glob("imp_*")), [])
        get_response = self.client.get(f"/api/research/jobs/{job_id}")
        self.assertEqual(get_response.status_code, 200)
        self.assertEqual(get_response.json()["status"], "AWAITING_EVIDENCE")

    def test_import_recovery_all_publication_failure_points(self):
        failure_points = ("immutable", "events.jsonl", "job.json", "pointers.json")
        for index, failure_point in enumerate(failure_points):
            with self.subTest(failure_point=failure_point):
                record_id = f"rec_failure_{index}"
                job_id = self._create_repository_job(record_id)
                failed = {"value": False}
                if failure_point == "immutable":
                    original = repo._write_immutable

                    def fail_once(path, data):
                        if not failed["value"]:
                            failed["value"] = True
                            raise OSError("simulated immutable publication failure")
                        return original(path, data)

                    patcher = patch("server.research_job_repository._write_immutable", side_effect=fail_once)
                else:
                    original = repo._atomic_replace_bytes

                    def fail_once(path, data, target=failure_point):
                        if path.name == target and not failed["value"]:
                            failed["value"] = True
                            raise OSError(f"simulated {target} replacement failure")
                        return original(path, data)

                    patcher = patch("server.research_job_repository._atomic_replace_bytes", side_effect=fail_once)

                with patcher:
                    response = self.client.post(
                        f"/api/research/jobs/{job_id}/evidence/import",
                        json=_valid_bundle(job_id, record_id=record_id),
                    )
                self.assertEqual(response.status_code, 500)
                recovered = self.client.get(f"/api/research/jobs/{job_id}")
                self.assertEqual(recovered.status_code, 200)
                self.assertEqual(recovered.json()["status"], "EVIDENCE_IMPORTED")

    def test_quarantine_orphan_cleanup_is_job_scoped(self):
        first_job_id = self._create_job()
        second_job_id = self._create_repository_job("rec_second_job")
        stage_dir = self.results_dir / "_incoming" / "quarantine" / f"imp_{uuid.uuid4()}"
        stage_dir.mkdir(parents=True)
        (stage_dir / "job_id").write_text(second_job_id)
        (stage_dir / "partial.tmp").write_text("partial")

        self.assertEqual(self.client.get(f"/api/research/jobs/{first_job_id}").status_code, 200)
        self.assertTrue(stage_dir.exists())
        self.assertEqual(self.client.get(f"/api/research/jobs/{second_job_id}").status_code, 200)
        self.assertFalse(stage_dir.exists())

    def test_immutable_publication_retries_short_writes(self):
        destination = self.results_dir / "short-write.bin"
        payload = b"x" * 65537
        original_write = os.write

        def short_write(fd, data):
            size = max(1, len(data) // 2)
            return original_write(fd, bytes(data[:size]))

        with patch("server.research_job_repository.os.write", side_effect=short_write):
            repo._write_immutable(destination, payload)
        self.assertEqual(destination.read_bytes(), payload)

    def test_mvp002_verification_and_assessment_are_versioned_and_immutable(self):
        job_id = self._create_job()
        self.assertEqual(self.client.post(
            f"/api/research/jobs/{job_id}/evidence/import", json=_valid_bundle(job_id)
        ).status_code, 201)
        verification = self.client.post(
            f"/api/research/jobs/{job_id}/verification", json=_valid_verification(job_id)
        )
        self.assertEqual(verification.status_code, 201)
        self.assertEqual(verification.json()["new_job_state"], "EVIDENCE_VERIFIED")
        job_dir = self.results_dir / job_id
        verification_path = job_dir / "verification" / "v0001.json"
        self.assertTrue(verification_path.exists())
        self.assertEqual(self.client.get(f"/api/research/jobs/{job_id}").json()["status"], "EVIDENCE_VERIFIED")

        assessment = self.client.post(
            f"/api/research/jobs/{job_id}/assessment", json=_valid_assessment(job_id)
        )
        self.assertEqual(assessment.status_code, 201)
        self.assertEqual(assessment.json()["new_job_state"], "RESEARCH_ASSESSMENT_READY")
        assessment_path = job_dir / "assessment" / "v0001.json"
        self.assertTrue(assessment_path.exists())
        pointers = json.loads((job_dir / "pointers.json").read_text())
        self.assertEqual(pointers["verification_files"], ["verification/v0001.json"])
        self.assertEqual(pointers["assessment_files"], ["assessment/v0001.json"])
        assessment_path.write_bytes(assessment_path.read_bytes() + b" ")
        self.assertEqual(self.client.get(f"/api/research/jobs/{job_id}").status_code, 404)

    def test_mvp002_rejects_binding_invalid_state_and_directional_content(self):
        job_id = self._create_job()
        self.assertEqual(self.client.post(
            f"/api/research/jobs/{job_id}/evidence/import", json=_valid_bundle(job_id)
        ).status_code, 201)
        invalid_assessment = self.client.post(
            f"/api/research/jobs/{job_id}/assessment", json={}
        )
        self.assertEqual(invalid_assessment.status_code, 409)

        bad = _valid_verification(job_id)
        bad["evidence_set_hash"] = "0" * 64
        _report_hash(bad)
        rejected = self.client.post(f"/api/research/jobs/{job_id}/verification", json=bad)
        self.assertEqual(rejected.status_code, 400)
        self.assertEqual(rejected.json()["status"], "REJECTED_BINDING")
        self.assertEqual(self.client.get(f"/api/research/jobs/{job_id}").json()["status"], "EVIDENCE_IMPORTED")

        self.assertEqual(self.client.post(
            f"/api/research/jobs/{job_id}/verification", json=_valid_verification(job_id)
        ).status_code, 201)
        directional = _valid_assessment(job_id)
        directional["synthesis_findings"] = "BUY now"
        _report_hash(directional)
        response = self.client.post(f"/api/research/jobs/{job_id}/assessment", json=directional)
        self.assertEqual(response.status_code, 400)
        self.assertEqual(response.json()["status"], "REJECTED_SCHEMA")
        self.assertEqual(self.client.get(f"/api/research/jobs/{job_id}").json()["status"], "EVIDENCE_VERIFIED")

    def test_mvp003_watch_is_immutable_and_tamper_fails_closed(self):
        job_id = self._create_job()
        self.assertEqual(self.client.post(f"/api/research/jobs/{job_id}/evidence/import", json=_valid_bundle(job_id)).status_code, 201)
        self.assertEqual(self.client.post(f"/api/research/jobs/{job_id}/verification", json=_valid_verification(job_id)).status_code, 201)
        self.assertEqual(self.client.post(f"/api/research/jobs/{job_id}/assessment", json=_valid_assessment(job_id)).status_code, 201)
        response = self.client.post(f"/api/research/jobs/{job_id}/owner_decision", json=_valid_owner_decision(job_id, "WATCH"))
        self.assertEqual(response.status_code, 201)
        self.assertEqual(response.json()["new_job_state"], "WATCHLISTED")
        job_dir = self.results_dir / job_id
        artifact = job_dir / "owner_decisions" / "v0001.json"
        self.assertTrue(artifact.exists())
        self.assertEqual(json.loads((job_dir / "pointers.json").read_text())["owner_decision_files"], ["owner_decisions/v0001.json"])
        artifact.write_bytes(artifact.read_bytes() + b" ")
        self.assertEqual(self.client.get(f"/api/research/jobs/{job_id}").status_code, 404)

    def test_mvp003_historical_approve_paper_is_rejected_without_transition(self):
        job_id = self._create_job()
        self.assertEqual(self.client.post(f"/api/research/jobs/{job_id}/evidence/import", json=_valid_bundle(job_id)).status_code, 201)
        self.assertEqual(self.client.post(f"/api/research/jobs/{job_id}/verification", json=_valid_verification(job_id)).status_code, 201)
        self.assertEqual(self.client.post(f"/api/research/jobs/{job_id}/assessment", json=_valid_assessment(job_id)).status_code, 201)
        response = self.client.post(f"/api/research/jobs/{job_id}/owner_decision", json=_valid_owner_decision(job_id, "APPROVE_PAPER"))
        self.assertEqual(response.status_code, 400)
        self.assertEqual(response.json()["status"], "REJECTED_SCHEMA")
        self.assertIn("HISTORICAL_MODE_BLOCKED", response.json()["error_codes"])
        job_dir = self.results_dir / job_id
        rejection = json.loads(next((job_dir / "imports").glob("dec_*.json")).read_text())
        self.assertEqual(rejection["attempt_kind"], "owner_decision")
        self.assertEqual(rejection["status"], "REJECTED_SCHEMA")
        events = [json.loads(line) for line in (job_dir / "events.jsonl").read_text().splitlines()]
        self.assertEqual(events[-1]["event_type"], "OWNER_DECISION_REJECTED")
        self.assertEqual(self.client.get(f"/api/research/jobs/{job_id}").json()["status"], "RESEARCH_ASSESSMENT_READY")

    def test_mvp003_preset_hash_matches_paper_plan_engine(self):
        preset_path = PROJECT_ROOT / "config" / "paper_execution_presets.yaml"
        preset = yaml.safe_load(preset_path.read_text(encoding="utf-8"))
        self.assertEqual(preset["preset_version"], "v0.1.0")
        self.assertEqual(preset["status"], "APPROVED")
        self.assertEqual(_preset_hash(preset), paper_plan_preset_hash(preset))
        self.assertEqual(
            _preset_hash(preset),
            "a81ad47bbb332ef26d2399c7fae1e58ce1232534406f8b140f9654dd16edb958",
        )

    def test_mvp003_owner_decision_recovers_and_accepts_once_under_contention(self):
        recovery_job = self._create_job()
        self.assertEqual(self.client.post(f"/api/research/jobs/{recovery_job}/evidence/import", json=_valid_bundle(recovery_job)).status_code, 201)
        self.assertEqual(self.client.post(f"/api/research/jobs/{recovery_job}/verification", json=_valid_verification(recovery_job)).status_code, 201)
        self.assertEqual(self.client.post(f"/api/research/jobs/{recovery_job}/assessment", json=_valid_assessment(recovery_job)).status_code, 201)
        original = repo._atomic_replace_bytes
        failed = {"value": False}

        def fail_once(path, data):
            if path.name == "events.jsonl" and not failed["value"]:
                failed["value"] = True
                raise OSError("simulated OwnerDecision crash")
            return original(path, data)

        with patch("server.research_job_repository._atomic_replace_bytes", side_effect=fail_once):
            response = self.client.post(
                f"/api/research/jobs/{recovery_job}/owner_decision", json=_valid_owner_decision(recovery_job, "WATCH")
            )
        self.assertEqual(response.status_code, 500)
        self.assertEqual(self.client.get(f"/api/research/jobs/{recovery_job}").json()["status"], "WATCHLISTED")

        concurrent_record = "rec_owner_contention"
        concurrent_job = self._create_repository_job(concurrent_record)
        self.assertEqual(self.client.post(f"/api/research/jobs/{concurrent_job}/evidence/import", json=_valid_bundle(concurrent_job, record_id=concurrent_record)).status_code, 201)
        self.assertEqual(self.client.post(f"/api/research/jobs/{concurrent_job}/verification", json=_valid_verification(concurrent_job)).status_code, 201)
        self.assertEqual(self.client.post(f"/api/research/jobs/{concurrent_job}/assessment", json=_valid_assessment(concurrent_job)).status_code, 201)
        decision = _valid_owner_decision(concurrent_job, "WATCH")
        with concurrent.futures.ProcessPoolExecutor(max_workers=5) as executor:
            futures = [
                executor.submit(_run_client_owner_decision, concurrent_job, decision, str(self.results_dir))
                for _ in range(5)
            ]
            responses = [future.result() for future in concurrent.futures.as_completed(futures)]
        self.assertEqual(sum(status == 201 for status, _ in responses), 1)
        self.assertEqual(sum(status == 409 for status, _ in responses), 4)
        job_dir = self.results_dir / concurrent_job
        self.assertEqual(len(list((job_dir / "owner_decisions").glob("v*.json"))), 1)
        self.assertEqual(self.client.get(f"/api/research/jobs/{concurrent_job}").json()["status"], "WATCHLISTED")

    def test_mvp002_duplicate_and_report_recovery(self):
        job_id = self._create_job()
        self.assertEqual(self.client.post(
            f"/api/research/jobs/{job_id}/evidence/import", json=_valid_bundle(job_id)
        ).status_code, 201)
        report = _valid_verification(job_id)
        self.assertEqual(self.client.post(
            f"/api/research/jobs/{job_id}/verification", json=report
        ).status_code, 201)
        duplicate = self.client.post(f"/api/research/jobs/{job_id}/verification", json=report)
        self.assertEqual(duplicate.status_code, 400)
        self.assertEqual(duplicate.json()["status"], "DUPLICATE")
        self.assertEqual(len(list((self.results_dir / job_id / "verification").glob("*.json"))), 1)

        recovery_job = self._create_repository_job("rec_report_recovery")
        self.assertEqual(self.client.post(
            f"/api/research/jobs/{recovery_job}/evidence/import", json=_valid_bundle(recovery_job, record_id="rec_report_recovery")
        ).status_code, 201)
        original = repo._atomic_replace_bytes
        failed = {"value": False}
        def fail_once(path, data):
            if path.name == "events.jsonl" and not failed["value"]:
                failed["value"] = True
                raise OSError("simulated report crash")
            return original(path, data)
        with patch("server.research_job_repository._atomic_replace_bytes", side_effect=fail_once):
            response = self.client.post(
                f"/api/research/jobs/{recovery_job}/verification", json=_valid_verification(recovery_job)
            )
        self.assertEqual(response.status_code, 500)
        recovered = self.client.get(f"/api/research/jobs/{recovery_job}")
        self.assertEqual(recovered.status_code, 200)
        self.assertEqual(recovered.json()["status"], "EVIDENCE_VERIFIED")

    def test_mvp002_concurrent_verification_accepts_once(self):
        job_id = self._create_job()
        self.assertEqual(self.client.post(
            f"/api/research/jobs/{job_id}/evidence/import", json=_valid_bundle(job_id)
        ).status_code, 201)
        report = _valid_verification(job_id)
        with concurrent.futures.ProcessPoolExecutor(max_workers=5) as executor:
            futures = [
                executor.submit(_run_client_report, "verification", job_id, report, str(self.results_dir))
                for _ in range(5)
            ]
            responses = [future.result() for future in concurrent.futures.as_completed(futures)]
        self.assertEqual(sum(status == 201 for status, _ in responses), 1)
        self.assertEqual(sum(data.get("status") == "DUPLICATE" for _, data in responses), 4)
        job_dir = self.results_dir / job_id
        self.assertEqual(len(list((job_dir / "verification").glob("*.json"))), 1)
        self.assertEqual(self.client.get(f"/api/research/jobs/{job_id}").json()["status"], "EVIDENCE_VERIFIED")

if __name__ == "__main__":
    unittest.main()
