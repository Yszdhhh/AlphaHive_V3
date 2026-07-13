"""Run registry helpers."""
from __future__ import annotations

from pathlib import Path
from typing import Any

import yaml


PROJECT_ROOT = Path(__file__).resolve().parents[2]
REGISTRY_PATH = PROJECT_ROOT / "harness" / "run_registry.yaml"


def load_registry() -> dict[str, Any]:
    if not REGISTRY_PATH.exists():
        return {"schema_version": "v1", "runs": []}
    with REGISTRY_PATH.open("r", encoding="utf-8") as f:
        return yaml.safe_load(f) or {"schema_version": "v1", "runs": []}


def run_entry(run_id: str) -> dict[str, Any] | None:
    for entry in load_registry().get("runs", []):
        if entry.get("run_id") == run_id:
            return entry
    return None


def run_status(run_id: str) -> str:
    entry = run_entry(run_id)
    return str(entry.get("status")) if entry else "unregistered"


def clean_run_ids() -> list[str]:
    return [
        entry["run_id"]
        for entry in load_registry().get("runs", [])
        if entry.get("status") == "clean" and entry.get("eligible_for_dod") is True
    ]
