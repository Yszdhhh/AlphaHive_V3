"""Turnover calculations shared by scan, baseline, and friction scripts."""
from __future__ import annotations

from dataclasses import dataclass

import pandas as pd


@dataclass(frozen=True)
class TurnoverResult:
    turnover_24h_usd_effective: float | None
    n_valid_bars: int
    confidence: str


def bar_turnover_usd(df: pd.DataFrame) -> pd.Series:
    if "quote_volume" in df.columns:
        return pd.to_numeric(df["quote_volume"], errors="coerce")
    if "volume_usd" in df.columns:
        return pd.to_numeric(df["volume_usd"], errors="coerce")
    if "turnover_usd" in df.columns:
        return pd.to_numeric(df["turnover_usd"], errors="coerce")
    close = pd.to_numeric(df.get("close"), errors="coerce")
    volume = pd.to_numeric(df.get("volume"), errors="coerce")
    return close * volume


def turnover_24h_effective(
    symbol_df: pd.DataFrame,
    min_valid_bars: int = 18,
) -> TurnoverResult:
    if symbol_df.empty:
        return TurnoverResult(None, 0, "none")
    df = symbol_df.sort_values("timestamp").tail(24).copy()
    turnover = bar_turnover_usd(df)
    close = pd.to_numeric(df.get("close"), errors="coerce")
    volume = pd.to_numeric(df.get("volume"), errors="coerce")
    valid_mask = turnover.notna() & (turnover > 0) & close.notna()
    if "volume" in df.columns:
        valid_mask &= volume.notna() & (volume > 0)
    valid = turnover[valid_mask]
    n_valid = int(valid.count())
    if n_valid == 0:
        return TurnoverResult(None, 0, "none")
    if n_valid >= min_valid_bars:
        return TurnoverResult(float(valid.sum()), n_valid, "full")
    return TurnoverResult(float(valid.mean() * 24.0), n_valid, "low")


def turnover_map_from_snapshot(
    snapshot: pd.DataFrame,
    min_valid_bars: int = 18,
) -> dict[str, TurnoverResult]:
    return {
        str(symbol): turnover_24h_effective(group, min_valid_bars=min_valid_bars)
        for symbol, group in snapshot.groupby("symbol")
    }
