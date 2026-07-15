"""Funding unit normalization.

This is the only place in AlphaHive V3 where raw funding values may be
converted from source units into decimal 8h rates.
"""
from __future__ import annotations

from pathlib import Path
from typing import Any

import pandas as pd
import yaml


PROJECT_ROOT = Path(__file__).resolve().parents[2]
CONTRACT_PATH = PROJECT_ROOT / "config" / "data_contracts.yaml"


def _contract() -> dict[str, Any]:
    with CONTRACT_PATH.open("r", encoding="utf-8") as f:
        data = yaml.safe_load(f)
    return data["funding"]


def raw_funding_hard_bounds() -> tuple[float, float]:
    """Return the single source-of-truth raw funding hard bounds."""
    rules = _contract()["raw_assertion"]
    return float(rules["median_abs_min"]), float(rules["abs_max"])


def normalized_funding_abs_max() -> float:
    """Derive the normalized upper bound; do not duplicate it in config."""
    funding = _contract()
    factor = float(funding["normalized_assertion"]["conversion_factor"])
    return raw_funding_hard_bounds()[1] * factor


def funding_sampling_policy() -> dict[str, Any]:
    """Return the single contract-declared funding sampling policy."""
    policy = _contract().get("sampling", {})
    if policy.get("deduplication") != "last_observation_per_utc_settlement_window":
        raise ValueError("Unsupported funding deduplication policy")
    period_hours = int(policy.get("settlement_period_hours", 0))
    if period_hours <= 0:
        raise ValueError("funding settlement_period_hours must be positive")
    if policy.get("timestamp_anchor") != "unix_epoch_utc":
        raise ValueError("Unsupported funding timestamp anchor")
    return policy


def deduplicate_funding_8h(frame: pd.DataFrame, timestamp_col: str = "timestamp") -> pd.DataFrame:
    """Keep the final source observation in each contract-defined UTC 8h window."""
    if timestamp_col not in frame.columns:
        raise ValueError(f"Funding frame missing timestamp column: {timestamp_col}")
    policy = funding_sampling_policy()
    timestamps = pd.to_numeric(frame[timestamp_col], errors="coerce")
    if timestamps.isna().any():
        raise ValueError("Funding frame contains invalid timestamps")
    period_ms = int(policy["settlement_period_hours"]) * 60 * 60 * 1000
    source = frame.copy()
    source["_funding_timestamp_ms"] = timestamps.astype("int64")
    source["_funding_settlement_window"] = source["_funding_timestamp_ms"] // period_ms
    source = source.sort_values(["_funding_settlement_window", "_funding_timestamp_ms"])
    source = source.groupby("_funding_settlement_window", sort=False, as_index=False).tail(1)
    return source.sort_values("_funding_timestamp_ms").drop(
        columns=["_funding_timestamp_ms", "_funding_settlement_window"]
    ).reset_index(drop=True)


def _numeric(series: pd.Series) -> pd.Series:
    return pd.to_numeric(series, errors="coerce").dropna()


def assert_raw_funding(series: pd.Series) -> None:
    values = _numeric(series)
    values = values[values != 0]
    if values.empty:
        raise AssertionError("RAW funding has no non-null, non-zero samples")
    rules = _contract()["raw_assertion"]
    med = float(values.abs().median())
    max_abs = float(values.abs().max())
    if med < float(rules["median_abs_min"]):
        raise AssertionError(
            f"RAW funding median_abs={med:.3e} below "
            f"{rules['median_abs_min']}; source unit may be wrong"
        )
    if max_abs > float(rules["abs_max"]):
        raise AssertionError(
            f"RAW funding abs_max={max_abs:.3e} above {rules['abs_max']}"
        )


def assert_normalized_funding(series: pd.Series) -> None:
    values = _numeric(series)
    values = values[values != 0]
    if values.empty:
        raise AssertionError("NORMALIZED funding has no non-null, non-zero samples")
    max_abs = float(values.abs().max())
    normalized_max = normalized_funding_abs_max()
    if max_abs > normalized_max:
        raise AssertionError(
            f"NORMALIZED funding abs_max={max_abs:.3e} above derived {normalized_max}"
        )


def normalize_funding(series: pd.Series) -> pd.Series:
    values = pd.to_numeric(series, errors="coerce")
    assert_raw_funding(values)
    op = str(_contract()["normalize_op"]).lower()
    if "raw_close / 100" in op or "raw / 100" in op or "/ 100" in op:
        out = values / 100.0
    elif "identity" in op or "no-op" in op:
        out = values
    else:
        raise ValueError(f"Unsupported funding normalize_op: {op}")
    assert_normalized_funding(out)
    return out


def normalize_funding_value(value: object) -> float:
    if pd.isna(value):
        return float("nan")
    return float(normalize_funding(pd.Series([value])).iloc[0])




