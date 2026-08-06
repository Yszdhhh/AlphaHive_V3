"""Read-only CoinGlass/Binance funding overlap reconciliation.

The report is an alignment study only. It never writes to either raw store,
changes the data contract, or authorizes a historical gap fill.
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

from harness.lib.canonical_data import canonicalize_funding  # noqa: E402

DEFAULT_COINGLASS = Path(r"C:\Users\10639\Desktop\加密\coinglass_db")
DEFAULT_BINANCE = Path(r"C:\Users\10639\Desktop\加密\binance_free_db")
SETTLEMENT_MS = 8 * 60 * 60 * 1000
CG_TO_SETTLEMENT_MS = 60 * 60 * 1000
ALIGNMENT_BUCKET_MS = 60 * 60 * 1000


def load_effective_symbols(universe_path: Path) -> list[str]:
    data = json.loads(universe_path.read_text(encoding="utf-8"))
    disabled = set(data.get("disabled_pull_symbols", []))
    symbols = [row["symbol"] if isinstance(row, dict) else str(row) for row in data.get("symbols", [])]
    benchmarks = [str(row) for row in data.get("benchmark_symbols", [])]
    return list(dict.fromkeys([s for s in symbols if s not in disabled] + benchmarks))


def _date(value: int | None) -> str:
    if value is None:
        return "N/A"
    return datetime.fromtimestamp(value / 1000, tz=timezone.utc).date().isoformat()


def reconcile_symbol(coinglass_root: Path, binance_root: Path, symbol: str) -> dict:
    cg_path = coinglass_root / "raw_1h" / "funding_ohlc" / f"{symbol}.parquet"
    bn_path = binance_root / "raw_8h" / "funding" / f"{symbol}.parquet"
    result = {"symbol": symbol, "cg_present": cg_path.exists(), "bn_present": bn_path.exists()}
    if not cg_path.exists() or not bn_path.exists():
        result.update({"cg_rows": 0, "bn_rows": 0, "matches": 0, "median_abs_diff": None, "max_abs_diff": None})
        return result

    cg = canonicalize_funding(pd.read_parquet(cg_path), "coinglass", symbol=symbol)
    bn = canonicalize_funding(pd.read_parquet(bn_path), "binance", symbol=symbol)
    bn_raw_rows = len(bn)
    cg = cg[["timestamp_ms", "funding_rate_decimal"]].rename(
        columns={"timestamp_ms": "aligned_timestamp_ms", "funding_rate_decimal": "cg_decimal"}
    )
    cg["aligned_timestamp_ms"] += CG_TO_SETTLEMENT_MS
    bn["raw_timestamp_ms"] = bn["timestamp_ms"]
    bn["aligned_timestamp_ms"] = (
        (bn["timestamp_ms"] + ALIGNMENT_BUCKET_MS // 2) // ALIGNMENT_BUCKET_MS
    ) * ALIGNMENT_BUCKET_MS
    bn = bn[["aligned_timestamp_ms", "raw_timestamp_ms", "funding_rate_decimal"]].rename(
        columns={"funding_rate_decimal": "bn_decimal"}
    )
    # A few Binance pulls contain more than one record inside the same UTC
    # settlement boundary. Keep the latest raw observation and record the
    # raw count separately; this is a reconciliation rule, not a source edit.
    bn = bn.sort_values("raw_timestamp_ms").drop_duplicates("aligned_timestamp_ms", keep="last")
    merged = bn.merge(cg, on="aligned_timestamp_ms", how="inner", validate="one_to_one")
    diffs = (merged["bn_decimal"] - merged["cg_decimal"]).abs()
    result.update(
        {
            "cg_rows": len(cg),
            "bn_rows": bn_raw_rows,
            "bn_unique_settlements": len(bn),
            "cg_start": _date(int(cg["aligned_timestamp_ms"].min()) - CG_TO_SETTLEMENT_MS) if len(cg) else "N/A",
            "cg_end": _date(int(cg["aligned_timestamp_ms"].max()) - CG_TO_SETTLEMENT_MS) if len(cg) else "N/A",
            "bn_start": _date(int(bn["raw_timestamp_ms"].min())) if len(bn) else "N/A",
            "bn_end": _date(int(bn["raw_timestamp_ms"].max())) if len(bn) else "N/A",
            "matches": len(merged),
            "median_abs_diff": float(diffs.median()) if len(diffs) else None,
            "max_abs_diff": float(diffs.max()) if len(diffs) else None,
            "max_binance_jitter_ms": int((bn["raw_timestamp_ms"] - bn["aligned_timestamp_ms"]).abs().max()) if len(bn) else 0,
        }
    )
    return result


def build_report(coinglass_root: Path, binance_root: Path, universe_path: Path) -> str:
    symbols = load_effective_symbols(universe_path)
    rows = [reconcile_symbol(coinglass_root, binance_root, symbol) for symbol in symbols]
    both = [row for row in rows if row["cg_present"] and row["bn_present"]]
    matched = [row for row in both if row["matches"]]
    bn_rows = sum(row["bn_unique_settlements"] for row in both)
    match_rows = sum(row["matches"] for row in both)
    generated = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
    lines = [
        "# Funding overlap reconciliation (read-only)",
        "",
        f"Generated: {generated}",
        f"Effective symbols: {len(symbols)}",
        f"CoinGlass root: `{coinglass_root}`",
        f"Binance root: `{binance_root}`",
        "",
        "## Summary",
        "",
        f"- Both stores present: **{len(both)}/{len(symbols)}** symbols.",
        f"- Symbols with at least one aligned row: **{len(matched)}/{len(symbols)}**.",
        f"- Aligned rows: **{match_rows}/{bn_rows}** unique Binance settlement keys ({(match_rows / bn_rows):.1%} of keys where both stores exist)." if bn_rows else "- Aligned rows: **0/0**.",
        "- This is evidence for timestamp alignment and value comparison only; it does not authorize a gap fill or source switch.",
        "",
        "## Alignment rule",
        "",
        "- CoinGlass `time` is shifted forward by one hour to the settlement timestamp.",
        "- Binance `fundingTime` is rounded to the nearest UTC hour to remove millisecond jitter; the observed settlement cadence is not assumed to be 8h for this comparison.",
        "- CoinGlass `close` is converted from the existing percent contract to decimal by the canonical adapter.",
        "- No tolerance or pass/fail threshold is introduced here; differences remain Owner/audit evidence.",
        "",
        "## Per-symbol evidence",
        "",
        "| Symbol | CG rows | BN raw rows | BN unique settlements | CG date range | BN date range | Aligned rows | Median abs diff | Max abs diff | Max BN jitter (ms) |",
        "|---|---:|---:|---:|---|---|---:|---:|---:|---:|",
    ]
    for row in rows:
        med = "N/A" if row.get("median_abs_diff") is None else f"{row['median_abs_diff']:.10g}"
        max_diff = "N/A" if row.get("max_abs_diff") is None else f"{row['max_abs_diff']:.10g}"
        lines.append(
            f"| {row['symbol']} | {row['cg_rows']} | {row['bn_rows']} | {row.get('bn_unique_settlements', 0)} | "
            f"{row.get('cg_start', 'N/A')}–{row.get('cg_end', 'N/A')} | "
            f"{row.get('bn_start', 'N/A')}–{row.get('bn_end', 'N/A')} | {row['matches']} | "
            f"{med} | {max_diff} | {row.get('max_binance_jitter_ms', 0)} |"
        )
    lines += [
        "",
        "## Boundary and next decision",
        "",
        "- Raw parquet stores were read only; no files were merged, overwritten, or regenerated.",
        "- A complete 59-symbol × date object/schema verification is still outside this report and remains required before any T3 gap-fill execution.",
        "- Any Binance Vision download, contract migration, or scanner source change remains `OWNER_DECISIONS_NEEDED` and `PARK`.",
        "",
        "Status: `READ_ONLY_ALIGNMENT_EVIDENCE`",
    ]
    return "\n".join(lines) + "\n"


def main() -> int:
    parser = argparse.ArgumentParser(description="Build a read-only funding overlap report")
    parser.add_argument("--coinglass-root", type=Path, default=DEFAULT_COINGLASS)
    parser.add_argument("--binance-root", type=Path, default=DEFAULT_BINANCE)
    parser.add_argument("--universe", type=Path, default=PROJECT_ROOT / "config" / "universe.json")
    parser.add_argument("--output", type=Path, default=PROJECT_ROOT / "reports" / "DATA_FUNDING_OVERLAP_RECONCILIATION_20260716.md")
    args = parser.parse_args()
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(build_report(args.coinglass_root, args.binance_root, args.universe), encoding="utf-8")
    print(f"Report written to: {args.output}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
