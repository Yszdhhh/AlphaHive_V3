"""Pure mappings from Binance-free extracts to AlphaHive contract fields.

This module does not read databases or select scanner sources. It only makes
the existing contract-compatible conversions available for a later, approved
integration.
"""
from __future__ import annotations

import pandas as pd

from harness.lib.funding_normalize import raw_funding_from_normalized


def binance_funding_decimal_to_contract_raw(series: pd.Series) -> pd.Series:
    """Map Binance decimal funding into the contract-defined raw percent unit."""
    return raw_funding_from_normalized(series)


def map_binance_open_interest(frame: pd.DataFrame) -> pd.DataFrame:
    """Map timestamp and absolute OI without inferring its undeclared unit."""
    timestamp_col = "timestamp" if "timestamp" in frame.columns else "time"
    required = {timestamp_col, "sumOpenInterest"}
    missing = required.difference(frame.columns)
    if missing:
        raise ValueError(f"Binance OI mapping missing required columns: {sorted(missing)}")
    mapped = frame[[timestamp_col, "sumOpenInterest"]].copy()
    mapped = mapped.rename(columns={timestamp_col: "timestamp", "sumOpenInterest": "open_interest"})
    mapped["timestamp"] = pd.to_numeric(mapped["timestamp"], errors="coerce")
    mapped["open_interest"] = pd.to_numeric(mapped["open_interest"], errors="coerce")
    if mapped["timestamp"].isna().any() or mapped["open_interest"].isna().any():
        raise ValueError("Binance OI mapping contains invalid timestamp or open-interest values")
    return mapped
