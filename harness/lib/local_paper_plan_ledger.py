"""Durable local-only ledger for already-built PaperPlan fixtures.

This is intentionally not connected to the ResearchJob service, a scheduler,
an exchange, or a network client.  A caller must provide an explicit local
root (normally a temporary test directory).  It is therefore safe to exercise
the immutable PaperPlan lifecycle without creating a production PaperPlan.
"""
from __future__ import annotations

import hashlib
import json
import os
import shutil
import time
import uuid
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from .paper_plan_engine import canonical_json, content_hash


class LocalPaperPlanLedgerError(ValueError):
    """A fail-closed local-ledger rejection."""

    def __init__(self, code: str):
        self.code = code
        super().__init__(code)


def _bytes(value: Any) -> bytes:
    return canonical_json(value).encode("utf-8")


def _sha256(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def _fsync_directory(path: Path) -> None:
    try:
        fd = os.open(str(path), os.O_RDONLY)
    except OSError:
        return
    try:
        os.fsync(fd)
    finally:
        os.close(fd)


def _write(path: Path, data: bytes) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("wb") as handle:
        handle.write(data)
        handle.flush()
        os.fsync(handle.fileno())


def _event_hash(event: dict[str, Any]) -> str:
    return content_hash({key: value for key, value in event.items() if key != "event_hash"})


def _validate_plan(plan: dict[str, Any]) -> None:
    if not isinstance(plan, dict) or plan.get("schema_version") != "paper_plan_v1":
        raise LocalPaperPlanLedgerError("invalid_plan_schema")
    if plan.get("no_live_order_path") is not True:
        raise LocalPaperPlanLedgerError("live_order_path_forbidden")
    stored_hash = plan.get("artifact_hash")
    actual_hash = content_hash({key: value for key, value in plan.items() if key != "artifact_hash"})
    if not isinstance(stored_hash, str) or stored_hash != actual_hash:
        raise LocalPaperPlanLedgerError("plan_hash_mismatch")
    if not isinstance(plan.get("plan_id"), str) or not isinstance(plan.get("record_id"), str):
        raise LocalPaperPlanLedgerError("plan_identity_missing")


def _lock(root: Path):
    class _Lock:
        def __enter__(self):
            self.path = root / ".ledger.lock"
            root.mkdir(parents=True, exist_ok=True)
            for _ in range(200):
                try:
                    self.fd = os.open(str(self.path), os.O_CREAT | os.O_EXCL | os.O_WRONLY)
                    return self
                except FileExistsError:
                    time.sleep(0.005)
            raise LocalPaperPlanLedgerError("ledger_busy")

        def __exit__(self, *_unused):
            try:
                os.close(self.fd)
            except OSError:
                pass
            try:
                self.path.unlink()
            except FileNotFoundError:
                pass
            _fsync_directory(root)

    return _Lock()


def _relative_plan_files(root: Path) -> list[str]:
    plans = root / "plans"
    if not plans.exists():
        return []
    return sorted(f"plans/{path.name}" for path in plans.glob("v[0-9][0-9][0-9][0-9].json"))


def recover_local_paper_plan_ledger(root: str | Path) -> None:
    """Finish a durable staged publication, or remove an uncommitted stage."""
    root = Path(root)
    staging_root = root / "_staging"
    if not staging_root.exists():
        return
    for stage in sorted(path for path in staging_root.iterdir() if path.is_dir()):
        manifest_path = stage / "manifest.json"
        if not manifest_path.exists():
            shutil.rmtree(stage, ignore_errors=True)
            continue
        manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
        if manifest.get("schema_version") != "local_paper_plan_ledger_transaction_v1":
            raise LocalPaperPlanLedgerError("invalid_staging_manifest")
        for item in manifest.get("immutable", []):
            staged = stage / item["staged"]
            data = staged.read_bytes()
            if _sha256(data) != item["sha256"]:
                raise LocalPaperPlanLedgerError("staged_hash_mismatch")
            target = root / item["target"]
            if target.exists():
                if target.read_bytes() != data:
                    raise LocalPaperPlanLedgerError("immutable_target_conflict")
            else:
                target.parent.mkdir(parents=True, exist_ok=True)
                os.replace(staged, target)
        for item in manifest.get("mutable", []):
            staged = stage / item["staged"]
            data = staged.read_bytes()
            if _sha256(data) != item["sha256"]:
                raise LocalPaperPlanLedgerError("staged_hash_mismatch")
            target = root / item["target"]
            target.parent.mkdir(parents=True, exist_ok=True)
            os.replace(staged, target)
        _fsync_directory(root)
        shutil.rmtree(stage, ignore_errors=True)
    if staging_root.exists() and not any(staging_root.iterdir()):
        staging_root.rmdir()


def validate_local_paper_plan_ledger(root: str | Path) -> bool:
    root = Path(root)
    try:
        recover_local_paper_plan_ledger(root)
        pointers_path = root / "pointers.json"
        events_path = root / "events.jsonl"
        files = _relative_plan_files(root)
        if not pointers_path.exists() and not events_path.exists():
            return not files
        if not pointers_path.exists() or not events_path.exists():
            return False
        pointers = json.loads(pointers_path.read_text(encoding="utf-8"))
        if pointers.get("schema_version") != "local_paper_plan_ledger_v1":
            return False
        if pointers.get("plan_files") != files or len(files) != 1:
            return False
        if pointers.get("active_plan_file") != files[0]:
            return False
        file_hashes = pointers.get("file_hashes", {})
        file_sizes = pointers.get("file_sizes", {})
        expected = {"events.jsonl": events_path.read_bytes()}
        for relative in files:
            expected[relative] = (root / relative).read_bytes()
        for name, data in expected.items():
            if file_hashes.get(name) != _sha256(data) or file_sizes.get(name) != len(data):
                return False
        plan = json.loads(expected[files[0]])
        _validate_plan(plan)
        events = [json.loads(line) for line in expected["events.jsonl"].decode("utf-8").splitlines() if line.strip()]
        if len(events) != 1:
            return False
        event = events[0]
        if (
            event.get("sequence") != 1
            or event.get("previous_event_hash") is not None
            or event.get("event_type") != "LOCAL_PAPER_PLAN_PUBLISHED"
            or event.get("new_state") != "PAPER_PLAN_ACTIVE"
            or event.get("plan_artifact_hash") != plan.get("artifact_hash")
            or event.get("event_hash") != _event_hash(event)
            or pointers.get("latest_event_hash") != event.get("event_hash")
        ):
            return False
        return True
    except Exception:
        return False


def publish_local_paper_plan(root: str | Path, plan: dict[str, Any]) -> dict[str, Any]:
    """Publish one synthetic/local plan through an immutable staged ledger.

    ``root`` is required so this API cannot silently write to an authoritative
    ResearchJob directory.
    """
    root = Path(root)
    _validate_plan(plan)
    with _lock(root):
        recover_local_paper_plan_ledger(root)
        if not validate_local_paper_plan_ledger(root):
            raise LocalPaperPlanLedgerError("ledger_corrupt")
        pointers_path = root / "pointers.json"
        if pointers_path.exists():
            pointers = json.loads(pointers_path.read_text(encoding="utf-8"))
            current = root / pointers["active_plan_file"]
            current_plan = json.loads(current.read_text(encoding="utf-8"))
            if current_plan.get("artifact_hash") == plan["artifact_hash"]:
                return {
                    "status": "ACCEPTED",
                    "version": current.stem,
                    "plan_file": pointers["active_plan_file"],
                    "idempotent_replay": True,
                }
            raise LocalPaperPlanLedgerError("active_plan_exists")

        version = "v0001"
        relative = f"plans/{version}.json"
        plan_bytes = _bytes(plan)
        now = datetime.now(timezone.utc).isoformat()
        event = {
            "schema_version": "local_paper_plan_event_v1",
            "event_id": f"evt_{uuid.uuid4()}",
            "sequence": 1,
            "event_type": "LOCAL_PAPER_PLAN_PUBLISHED",
            "previous_state": None,
            "new_state": "PAPER_PLAN_ACTIVE",
            "previous_event_hash": None,
            "timestamp_utc": now,
            "plan_id": plan["plan_id"],
            "plan_artifact_hash": plan["artifact_hash"],
        }
        event["event_hash"] = _event_hash(event)
        events_bytes = _bytes(event) + b"\n"
        pointers = {
            "schema_version": "local_paper_plan_ledger_v1",
            "active_plan_file": relative,
            "plan_files": [relative],
            "latest_event_hash": event["event_hash"],
            "file_hashes": {relative: _sha256(plan_bytes), "events.jsonl": _sha256(events_bytes)},
            "file_sizes": {relative: len(plan_bytes), "events.jsonl": len(events_bytes)},
        }
        pointers_bytes = _bytes(pointers)
        stage = root / "_staging" / f"plan_{uuid.uuid4()}"
        stage.mkdir(parents=True)
        _write(stage / "plan.json", plan_bytes)
        _write(stage / "events.jsonl", events_bytes)
        _write(stage / "pointers.json", pointers_bytes)
        manifest = {
            "schema_version": "local_paper_plan_ledger_transaction_v1",
            "immutable": [{"staged": "plan.json", "target": relative, "sha256": _sha256(plan_bytes)}],
            "mutable": [
                {"staged": "events.jsonl", "target": "events.jsonl", "sha256": _sha256(events_bytes)},
                {"staged": "pointers.json", "target": "pointers.json", "sha256": _sha256(pointers_bytes)},
            ],
        }
        _write(stage / "manifest.json", _bytes(manifest))
        _fsync_directory(stage)
        _fsync_directory(stage.parent)
        recover_local_paper_plan_ledger(root)
        if not validate_local_paper_plan_ledger(root):
            raise LocalPaperPlanLedgerError("publication_validation_failed")
        return {"status": "ACCEPTED", "version": version, "plan_file": relative, "idempotent_replay": False}
