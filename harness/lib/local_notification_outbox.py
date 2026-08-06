"""A no-network notification outbox for local lifecycle testing.

It accepts only ``local:`` destinations and has no HTTP, Feishu, bot, secret,
or scheduler dependency.  Production delivery must use a separate, explicitly
authorized adapter rather than extending this module in place.
"""
from __future__ import annotations

import hashlib
import json
import os
import time
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


class LocalOutboxError(ValueError):
    def __init__(self, code: str):
        self.code = code
        super().__init__(code)


STATES = ("pending", "sending", "sent", "dead")


def _canonical(value: Any) -> bytes:
    return json.dumps(value, sort_keys=True, ensure_ascii=False, separators=(",", ":")).encode("utf-8")


def _hash(value: Any) -> str:
    return hashlib.sha256(_canonical(value)).hexdigest()


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


def _utc(value: Any) -> datetime | None:
    if not isinstance(value, str):
        return None
    try:
        parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
    except ValueError:
        return None
    return parsed.astimezone(timezone.utc) if parsed.tzinfo is not None else None


def _write(path: Path, value: dict[str, Any]) -> None:
    data = _canonical(value)
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("wb") as handle:
        handle.write(data)
        handle.flush()
        os.fsync(handle.fileno())


def _with_hash(value: dict[str, Any]) -> dict[str, Any]:
    out = dict(value)
    out["artifact_hash"] = _hash({key: item for key, item in out.items() if key != "artifact_hash"})
    return out


def _paths(root: Path, key: str) -> list[Path]:
    return [root / state / f"{key}.json" for state in STATES]


def _read(path: Path) -> dict[str, Any]:
    payload = json.loads(path.read_text(encoding="utf-8"))
    stored = payload.get("artifact_hash")
    actual = _hash({key: item for key, item in payload.items() if key != "artifact_hash"})
    if stored != actual:
        raise LocalOutboxError("notification_hash_mismatch")
    return payload


def recover_local_outbox(root: str | Path, *, claim_lease_seconds: float = 30.0) -> None:
    """Recover only an expired sending lease; live claims are left untouched."""
    root = Path(root)
    for state in STATES:
        (root / state).mkdir(parents=True, exist_ok=True)
    seen: dict[str, list[tuple[str, Path, dict[str, Any]]]] = {}
    for state in STATES:
        for path in sorted((root / state).glob("*.json")):
            key = path.stem
            seen.setdefault(key, []).append((state, path, _read(path)))
    for entries in seen.values():
        if len(entries) == 1:
            continue
        terminal = [entry for entry in entries if entry[0] in {"sent", "dead"}]
        interrupted = [entry for entry in entries if entry[0] == "sending"]
        same_identity = len({entry[2].get("notification_id") for entry in entries}) == 1
        if len(terminal) == 1 and len(interrupted) == len(entries) - 1 and same_identity:
            for _, path, _ in interrupted:
                path.unlink()
            continue
        raise LocalOutboxError("duplicate_notification_state")
    for path in sorted((root / "sending").glob("*.json")):
        payload = _read(path)
        claimed_at = _utc(payload.get("claimed_at_utc"))
        if claimed_at is not None and (datetime.now(timezone.utc) - claimed_at).total_seconds() <= claim_lease_seconds:
            continue
        payload["status"] = "pending"
        payload["last_error"] = "recovered_interrupted_dry_run"
        payload["updated_at_utc"] = _now()
        payload["claim_token"] = None
        payload["claimed_at_utc"] = None
        payload = _with_hash(payload)
        target = root / "pending" / path.name
        _write(target, payload)
        path.unlink()


def validate_local_outbox(root: str | Path) -> bool:
    root = Path(root)
    try:
        recover_local_outbox(root)
        seen: set[str] = set()
        for state in STATES:
            for path in (root / state).glob("*.json"):
                if path.stem in seen:
                    return False
                seen.add(path.stem)
                payload = _read(path)
                if payload.get("schema_version") != "local_notification_outbox_v1":
                    return False
                if payload.get("status") != state:
                    return False
                if not str(payload.get("destination", "")).startswith("local:"):
                    return False
                if payload.get("payload_hash") != _hash(payload.get("payload")):
                    return False
                if not isinstance(payload.get("attempt_count"), int) or payload["attempt_count"] < 0:
                    return False
        return True
    except Exception:
        return False


def enqueue_local_notification(root: str | Path, event: dict[str, Any], *, destination: str = "local:dry-run") -> dict[str, Any]:
    """Durably queue one local-only event, keyed for idempotent replay."""
    root = Path(root)
    if not isinstance(event, dict) or not isinstance(event.get("event_id"), str) or not event.get("event_id"):
        raise LocalOutboxError("invalid_event")
    if not isinstance(event.get("event_type"), str) or not event.get("event_type"):
        raise LocalOutboxError("invalid_event")
    if not destination.startswith("local:"):
        raise LocalOutboxError("external_destination_forbidden")
    recover_local_outbox(root)
    payload = {"event_id": event["event_id"], "event_type": event["event_type"], "payload": event.get("payload", {})}
    payload_hash = _hash(payload["payload"])
    key = _hash({"event_id": event["event_id"], "event_type": event["event_type"], "payload_hash": payload_hash, "destination": destination})
    existing = [path for path in _paths(root, key) if path.exists()]
    if existing:
        return {"status": "ACCEPTED", "notification_id": _read(existing[0])["notification_id"], "idempotent_replay": True}
    envelope = _with_hash({
        "schema_version": "local_notification_outbox_v1",
        "notification_id": "ntf_" + key[:32],
        "idempotency_key": key,
        "destination": destination,
        "payload": payload["payload"],
        "payload_hash": payload_hash,
        "source_event_id": event["event_id"],
        "source_event_type": event["event_type"],
        "status": "pending",
        "attempt_count": 0,
        "created_at_utc": _now(),
        "updated_at_utc": _now(),
        "last_error": None,
    })
    path = root / "pending" / f"{key}.json"
    path.parent.mkdir(parents=True, exist_ok=True)
    try:
        fd = os.open(str(path), os.O_CREAT | os.O_EXCL | os.O_WRONLY)
    except FileExistsError:
        return {"status": "ACCEPTED", "notification_id": _read(path)["notification_id"], "idempotent_replay": True}
    try:
        data = _canonical(envelope)
        os.write(fd, data)
        os.fsync(fd)
    finally:
        os.close(fd)
    return {"status": "ACCEPTED", "notification_id": envelope["notification_id"], "idempotent_replay": False}


def claim_one_local_notification(root: str | Path) -> dict[str, Any] | None:
    """Atomically claim one pending local-only notification for dry-run work."""
    root = Path(root)
    recover_local_outbox(root)
    pending = sorted((root / "pending").glob("*.json"))
    if not pending:
        return None
    source = pending[0]
    sending = root / "sending" / source.name
    try:
        os.replace(source, sending)
    except FileNotFoundError:
        return None
    payload = _read(sending)
    payload["attempt_count"] += 1
    payload["status"] = "sending"
    payload["updated_at_utc"] = _now()
    payload["claim_token"] = "claim_" + os.urandom(8).hex()
    payload["claimed_at_utc"] = payload["updated_at_utc"]
    payload = _with_hash(payload)
    _write(sending, payload)
    return payload


def fail_local_notification(root: str | Path, notification_id: str, error: str, *, max_attempts: int = 3) -> dict[str, Any]:
    """Record a local simulated failure, retrying or dead-lettering without sending."""
    root = Path(root)
    matches = [path for path in (root / "sending").glob("*.json") if _read(path).get("notification_id") == notification_id]
    if len(matches) != 1:
        raise LocalOutboxError("notification_not_claimed")
    sending = matches[0]
    payload = _read(sending)
    payload["updated_at_utc"] = _now()
    payload["last_error"] = str(error)
    payload["status"] = "dead" if payload["attempt_count"] >= max_attempts else "pending"
    payload["claim_token"] = None
    payload["claimed_at_utc"] = None
    payload = _with_hash(payload)
    target = root / payload["status"] / sending.name
    _write(target, payload)
    sending.unlink()
    return payload


def process_one_local_notification(root: str | Path) -> dict[str, Any] | None:
    """Mark one queued message sent as a dry-run; it never sends a message."""
    root = Path(root)
    payload = claim_one_local_notification(root)
    if payload is None:
        return None
    sending = next(path for path in (root / "sending").glob("*.json") if _read(path).get("notification_id") == payload["notification_id"])
    payload["status"] = "sent"
    payload["updated_at_utc"] = _now()
    payload["delivered_at_utc"] = payload["updated_at_utc"]
    payload["delivery_mode"] = "DRY_RUN_NO_NETWORK"
    payload["last_error"] = None
    payload["claim_token"] = None
    payload["claimed_at_utc"] = None
    payload = _with_hash(payload)
    target = root / "sent" / sending.name
    _write(target, payload)
    sending.unlink()
    return payload


def local_outbox_status(root: str | Path) -> dict[str, int]:
    root = Path(root)
    recover_local_outbox(root)
    return {state: len(list((root / state).glob("*.json"))) for state in STATES}
