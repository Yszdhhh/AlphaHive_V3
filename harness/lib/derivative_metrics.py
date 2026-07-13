"""Honest, self-timeseries derivative metric summaries for the scanner."""
from __future__ import annotations

from typing import Tuple

import pandas as pd

from harness.lib.cutoff import KLINE_BAR_INTERVAL_MS


def empty_metric_summary(metric: str, reason: str) -> dict:
    return {
        "metric": metric,
        "status": "NOT_COMPUTED",
        "n_valid": 0,
        "window_start": None,
        "window_end": None,
        "coverage": 0.0,
        "quantile": None,
        "latest_value": None,
        "latest_timestamp": None,
        "reason": reason,
    }


def compute_metric_summary(
    frame: pd.DataFrame,
    metric: str,
    timestamp_col: str,
    value_col: str,
    effective_cutoff_ms: int,
    lookback_hours: int,
    derive_24h_change: bool = False,
) -> Tuple[dict, pd.DataFrame]:
    """Compute one symbol's metric using only its own completed history.

    The returned status is deliberately capped at PARTIAL until the parked
    minimum-sample/coverage policy is approved.  The returned series is safe
    to merge back into the frozen kline snapshot; it never contains post-cutoff
    rows.
    """
    if frame.empty or timestamp_col not in frame.columns or value_col not in frame.columns:
        return empty_metric_summary(metric, "MISSING_SOURCE_OR_FIELD"), pd.DataFrame(columns=["timestamp", "metric_value"])

    timestamps = pd.to_numeric(frame[timestamp_col], errors="coerce")
    values = pd.to_numeric(frame[value_col], errors="coerce")
    if timestamps.isna().any():
        return empty_metric_summary(metric, "INVALID_TIMESTAMP"), pd.DataFrame(columns=["timestamp", "metric_value"])
    if not timestamps.is_monotonic_increasing or timestamps.duplicated().any():
        return empty_metric_summary(metric, "TIMESTAMP_NOT_MONOTONIC_OR_DUPLICATED"), pd.DataFrame(columns=["timestamp", "metric_value"])

    complete_mask = (timestamps + KLINE_BAR_INTERVAL_MS) <= int(effective_cutoff_ms)
    window_start_ms = int(effective_cutoff_ms) - int(lookback_hours) * 60 * 60 * 1000
    window_mask = complete_mask & (timestamps >= window_start_ms)
    source = pd.DataFrame({"timestamp": timestamps, "source_value": values})
    source = source.loc[window_mask].copy()
    source = source.dropna(subset=["source_value"])
    expected_points = max(int(lookback_hours), 1)
    n_source = int(len(source))
    if n_source == 0:
        return empty_metric_summary(metric, "NO_VALID_WINDOW_SAMPLES"), pd.DataFrame(columns=["timestamp", "metric_value"])

    if derive_24h_change:
        source_by_timestamp = source.set_index("timestamp")["source_value"]
        prior = source_by_timestamp.reindex(source["timestamp"] - 24 * 60 * 60 * 1000).to_numpy()
        current = source["source_value"].to_numpy()
        source["metric_value"] = (current / prior - 1.0) * 100.0
        source.loc[(prior == 0) | pd.isna(prior), "metric_value"] = pd.NA
        reason_prefix = "NO_VALID_24H_CHANGE"
    else:
        source["metric_value"] = source["source_value"]
        reason_prefix = "NO_VALID_METRIC_SAMPLES"

    metric_series = source[["timestamp", "metric_value"]].dropna().copy()
    metric_series["timestamp"] = metric_series["timestamp"].astype("int64")
    metric_values = pd.to_numeric(metric_series["metric_value"], errors="coerce").dropna()
    n_valid = int(len(metric_values))
    if n_valid == 0:
        return empty_metric_summary(metric, reason_prefix), pd.DataFrame(columns=["timestamp", "metric_value"])
    if metric_values.nunique(dropna=True) <= 1:
        return empty_metric_summary(metric, "DEGENERATE_CONSTANT_SERIES"), metric_series

    latest_timestamp = int(metric_series["timestamp"].iloc[-1])
    latest_value = float(metric_values.iloc[-1])
    self_quantile = float((metric_values <= latest_value).mean())
    summary = {
        "metric": metric,
        "status": "PARTIAL",
        "n_valid": n_valid,
        "window_start": pd.to_datetime(int(metric_series["timestamp"].min()), unit="ms", utc=True).isoformat(),
        "window_end": pd.to_datetime(int(metric_series["timestamp"].max()), unit="ms", utc=True).isoformat(),
        "coverage": min(float(n_valid) / float(expected_points), 1.0),
        "quantile": self_quantile,
        "latest_value": latest_value,
        "latest_timestamp": latest_timestamp,
        "reason": "MIN_SAMPLE_COVERAGE_POLICY_PARKED",
    }
    return summary, metric_series
