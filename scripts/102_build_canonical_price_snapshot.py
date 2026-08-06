"""Build and atomically publish the Owner-approved local canonical price view."""
from __future__ import annotations

import argparse
from datetime import datetime, timezone
import json
from pathlib import Path
import sys

import pandas as pd

PROJECT_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(PROJECT_ROOT))

from harness.lib.candidate_data_bridge import CandidateBridgeError, build_price_snapshot
from harness.lib.canonical_price_snapshot import (
    DEFAULT_ROOT,
    CanonicalPriceSnapshotError,
    evaluate_gap_policy,
    publish_price_snapshot,
)
from harness.lib.cutoff import resolve_completed_bar_cutoff


BINANCE_KLINES = Path(r"C:\Users\10639\Desktop\加密\binance_free_db\raw_1h\klines")
COINGLASS_KLINES = Path(r"C:\Users\10639\Desktop\加密\coinglass_db\raw_1h\klines")


def effective_symbols(universe_path: Path) -> list[str]:
    data = json.loads(universe_path.read_text(encoding="utf-8"))
    disabled = set(data.get("disabled_pull_symbols", []))
    symbols = [row["symbol"] if isinstance(row, dict) else str(row) for row in data.get("symbols", [])]
    symbols.extend(str(symbol) for symbol in data.get("benchmark_symbols", []))
    return list(dict.fromkeys(symbol for symbol in symbols if symbol not in disabled))


def _frame(path: Path) -> pd.DataFrame | None:
    return pd.read_parquet(path) if path.exists() else None


def main() -> int:
    parser = argparse.ArgumentParser(description="Publish a local canonical price snapshot")
    parser.add_argument("--scan-time-utc", default=None)
    parser.add_argument("--universe", type=Path, default=PROJECT_ROOT / "config" / "universe.json")
    parser.add_argument("--output-root", type=Path, default=DEFAULT_ROOT)
    args = parser.parse_args()
    scan_time = args.scan_time_utc or datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
    cutoff_ms, blockers = resolve_completed_bar_cutoff(scan_time)
    if blockers:
        raise SystemExit(f"STOP_AND_REPORT_OWNER cutoff resolution failed: {blockers}")

    accepted = {}
    rejected = {}
    for symbol in effective_symbols(args.universe):
        try:
            snapshot = build_price_snapshot(
                symbol=symbol,
                binance_klines=_frame(BINANCE_KLINES / f"{symbol}.parquet"),
                coinglass_klines=_frame(COINGLASS_KLINES / f"{symbol}.parquet"),
                effective_cutoff_ms=cutoff_ms,
            )
            decision = evaluate_gap_policy(snapshot.manifest)
            if decision["status"] == "BLOCK":
                rejected[symbol] = decision
            else:
                snapshot.manifest["gap_policy"] = decision
                accepted[symbol] = (snapshot.rows, snapshot.manifest)
        except CandidateBridgeError as exc:
            rejected[symbol] = {"status": "BLOCK", "reason": str(exc)}
    if rejected:
        raise SystemExit(f"STOP_AND_REPORT_OWNER canonical snapshot blocked symbols: {json.dumps(rejected, sort_keys=True)}")
    try:
        pointer = publish_price_snapshot(accepted, root=args.output_root)
    except CanonicalPriceSnapshotError as exc:
        raise SystemExit(f"STOP_AND_REPORT_OWNER canonical publication failed: {exc}") from exc
    print(json.dumps({"pointer": pointer, "symbol_count": len(accepted), "effective_cutoff_ms": cutoff_ms}, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
