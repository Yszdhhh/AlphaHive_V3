"""Pure CoinGlass/Binance canonical field adapters.

The adapters deliberately do not choose a source, merge rows, overwrite raw
data, or switch the scanner. They only make the two existing schemas
comparable while preserving source and unit provenance.
"""
from __future__ import annotations

import math

import pandas as pd


class CanonicalSchemaError(ValueError):
    """Raised when a source frame cannot be mapped without guessing."""


def _source_name(source: str) -> str:
    value = str(source).strip().lower()
    if value not in {"coinglass", "binance"}:
        raise CanonicalSchemaError(f"Unsupported source: {source!r}")
    return value


def _require(frame: pd.DataFrame, columns: set[str], label: str) -> None:
    missing = sorted(columns.difference(frame.columns))
    if missing:
        raise CanonicalSchemaError(f"{label} missing required columns: {missing}")


def _symbol_series(frame: pd.DataFrame, symbol: str | None) -> pd.Series:
    candidates = [c for c in ("symbol", "_symbol") if c in frame.columns]
    if candidates:
        values = frame[candidates[0]].astype("string")
        non_null = values.dropna()
        if symbol is not None and not non_null.empty and set(non_null) != {str(symbol)}:
            raise CanonicalSchemaError(
                f"symbol argument {symbol!r} disagrees with source values {sorted(set(non_null))}"
            )
        return values.fillna(str(symbol) if symbol is not None else "")
    if symbol is None or not str(symbol).strip():
        raise CanonicalSchemaError("A symbol column or explicit symbol argument is required")
    return pd.Series([str(symbol)] * len(frame), index=frame.index, dtype="string")


def _timestamp(frame: pd.DataFrame, column: str, label: str) -> pd.Series:
    values = pd.to_numeric(frame[column], errors="coerce")
    finite = values.map(lambda value: math.isfinite(float(value)) if pd.notna(value) else False)
    if values.isna().any() or not finite.all() or (values < 100_000_000_000).any():
        raise CanonicalSchemaError(f"{label} timestamps must be unix milliseconds")
    return values.astype("int64")


def _numeric(frame: pd.DataFrame, columns: list[str], label: str) -> pd.DataFrame:
    out = frame[columns].copy()
    for column in columns:
        out[column] = pd.to_numeric(out[column], errors="coerce")
        finite = out[column].map(lambda value: math.isfinite(float(value)) if pd.notna(value) else False)
        if out[column].isna().any() or not finite.all():
            raise CanonicalSchemaError(f"{label} contains non-numeric values in {column}")
    return out


def _validate_ohlcv(out: pd.DataFrame, label: str) -> None:
    """Reject malformed complete OHLCV rows without selecting a data source.

    This is intentionally structural only.  It does not fill timestamp gaps,
    resolve source conflicts, or decide whether a source is current enough for
    the scanner; those actions remain outside the adapter boundary.
    """
    prices = out[["open", "high", "low", "close"]]
    if (prices < 0).any().any() or (out["volume"] < 0).any():
        raise CanonicalSchemaError(f"{label} contains negative OHLCV values")
    if (
        (out["high"] < out["low"]).any()
        or (out["high"] < out["open"]).any()
        or (out["high"] < out["close"]).any()
        or (out["low"] > out["open"]).any()
        or (out["low"] > out["close"]).any()
    ):
        raise CanonicalSchemaError(f"{label} has inconsistent OHLC bounds")
    if out.duplicated(["symbol", "timestamp_ms"]).any():
        raise CanonicalSchemaError(f"{label} contains duplicate symbol/timestamp rows")


def _base(frame: pd.DataFrame, source: str, timestamp: pd.Series, label: str, symbol: str | None) -> pd.DataFrame:
    source = _source_name(source)
    out = pd.DataFrame({
        "symbol": _symbol_series(frame, symbol).astype("string"),
        "timestamp_ms": timestamp.astype("int64"),
        "source": source,
        "source_schema": label,
    }, index=frame.index)
    return out.reset_index(drop=True)


def canonicalize_klines(frame: pd.DataFrame, source: str, symbol: str | None = None) -> pd.DataFrame:
    """Map CoinGlass or Binance 1h klines to common names."""
    source = _source_name(source)
    if source == "coinglass":
        _require(frame, {"open_time", "open", "high", "low", "close", "volume"}, "CoinGlass klines")
        timestamp = _timestamp(frame, "open_time", "CoinGlass klines")
        names = {
            "volume": "volume",
            "quote_volume": "quote_volume",
            "taker_buy_volume": "taker_buy_volume",
            "taker_buy_vol": "taker_buy_volume",
            "taker_buy_quote_volume": "taker_buy_quote_volume",
            "taker_buy_quote_vol": "taker_buy_quote_volume",
        }
        schema = "coinglass_klines"
    else:
        _require(frame, {"open_time", "open", "high", "low", "close", "volume"}, "Binance klines")
        timestamp = _timestamp(frame, "open_time", "Binance klines")
        names = {
            "volume": "volume",
            "quote_volume": "quote_volume",
            "taker_buy_vol": "taker_buy_volume",
            "taker_buy_quote_vol": "taker_buy_quote_volume",
            "turnover_usd": "turnover_usd",
        }
        schema = "binance_klines"

    out = _base(frame, source, timestamp, schema, symbol)
    prices = _numeric(frame, ["open", "high", "low", "close"], f"{source} klines")
    for column in prices.columns:
        out[column] = prices[column].to_numpy()
    for input_name, output_name in names.items():
        if input_name in frame.columns:
            out[output_name] = pd.to_numeric(frame[input_name], errors="coerce").to_numpy()
    if "turnover_usd" not in out and "quote_volume" in out:
        out["turnover_usd"] = out["quote_volume"]
    _validate_ohlcv(out, f"{source} klines")
    return out


def canonicalize_funding(frame: pd.DataFrame, source: str, symbol: str | None = None) -> pd.DataFrame:
    """Map funding into decimal and contract-compatible percent views.

    Binance's native decimal value is preserved as the canonical decimal
    value. CoinGlass's raw ``close`` is interpreted as percent only because
    that is the existing contract declaration; no heuristic unit guessing is
    performed.
    """
    source = _source_name(source)
    if source == "coinglass":
        _require(frame, {"time", "close"}, "CoinGlass funding")
        timestamp = _timestamp(frame, "time", "CoinGlass funding")
        raw_percent = pd.to_numeric(frame["close"], errors="coerce")
        if raw_percent.isna().any():
            raise CanonicalSchemaError("CoinGlass funding close contains non-numeric values")
        decimal = raw_percent / 100.0
        schema = "coinglass_funding_ohlc"
        source_unit = "percent"
        mark_price = pd.Series([float("nan")] * len(frame), index=frame.index)
    else:
        _require(frame, {"fundingTime"}, "Binance funding")
        timestamp = _timestamp(frame, "fundingTime", "Binance funding")
        decimal = pd.to_numeric(frame.get("fundingRate_decimal"), errors="coerce") if "fundingRate_decimal" in frame else pd.Series(float("nan"), index=frame.index)
        raw = pd.to_numeric(frame.get("fundingRate_raw"), errors="coerce") if "fundingRate_raw" in frame else pd.Series(float("nan"), index=frame.index)
        if decimal.isna().all() and raw.isna().all():
            raise CanonicalSchemaError("Binance funding needs fundingRate_decimal or fundingRate_raw")
        if decimal.notna().any() and raw.notna().any():
            comparable = decimal.notna() & raw.notna()
            same_as_decimal = (raw[comparable] - decimal[comparable]).abs() <= 1e-12
            same_as_percent = (raw[comparable] - decimal[comparable] * 100.0).abs() <= 1e-12
            if same_as_decimal.all():
                # Some Binance pull artifacts retain the raw column name while
                # storing the same decimal value in both columns. Do not
                # mistake the name for a completed percent conversion.
                source_unit = "decimal_alias_columns"
                decimal = decimal.where(decimal.notna(), raw)
                raw_percent = decimal * 100.0
            elif same_as_percent.all():
                source_unit = "decimal_with_percent_raw"
                decimal = decimal.where(decimal.notna(), raw / 100.0)
                raw_percent = raw
            else:
                raise CanonicalSchemaError("Binance funding raw/decimal columns disagree or mix units")
        elif decimal.notna().any():
            source_unit = "decimal"
            raw_percent = decimal * 100.0
        else:
            source_unit = "percent_raw_only"
            decimal = raw / 100.0
            raw_percent = raw
        schema = "binance_funding"
        mark_price = pd.to_numeric(frame.get("markPrice"), errors="coerce") if "markPrice" in frame else pd.Series(float("nan"), index=frame.index)

    out = _base(frame, source, timestamp, schema, symbol)
    out["funding_rate_decimal"] = decimal.to_numpy()
    out["funding_rate_raw_percent"] = raw_percent.to_numpy()
    out["source_unit"] = source_unit
    out["mark_price"] = mark_price.to_numpy()
    return out


def canonicalize_oi(frame: pd.DataFrame, source: str, symbol: str | None = None) -> pd.DataFrame:
    """Map OI while explicitly refusing to infer an absolute unit."""
    source = _source_name(source)
    if source == "coinglass":
        _require(frame, {"time", "close"}, "CoinGlass OI")
        timestamp = _timestamp(frame, "time", "CoinGlass OI")
        oi = pd.to_numeric(frame["close"], errors="coerce")
        value = pd.Series(float("nan"), index=frame.index)
        schema = "coinglass_oi_ohlc"
    else:
        _require(frame, {"timestamp", "sumOpenInterest"}, "Binance OI")
        timestamp = _timestamp(frame, "timestamp", "Binance OI")
        oi = pd.to_numeric(frame["sumOpenInterest"], errors="coerce")
        value = pd.to_numeric(frame.get("sumOpenInterestValue"), errors="coerce") if "sumOpenInterestValue" in frame else pd.Series(float("nan"), index=frame.index)
        schema = "binance_oi"
    if oi.isna().any():
        raise CanonicalSchemaError(f"{source} OI contains non-numeric open interest")
    out = _base(frame, source, timestamp, schema, symbol)
    out["open_interest"] = oi.to_numpy()
    out["open_interest_value"] = value.to_numpy()
    out["absolute_unit_status"] = "UNDECLARED"
    return out


def canonicalize_taker(frame: pd.DataFrame, source: str, symbol: str | None = None) -> pd.DataFrame:
    """Map taker buy/sell volumes and preserve ratio provenance."""
    source = _source_name(source)
    if source == "coinglass":
        _require(frame, {"time", "taker_buy_volume_usd", "taker_sell_volume_usd"}, "CoinGlass taker")
        timestamp = _timestamp(frame, "time", "CoinGlass taker")
        buy = pd.to_numeric(frame["taker_buy_volume_usd"], errors="coerce")
        sell = pd.to_numeric(frame["taker_sell_volume_usd"], errors="coerce")
        ratio = buy / sell.where(sell != 0)
        ratio_source = "derived_from_buy_sell"
        schema = "coinglass_taker_buysell"
    else:
        _require(frame, {"timestamp", "buyVol", "sellVol"}, "Binance taker")
        timestamp = _timestamp(frame, "timestamp", "Binance taker")
        buy = pd.to_numeric(frame["buyVol"], errors="coerce")
        sell = pd.to_numeric(frame["sellVol"], errors="coerce")
        ratio = pd.to_numeric(frame.get("buySellRatio"), errors="coerce") if "buySellRatio" in frame else buy / sell.where(sell != 0)
        ratio_source = "source" if "buySellRatio" in frame else "derived_from_buy_sell"
        schema = "binance_taker_buysell"
    if buy.isna().any() or sell.isna().any():
        raise CanonicalSchemaError(f"{source} taker data contains non-numeric buy/sell values")
    out = _base(frame, source, timestamp, schema, symbol)
    out["taker_buy_volume"] = buy.to_numpy()
    out["taker_sell_volume"] = sell.to_numpy()
    out["taker_buy_sell_ratio"] = ratio.to_numpy()
    out["ratio_source"] = ratio_source
    return out
