"""Read-only CoinGlass/Binance coverage and canonical-adapter report.

This script deliberately creates a report only. It does not merge, overwrite,
or change the source parquet stores and it does not switch scanner inputs.
"""
from __future__ import annotations

import argparse
import json
import sys
from datetime import datetime, timezone
from pathlib import Path

import pandas as pd

PROJECT_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(PROJECT_ROOT))

from harness.lib.canonical_data import (
    CanonicalSchemaError,
    canonicalize_funding,
    canonicalize_klines,
    canonicalize_oi,
    canonicalize_taker,
)


DEFAULT_COINGLASS = Path(r"C:\Users\10639\Desktop\加密\coinglass_db")
DEFAULT_BINANCE = Path(r"C:\Users\10639\Desktop\加密\binance_free_db")

DIMENSIONS = {
    "klines": ("raw_1h/klines", "open_time"),
    "funding": ("raw_1h/funding_ohlc", "time"),
    "oi": ("raw_1h/oi_ohlc", "time"),
    "taker": ("raw_1h/taker_buysell", "time"),
}
BINANCE_DIMENSIONS = {
    "klines": ("raw_1h/klines", "open_time"),
    "funding": ("raw_8h/funding", "fundingTime"),
    "oi": ("raw_1h/oi", "timestamp"),
    "taker": ("raw_1h/taker_buysell", "timestamp"),
}
ADAPTERS = {
    "klines": canonicalize_klines,
    "funding": canonicalize_funding,
    "oi": canonicalize_oi,
    "taker": canonicalize_taker,
}


def load_live_symbols(universe_path: Path) -> list[str]:
    data = json.loads(universe_path.read_text(encoding="utf-8"))
    disabled = set(data.get("disabled_pull_symbols", []))
    candidates = [
        row["symbol"] if isinstance(row, dict) else str(row)
        for row in data.get("symbols", [])
    ]
    benchmarks = [str(row) for row in data.get("benchmark_symbols", [])]
    return list(dict.fromkeys([s for s in candidates if s not in disabled] + benchmarks))


def inspect_dimension(root: Path, source: str, dimension: str, symbols: list[str]) -> dict:
    mapping = DIMENSIONS if source == "coinglass" else BINANCE_DIMENSIONS
    relative, timestamp_column = mapping[dimension]
    directory = root / relative
    files = sorted(directory.glob("*.parquet")) if directory.exists() else []
    live_files = [directory / f"{symbol}.parquet" for symbol in symbols]
    present_live = [p for p in live_files if p.exists()]
    min_ms = None
    max_ms = None
    adapter_status = "NOT_RUN"
    adapter_error = ""
    sample_schema = ""
    for path in files:
        try:
            frame = pd.read_parquet(path)
            if not sample_schema:
                sample_schema = ", ".join(frame.columns)
            values = pd.to_numeric(frame[timestamp_column], errors="coerce").dropna()
            if not values.empty:
                current_min = int(values.min())
                current_max = int(values.max())
                min_ms = current_min if min_ms is None else min(min_ms, current_min)
                max_ms = current_max if max_ms is None else max(max_ms, current_max)
            if adapter_status == "NOT_RUN":
                ADAPTERS[dimension](frame.head(2), source, symbol=path.stem)
                adapter_status = "PASS"
        except (KeyError, ValueError, CanonicalSchemaError) as exc:
            if adapter_status == "NOT_RUN":
                adapter_status = "FAIL"
                adapter_error = str(exc)
    to_date = lambda value: datetime.fromtimestamp(value / 1000, tz=timezone.utc).date().isoformat() if value is not None else "N/A"
    return {
        "files": len(files),
        "live_present": len(present_live),
        "live_total": len(symbols),
        "start": to_date(min_ms),
        "end": to_date(max_ms),
        "schema": sample_schema,
        "adapter": adapter_status,
        "adapter_error": adapter_error,
    }


def build_report(coinglass_root: Path, binance_root: Path, universe_path: Path) -> str:
    symbols = load_live_symbols(universe_path)
    cg = {dim: inspect_dimension(coinglass_root, "coinglass", dim, symbols) for dim in DIMENSIONS}
    bn = {dim: inspect_dimension(binance_root, "binance", dim, symbols) for dim in BINANCE_DIMENSIONS}
    generated = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
    lines = [
        "# CoinGlass/Binance canonical coverage report",
        "",
        f"Generated: {generated}",
        f"Live symbols evaluated: {len(symbols)}",
        f"CoinGlass root: `{coinglass_root}`",
        f"Binance root: `{binance_root}`",
        "",
        "## Coverage and adapter checks",
        "",
        "| Source | Dimension | Files | Live present | Date range UTC | Adapter | Sample schema |",
        "|---|---|---:|---:|---|---|---|",
    ]
    for source, result in (("CoinGlass", cg), ("Binance", bn)):
        for dimension, item in result.items():
            schema = item["schema"].replace("|", "\\|")
            lines.append(
                f"| {source} | {dimension} | {item['files']} | "
                f"{item['live_present']}/{item['live_total']} | {item['start']} → {item['end']} | "
                f"{item['adapter']} | {schema} |"
            )
    lines += [
        "",
        "## Integration boundary",
        "",
        "- This is a read-only comparison report; no parquet data was merged or overwritten.",
        "- The existing AlphaHive scanner still consumes the CoinGlass paths declared in `config/data_contracts.yaml` and `config/universe.json`.",
        "- Binance remains a separate live store. The canonical adapters preserve `source`, `source_schema`, and source-unit provenance.",
        "- Funding is exposed as decimal plus contract-compatible raw-percent view; OI absolute units remain `UNDECLARED` unless an authoritative contract declares them.",
        "- If Binance `fundingRate_raw` and `fundingRate_decimal` are equal, the adapter labels them `decimal_alias_columns`; the column name alone is not treated as proof of percent conversion.",
        "- Source precedence, historical cutoff, and any scanner source switch remain Owner decisions.",
        "",
        "## Status",
        "",
        "`GREEN_FOR_ADDITIVE_RECONCILIATION` — adapters can be tested without changing the production scanner.",
    ]
    return "\n".join(lines) + "\n"


def main() -> int:
    parser = argparse.ArgumentParser(description="Build a read-only dual-source coverage report")
    parser.add_argument("--coinglass-root", type=Path, default=DEFAULT_COINGLASS)
    parser.add_argument("--binance-root", type=Path, default=DEFAULT_BINANCE)
    parser.add_argument("--universe", type=Path, default=PROJECT_ROOT / "config" / "universe.json")
    parser.add_argument("--output", type=Path, default=PROJECT_ROOT / "reports" / "DATA_CANONICAL_COVERAGE_20260715.md")
    args = parser.parse_args()
    report = build_report(args.coinglass_root, args.binance_root, args.universe)
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(report, encoding="utf-8")
    print(f"Report written to: {args.output}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
