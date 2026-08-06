import hashlib
import json
from pathlib import Path

import pytest

from harness.lib.local_notification_outbox import (
    LocalOutboxError,
    claim_one_local_notification,
    enqueue_local_notification,
    fail_local_notification,
    local_outbox_status,
    process_one_local_notification,
    recover_local_outbox,
    validate_local_outbox,
)


EVENT = {"event_id": "evt_fixture_001", "event_type": "LOCAL_PAPER_PLAN_PUBLISHED", "payload": {"plan_id": "plan_fixture"}}


def test_local_outbox_is_idempotent_and_never_networked(tmp_path: Path) -> None:
    first = enqueue_local_notification(tmp_path, EVENT)
    second = enqueue_local_notification(tmp_path, EVENT)
    sent = process_one_local_notification(tmp_path)
    assert first["idempotent_replay"] is False
    assert second["idempotent_replay"] is True
    assert sent is not None and sent["delivery_mode"] == "DRY_RUN_NO_NETWORK"
    assert local_outbox_status(tmp_path) == {"pending": 0, "sending": 0, "sent": 1, "dead": 0}
    assert validate_local_outbox(tmp_path) is True


def test_local_outbox_rejects_external_destination_and_detects_tamper(tmp_path: Path) -> None:
    with pytest.raises(LocalOutboxError) as exc:
        enqueue_local_notification(tmp_path, EVENT, destination="feishu:owner")
    assert exc.value.code == "external_destination_forbidden"
    enqueue_local_notification(tmp_path, EVENT)
    path = next((tmp_path / "pending").glob("*.json"))
    path.write_text(path.read_text(encoding="utf-8").replace("plan_fixture", "tampered"), encoding="utf-8")
    assert validate_local_outbox(tmp_path) is False


def test_local_outbox_retries_then_dead_letters_without_delivery(tmp_path: Path) -> None:
    queued = enqueue_local_notification(tmp_path, EVENT)
    first_claim = claim_one_local_notification(tmp_path)
    first_failure = fail_local_notification(tmp_path, first_claim["notification_id"], "fixture_failure", max_attempts=2)
    second_claim = claim_one_local_notification(tmp_path)
    second_failure = fail_local_notification(tmp_path, second_claim["notification_id"], "fixture_failure", max_attempts=2)
    assert queued["notification_id"] == first_claim["notification_id"] == second_claim["notification_id"]
    assert first_failure["status"] == "pending"
    assert second_failure["status"] == "dead"
    assert local_outbox_status(tmp_path) == {"pending": 0, "sending": 0, "sent": 0, "dead": 1}
    assert validate_local_outbox(tmp_path) is True


def test_only_expired_sending_lease_is_recovered(tmp_path: Path) -> None:
    queued = enqueue_local_notification(tmp_path, EVENT)
    claim_one_local_notification(tmp_path)
    recover_local_outbox(tmp_path)
    assert local_outbox_status(tmp_path)["sending"] == 1
    path = next((tmp_path / "sending").glob("*.json"))
    payload = json.loads(path.read_text(encoding="utf-8"))
    payload["claimed_at_utc"] = "2000-01-01T00:00:00+00:00"
    payload["artifact_hash"] = hashlib.sha256(
        json.dumps({key: value for key, value in payload.items() if key != "artifact_hash"}, sort_keys=True, ensure_ascii=False, separators=(",", ":")).encode("utf-8")
    ).hexdigest()
    path.write_text(json.dumps(payload, sort_keys=True, ensure_ascii=False, separators=(",", ":")), encoding="utf-8")
    recover_local_outbox(tmp_path)
    assert queued["notification_id"] == json.loads(next((tmp_path / "pending").glob("*.json")).read_text(encoding="utf-8"))["notification_id"]
    assert local_outbox_status(tmp_path)["pending"] == 1
