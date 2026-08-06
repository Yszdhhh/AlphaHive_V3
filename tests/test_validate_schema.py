"""Regression coverage for the standalone schema validator."""
from __future__ import annotations

import importlib.util
from pathlib import Path

import pandas as pd


PROJECT_ROOT = Path(__file__).resolve().parents[1]
VALIDATOR_PATH = PROJECT_ROOT / "scripts" / "99_validate_schema.py"


def _load_validator():
    spec = importlib.util.spec_from_file_location("validate_schema", VALIDATOR_PATH)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def test_empty_funding_samples_fail_g4_contract() -> None:
    validator = _load_validator()
    results: list[dict] = []

    validator.check_funding_contract(
        "unused-run-id",
        pd.DataFrame({"funding_rate_8h": [None, float("nan")]}),
        results,
    )

    assert results == [{
        "gate": "G4 funding contract",
        "status": "FAIL",
        "detail": "no funding samples in anomaly rows",
    }]


def test_live_disabled_dormant_funding_passes_g4_contract() -> None:
    validator = _load_validator()
    results: list[dict] = []

    validator.check_funding_contract(
        "unused-run-id",
        pd.DataFrame({"funding_rate_8h": [None, float("nan")]}),
        results,
        derivative_use_mode="LIVE_DISABLED",
    )

    assert results == [{
        "gate": "G4 funding contract",
        "status": "PASS",
        "detail": "funding dormant by design: derivative_use_mode=LIVE_DISABLED",
    }]


def test_live_disabled_with_funding_values_fails_g4_contract() -> None:
    validator = _load_validator()
    results: list[dict] = []

    validator.check_funding_contract(
        "unused-run-id",
        pd.DataFrame({"funding_rate_8h": [0.0001, None]}),
        results,
        derivative_use_mode="LIVE_DISABLED",
    )

    assert results == [{
        "gate": "G4 funding contract",
        "status": "FAIL",
        "detail": "1 funding samples present despite LIVE_DISABLED",
    }]
