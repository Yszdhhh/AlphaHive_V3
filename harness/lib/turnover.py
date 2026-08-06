"""Turnover calculations shared by scan, baseline, and friction scripts."""
from __future__ import annotations

from dataclasses import dataclass

import pandas as pd


@dataclass(frozen=True)
class TurnoverResult:
    turnover_24h_usd_effective: float | None
    n_valid_bars: int
    threshold_pass: bool | None
    valid_bar_pass: bool
    confidence: str
    reason: str


def bar_turnover_usd(df: pd.DataFrame) -> pd.Series:
    result = pd.Series(float("nan"), index=df.index, dtype="float64")
    for column in ("quote_volume", "volume_usd", "turnover_usd"):
        if column not in df.columns:
            continue
        candidate = pd.to_numeric(df[column], errors="coerce")
        result = result.where(result.notna() & (result > 0), candidate)
    close = pd.to_numeric(df.get("close"), errors="coerce")
    volume = pd.to_numeric(df.get("volume"), errors="coerce")
    fallback = close * volume
    return result.where(result.notna() & (result > 0), fallback)


def turnover_24h_effective(
    symbol_df: pd.DataFrame,
    min_valid_bars: int = 18,
    min_effective_turnover_usd: float | None = None,
) -> TurnoverResult:
    if symbol_df.empty:
        return TurnoverResult(None, 0, False if min_effective_turnover_usd is not None else None, False, "none", "NO_DATA")
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
        return TurnoverResult(None, 0, False if min_effective_turnover_usd is not None else None, False, "none", "NO_VALID_BARS")

    valid_bar_pass = n_valid >= min_valid_bars
    if valid_bar_pass:
        effective_turnover = float(valid.sum())
        confidence = "full"
    else:
        effective_turnover = float(valid.mean() * 24.0)
        confidence = "partial"

    threshold_pass = (
        None
        if min_effective_turnover_usd is None
        else effective_turnover >= float(min_effective_turnover_usd)
    )
    reasons = []
    if not valid_bar_pass:
        reasons.append("VALID_BARS_BELOW_MINIMUM")
    if threshold_pass is False:
        reasons.append("TURNOVER_BELOW_MINIMUM")
    reason = "PASS" if not reasons else ";".join(reasons)
    return TurnoverResult(
        effective_turnover,
        n_valid,
        threshold_pass,
        valid_bar_pass,
        confidence,
        reason,
    )


def turnover_map_from_snapshot(
    snapshot: pd.DataFrame,
    min_valid_bars: int = 18,
    min_effective_turnover_usd: float | None = None,
) -> dict[str, TurnoverResult]:
    return {
        str(symbol): turnover_24h_effective(
            group,
            min_valid_bars=min_valid_bars,
            min_effective_turnover_usd=min_effective_turnover_usd,
        )
        for symbol, group in snapshot.groupby("symbol")
    }
