"""Versioned local publication for Owner-approved canonical price snapshots."""
from __future__ import annotations

from contextlib import contextmanager
from dataclasses import dataclass
from datetime import datetime, timezone
import hashlib
import json
import os
from pathlib import Path
import uuid
from typing import Any, Iterator

import pandas as pd


PROJECT_ROOT = Path(__file__).resolve().parents[2]
DEFAULT_ROOT = PROJECT_ROOT / "harness" / "canonical_price_snapshots"
HOUR_MS = 60 * 60 * 1000


class CanonicalPriceSnapshotError(ValueError):
    """Raised for a rejected publication or tampered published snapshot."""


@dataclass(frozen=True)
class GapPolicy:
    fresh_guard_hours: int = 48
    max_gap_bars_outside_guard: int = 4
    max_missing_bars_90d: int = 6
    lookback_days: int = 90


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _write_and_fsync(path: Path, content: str) -> None:
    with path.open("w", encoding="utf-8", newline="\n") as handle:
        handle.write(content)
        handle.flush()
        os.fsync(handle.fileno())


@contextmanager
def _publish_lock(root: Path) -> Iterator[None]:
    """Use the Windows file-lock primitive; tests run on the same platform."""
    import msvcrt

    root.mkdir(parents=True, exist_ok=True)
    path = root / ".publish.lock"
    with path.open("a+b") as handle:
        # ``a+b`` appends every write to EOF, so a written sentinel byte lands
        # at a new offset on each publish while the unlock offset stays fixed.
        # Lock the fixed first byte instead; ``msvcrt`` permits locking a byte
        # range beyond EOF, and the same seek makes lock and unlock symmetric.
        handle.seek(0)
        msvcrt.locking(handle.fileno(), msvcrt.LK_LOCK, 1)
        try:
            yield
        finally:
            handle.seek(0)
            msvcrt.locking(handle.fileno(), msvcrt.LK_UNLCK, 1)


def evaluate_gap_policy(manifest: dict[str, Any], policy: GapPolicy = GapPolicy()) -> dict[str, Any]:
    """Return an auditable decision; never fill or modify a missing bar."""
    latest = int(manifest["latest_timestamp_ms"])
    fresh_start = latest - policy.fresh_guard_hours * HOUR_MS
    lookback_start = latest - policy.lookback_days * 24 * HOUR_MS
    gaps = list(manifest.get("gap_intervals", []))
    fresh = [gap for gap in gaps if int(gap["before_timestamp_ms"]) >= fresh_start]
    recent = [gap for gap in gaps if int(gap["before_timestamp_ms"]) >= lookback_start]
    missing = sum(int(gap["missing_bars"]) for gap in recent)
    oversized = [gap for gap in recent if int(gap["missing_bars"]) > policy.max_gap_bars_outside_guard]
    if fresh:
        status, reason = "BLOCK", "FRESH_GAP"
    elif oversized:
        status, reason = "BLOCK", "GAP_EXCEEDS_MAXIMUM"
    elif missing > policy.max_missing_bars_90d:
        status, reason = "BLOCK", "MISSING_BARS_EXCEED_90D_MAXIMUM"
    elif recent:
        status, reason = "HISTORICAL_GAP_WARNING", "BOUNDED_HISTORICAL_GAP"
    else:
        status, reason = "PASS", "CONTIGUOUS"
    return {
        "status": status,
        "reason": reason,
        "fresh_gap_count": len(fresh),
        "recent_gap_count": len(recent),
        "missing_bars_90d": missing,
        "policy": {
            "fresh_guard_hours": policy.fresh_guard_hours,
            "max_gap_bars_outside_guard": policy.max_gap_bars_outside_guard,
            "max_missing_bars_90d": policy.max_missing_bars_90d,
            "lookback_days": policy.lookback_days,
        },
    }


def _next_version(root: Path) -> str:
    versions = [int(path.name[1:]) for path in root.glob("v[0-9][0-9][0-9][0-9]") if path.is_dir()]
    return f"v{(max(versions, default=0) + 1):04d}"


def publish_price_snapshot(
    snapshots: dict[str, tuple[pd.DataFrame, dict[str, Any]]],
    *,
    root: Path = DEFAULT_ROOT,
    published_at_utc: str | None = None,
) -> dict[str, Any]:
    """Publish accepted symbol snapshots and atomically repoint ``current.json``."""
    if not snapshots:
        raise CanonicalPriceSnapshotError("no_symbol_snapshots")
    if any(evaluate_gap_policy(manifest)["status"] == "BLOCK" for _, manifest in snapshots.values()):
        raise CanonicalPriceSnapshotError("blocked_symbol_snapshot")
    with _publish_lock(root):
        version = _next_version(root)
        staging = root / "_staging" / f"{version}_{uuid.uuid4().hex}"
        final = root / version
        kline_root = staging / "klines"
        kline_root.mkdir(parents=True, exist_ok=False)
        files: dict[str, dict[str, Any]] = {}
        symbols: dict[str, dict[str, Any]] = {}
        for symbol, (rows, manifest) in sorted(snapshots.items()):
            path = kline_root / f"{symbol}.parquet"
            rows.to_parquet(path, index=False)
            files[symbol] = {"relative_path": f"klines/{symbol}.parquet", "sha256": sha256_file(path), "rows": len(rows)}
            symbols[symbol] = {"bridge_manifest": manifest, "gap_policy": evaluate_gap_policy(manifest)}
        published = published_at_utc or datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
        manifest = {
            "schema_version": "canonical_price_snapshot_v1",
            "version": version,
            "published_at_utc": published,
            "price_precedence": "BINANCE_OVER_COINGLASS",
            "derivative_status": {"funding": "NOT_INCLUDED", "oi": "NOT_INCLUDED"},
            "symbols": symbols,
            "files": files,
        }
        manifest_text = json.dumps(manifest, ensure_ascii=False, sort_keys=True, indent=2)
        _write_and_fsync(staging / "manifest.json", manifest_text)
        os.replace(staging, final)
        pointer = {"schema_version": "canonical_price_pointer_v1", "version": version, "manifest_sha256": sha256_file(final / "manifest.json")}
        pointer_tmp = root / f".current.{uuid.uuid4().hex}.tmp"
        _write_and_fsync(pointer_tmp, json.dumps(pointer, sort_keys=True))
        os.replace(pointer_tmp, root / "current.json")
        return {**pointer, "root": str(root), "path": str(final)}


def load_current_price_snapshot(*, root: Path = DEFAULT_ROOT) -> tuple[pd.DataFrame, dict[str, Any]]:
    """Load and validate every file named by the immutable current pointer."""
    pointer_path = root / "current.json"
    if not pointer_path.exists():
        raise CanonicalPriceSnapshotError("current_pointer_missing")
    pointer = json.loads(pointer_path.read_text(encoding="utf-8"))
    version = str(pointer.get("version", ""))
    if not version.startswith("v") or "/" in version or "\\" in version:
        raise CanonicalPriceSnapshotError("invalid_pointer_version")
    base = root / version
    manifest_path = base / "manifest.json"
    if not manifest_path.exists() or sha256_file(manifest_path) != pointer.get("manifest_sha256"):
        raise CanonicalPriceSnapshotError("manifest_hash_mismatch")
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    if manifest.get("version") != version or manifest.get("schema_version") != "canonical_price_snapshot_v1":
        raise CanonicalPriceSnapshotError("manifest_schema_or_version_mismatch")
    frames = []
    for symbol, details in sorted(manifest.get("files", {}).items()):
        relative = Path(str(details.get("relative_path", "")))
        if relative.is_absolute() or ".." in relative.parts:
            raise CanonicalPriceSnapshotError("unsafe_snapshot_path")
        path = base / relative
        if not path.exists() or sha256_file(path) != details.get("sha256"):
            raise CanonicalPriceSnapshotError(f"kline_hash_mismatch:{symbol}")
        frame = pd.read_parquet(path)
        if len(frame) != int(details.get("rows", -1)):
            raise CanonicalPriceSnapshotError(f"kline_row_count_mismatch:{symbol}")
        frames.append(frame)
    if not frames:
        raise CanonicalPriceSnapshotError("published_snapshot_empty")
    return pd.concat(frames, ignore_index=True), manifest
