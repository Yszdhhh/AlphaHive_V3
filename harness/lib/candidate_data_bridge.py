"""Non-active, deterministic price bridge for prospective-candidate inputs.

This module prepares a scanner-compatible OHLCV view from local Binance and
CoinGlass frames.  It does not read either database, write a snapshot, change
the configured scanner path, or choose a gap tolerance.  Those side effects
remain at separately approved activation boundaries.
"""
from __future__ import annotations

from dataclasses import dataclass
import hashlib
import json
from typing import Any

import pandas as pd

from .canonical_data import CanonicalSchemaError, canonicalize_klines


HOUR_MS = 60 * 60 * 1000
SCAN_COLUMNS = [
    "timestamp", "open", "high", "low", "close", "volume", "turnover_usd",
    "symbol", "price_source",
]


class CandidateBridgeError(ValueError):
    """Raised when source rows cannot produce an auditable price view."""


@dataclass(frozen=True)
class CandidateBridgeSnapshot:
    """A pure result; publication and source-path activation are intentionally absent."""

    rows: pd.DataFrame
    manifest: dict[str, Any]


def _canonical_json(value: Any) -> str:
    return json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":"), allow_nan=False)


def _content_hash(value: Any) -> str:
    return hashlib.sha256(_canonical_json(value).encode("utf-8")).hexdigest()


def _completed(frame: pd.DataFrame, effective_cutoff_ms: int | None) -> pd.DataFrame:
    if effective_cutoff_ms is None:
        return frame.copy()
    return frame.loc[frame["timestamp_ms"] + HOUR_MS <= int(effective_cutoff_ms)].copy()


def _overlap_conflicts(binance: pd.DataFrame, coinglass: pd.DataFrame) -> int:
    fields = ["open", "high", "low", "close", "volume", "turnover_usd"]
    left = binance[["symbol", "timestamp_ms", *fields]]
    right = coinglass[["symbol", "timestamp_ms", *fields]]
    overlap = left.merge(right, on=["symbol", "timestamp_ms"], suffixes=("_binance", "_coinglass"))
    if overlap.empty:
        return 0
    compared = [
        overlap[f"{field}_binance"].round(12).ne(overlap[f"{field}_coinglass"].round(12))
        for field in fields
    ]
    return int(pd.concat(compared, axis=1).any(axis=1).sum())


def _gap_intervals(rows: pd.DataFrame) -> list[dict[str, int]]:
    values = rows["timestamp"].sort_values().drop_duplicates().tolist()
    gaps: list[dict[str, int]] = []
    for previous, current in zip(values, values[1:]):
        delta = int(current) - int(previous)
        if delta > HOUR_MS:
            gaps.append({
                "after_timestamp_ms": int(previous),
                "before_timestamp_ms": int(current),
                "missing_bars": delta // HOUR_MS - 1,
            })
    return gaps


def build_price_snapshot(
    *,
    symbol: str,
    binance_klines: pd.DataFrame | None,
    coinglass_klines: pd.DataFrame | None,
    effective_cutoff_ms: int | None = None,
) -> CandidateBridgeSnapshot:
    """Prepare a Binance-preferred, source-provenance OHLCV view.

    CoinGlass contributes historical-only rows.  On an overlapping timestamp,
    Binance wins exactly as recorded in the Owner approval; a differing bar is
    counted in the manifest rather than silently ignored.  Gap handling is
    descriptive only so that publication policy remains an explicit decision.
    """
    if not str(symbol).strip():
        raise CandidateBridgeError("symbol_required")
    source_frames: list[pd.DataFrame] = []
    try:
        if binance_klines is not None and not binance_klines.empty:
            source_frames.append(_completed(canonicalize_klines(binance_klines, "binance", symbol=symbol), effective_cutoff_ms))
        if coinglass_klines is not None and not coinglass_klines.empty:
            source_frames.append(_completed(canonicalize_klines(coinglass_klines, "coinglass", symbol=symbol), effective_cutoff_ms))
    except CanonicalSchemaError as exc:
        raise CandidateBridgeError(str(exc)) from exc
    source_frames = [frame for frame in source_frames if not frame.empty]
    if not source_frames:
        raise CandidateBridgeError("no_completed_price_rows")

    by_source = {frame.loc[0, "source"]: frame for frame in source_frames}
    binance = by_source.get("binance", pd.DataFrame(columns=SCAN_COLUMNS))
    coinglass = by_source.get("coinglass", pd.DataFrame(columns=SCAN_COLUMNS))
    conflict_count = _overlap_conflicts(binance, coinglass) if not binance.empty and not coinglass.empty else 0

    combined = pd.concat(source_frames, ignore_index=True)
    combined["_priority"] = combined["source"].map({"binance": 0, "coinglass": 1})
    combined = combined.sort_values(["symbol", "timestamp_ms", "_priority"])
    chosen = combined.drop_duplicates(["symbol", "timestamp_ms"], keep="first").copy()
    chosen = chosen.rename(columns={"timestamp_ms": "timestamp", "source": "price_source"})
    for optional in ("turnover_usd",):
        if optional not in chosen:
            chosen[optional] = pd.NA
    rows = chosen[SCAN_COLUMNS].sort_values("timestamp").reset_index(drop=True)
    gaps = _gap_intervals(rows)
    row_records = rows.to_dict(orient="records")
    manifest = {
        "schema_version": "candidate_price_bridge_v1",
        "symbol": str(symbol),
        "effective_cutoff_ms": int(effective_cutoff_ms) if effective_cutoff_ms is not None else None,
        "price_precedence": "BINANCE_OVER_COINGLASS",
        "row_count": len(row_records),
        "earliest_timestamp_ms": int(rows["timestamp"].min()),
        "latest_timestamp_ms": int(rows["timestamp"].max()),
        "overlap_conflict_count": conflict_count,
        "gap_intervals": gaps,
        "gap_status": "GAPS_PRESENT" if gaps else "CONTIGUOUS",
        "derivative_status": {"funding": "NOT_INCLUDED", "oi": "NOT_INCLUDED"},
        "publication_status": "PREPARATION_ONLY_NO_ACTIVE_SCANNER_SWITCH",
        "rows_hash": _content_hash(row_records),
    }
    return CandidateBridgeSnapshot(rows=rows, manifest=manifest)
