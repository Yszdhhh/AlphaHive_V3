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

PROJECT_ROOT = Path(__file__).resolve().parents[1]
ALPHA_HIVE = PROJECT_ROOT.parent / "alpha_hive"
sys.path.insert(0, str(ALPHA_HIVE))

from server.app import app
from fastapi.testclient import TestClient
import server.research_job_repository as repo
import server.signal_review_repository as sr_repo

def _run_client_post(record_id: str, results_dir: str):
    # This runs in a separate process
    # We must patch RESULTS_DIR in this process as well
    with patch("server.research_job_repository.RESULTS_DIR", Path(results_dir)):
        # Mock signal_review_repository.get_signal
        mock_cand = {
            "record_id": record_id,
            "quality_status": "PASS",
            "package_hash": "hash_pass_123",
            "package": {"symbol": "BTC", "price": 50000}
        }
        with patch("server.research_job_service.signal_review_repository.get_signal", return_value=mock_cand):
            client = TestClient(app)
            resp = client.post("/api/research/jobs", json={"record_id": record_id})
            return resp.status_code, resp.json()

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
            "package": {"symbol": "BTC", "price": 50000}
        }
        
        self.mock_candidate_block = {
            "record_id": "rec_block",
            "quality_status": "BLOCK",
            "package_hash": "hash_block_456",
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
        self.assertIsNone(evt1["previous_state"])
        self.assertEqual(evt1["new_state"], "RESEARCH_JOB_CREATED")
        self.assertIsNone(evt1["previous_event_hash"])
        self.assertIn("event_hash", evt1)
        
        self.assertEqual(evt2["sequence"], 2)
        self.assertEqual(evt2["previous_state"], "RESEARCH_JOB_CREATED")
        self.assertEqual(evt2["new_state"], "AWAITING_EVIDENCE")
        self.assertEqual(evt2["previous_event_hash"], evt1["event_hash"])
        self.assertIn("event_hash", evt2)

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
        pkg_hash = hashlib.sha256(b'{"package":{"price":50000,"symbol":"BTC"},"package_hash":"hash_pass_123","quality_status":"PASS","record_id":"rec_001"}').hexdigest()
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

if __name__ == "__main__":
    unittest.main()
