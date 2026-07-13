"""Cutoff helpers shared by snapshot producers.

The effective-cutoff semantics remain owned by deep_research_package.  This
module only adds the 1h completed-bar rule used when freezing raw klines.
"""
from __future__ import annotations

from typing import Optional

import pandas as pd

from harness.lib.deep_research_package import _resolve_effective_cutoff


KLINE_BAR_RESOLUTION = "1h"
KLINE_BAR_INTERVAL_MS = int(pd.Timedelta(KLINE_BAR_RESOLUTION).total_seconds() * 1000)


def resolve_completed_bar_cutoff(
    scan_time_utc: str,
    manifest_data_cutoff: Optional[int] = None,
) -> tuple[int, list[str]]:
    """Resolve the existing effective cutoff for a completed 1h-bar snapshot."""
    return _resolve_effective_cutoff(scan_time_utc, manifest_data_cutoff)


def filter_completed_bars(
    frame: pd.DataFrame,
    effective_cutoff_ms: int,
    timestamp_col: str = "timestamp",
    bar_interval_ms: int = KLINE_BAR_INTERVAL_MS,
) -> tuple[pd.DataFrame, dict[str, int]]:
    """Keep only bars whose close is at or before the effective cutoff.

    A kline with open time T is complete only when T + interval <= cutoff.
    Invalid timestamps are excluded and counted rather than silently treated
    as complete.
    """
    if frame.empty:
        return frame.copy(), {
            "rows_read": 0,
            "rows_kept": 0,
            "filtered_rows": 0,
            "filtered_incomplete_or_future_rows": 0,
            "filtered_invalid_timestamp_rows": 0,
            "completed_bar_violations": 0,
            "max_kept_bar_end_ms": None,
        }

    timestamps = pd.to_numeric(frame.get(timestamp_col), errors="coerce")
    valid_timestamp = timestamps.notna()
    completed = valid_timestamp & ((timestamps + int(bar_interval_ms)) <= int(effective_cutoff_ms))
    kept = frame.loc[completed].copy()
    invalid_count = int((~valid_timestamp).sum())
    incomplete_count = int((valid_timestamp & ~completed).sum())
    kept_timestamps = timestamps.loc[completed]
    max_kept_bar_end_ms = (
        int(kept_timestamps.max()) + int(bar_interval_ms)
        if not kept_timestamps.empty else None
    )
    return kept, {
        "rows_read": int(len(frame)),
        "rows_kept": int(len(kept)),
        "filtered_rows": int(len(frame) - len(kept)),
        "filtered_incomplete_or_future_rows": incomplete_count,
        "filtered_invalid_timestamp_rows": invalid_count,
        "completed_bar_violations": int(
            ((kept_timestamps + int(bar_interval_ms)) > int(effective_cutoff_ms)).sum()
        ),
        "max_kept_bar_end_ms": max_kept_bar_end_ms,
    }
