"""Build an immutable post-scan return tape for a run.

The return tape is separate from input_snapshot.csv. It contains only the symbols
needed for return backfill: anomaly symbols, baseline symbols, and BTCUSDT.
"""
from __future__ import annotations

import argparse
import hashlib
import json
from datetime import timedelta
from pathlib import Path

import pandas as pd

PROJECT_ROOT = Path(__file__).resolve().parents[1]
RUNS_DIR = PROJECT_ROOT / "harness" / "runs"
LEDGER_DIR = PROJECT_ROOT / "ledger"
RAW_1H = Path(r"C:\Users\10639\Desktop\加密\coinglass_db\raw_1h")
ANOMALY_LEDGER = LEDGER_DIR / "Anomaly_Ledger.csv"
BASELINE_LEDGER = LEDGER_DIR / "Baseline_Ledger.csv"
BTC_SYMBOL = "BTCUSDT"
MAX_HOLDING_HOURS = 168


def sha256_file(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as f:
        for chunk in iter(lambda: f.read(1024 * 1024), b""):
            h.update(chunk)
    return h.hexdigest()


def normalize_kline(df: pd.DataFrame, symbol: str) -> pd.DataFrame:
    cols = ["open_time", "timestamp", "open", "high", "low", "close", "volume", "quote_volume", "volume_usd"]
    out = df[[c for c in cols if c in df.columns]].copy()
    if "open_time" in out.columns:
        out = out.rename(columns={"open_time": "timestamp"})
    if "timestamp" not in out.columns:
        raise ValueError(f"{symbol} kline missing timestamp/open_time")
    if "quote_volume" in out.columns and "volume_usd" in out.columns:
        out["turnover_usd"] = pd.to_numeric(out["quote_volume"], errors="coerce").fillna(
            pd.to_numeric(out["volume_usd"], errors="coerce")
        )
    elif "quote_volume" in out.columns:
        out["turnover_usd"] = pd.to_numeric(out["quote_volume"], errors="coerce")
    elif "volume_usd" in out.columns:
        out["turnover_usd"] = pd.to_numeric(out["volume_usd"], errors="coerce")
    else:
        out["turnover_usd"] = pd.NA
    out = out.drop(columns=[c for c in ["quote_volume", "volume_usd"] if c in out.columns])
    out["symbol"] = symbol
    return out


def needed_symbols(run_id: str) -> set[str]:
    anomaly = pd.read_csv(ANOMALY_LEDGER)
    baseline = pd.read_csv(BASELINE_LEDGER)
    symbols = set(anomaly[anomaly["run_id"] == run_id]["symbol"].dropna().astype(str))
    symbols.update(baseline[baseline["run_id"] == run_id]["symbol"].dropna().astype(str))
    symbols.add(BTC_SYMBOL)
    return symbols


def read_symbol_tape(symbol: str, start_ms: int, end_ms: int) -> pd.DataFrame:
    path = RAW_1H / "klines" / f"{symbol}.parquet"
    if not path.exists():
        return pd.DataFrame()
    df = normalize_kline(pd.read_parquet(path), symbol)
    ts = pd.to_numeric(df["timestamp"], errors="coerce")
    return df[(ts >= start_ms) & (ts <= end_ms)].copy()


def update_manifest(run_dir: Path, tape_path: Path) -> None:
    manifest_path = run_dir / "run_manifest.json"
    manifest = json.loads(manifest_path.read_text(encoding="utf-8")) if manifest_path.exists() else {}
    manifest["return_tape_path"] = str(tape_path)
    manifest["return_tape_sha256"] = sha256_file(tape_path)
    manifest_path.write_text(json.dumps(manifest, indent=2), encoding="utf-8")


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--run_id", required=True)
    args = parser.parse_args()
    run_id = args.run_id
    run_dir = RUNS_DIR / run_id
    candidates_path = run_dir / "candidates.csv"
    if not candidates_path.exists():
        raise SystemExit(f"missing candidates.csv for {run_id}")
    candidates = pd.read_csv(candidates_path)
    scan_times = pd.to_datetime(candidates["scan_time_utc"], utc=True, errors="coerce").dropna()
    if scan_times.empty:
        raise SystemExit(f"no scan_time_utc for {run_id}")
    scan_start = scan_times.min()
    start_ms = int(scan_start.value / 1e6)
    end_ms = int((scan_start + timedelta(hours=MAX_HOLDING_HOURS + 2)).value / 1e6)

    frames = []
    missing = []
    for symbol in sorted(needed_symbols(run_id)):
        tape = read_symbol_tape(symbol, start_ms, end_ms)
        if tape.empty:
            missing.append(symbol)
        else:
            frames.append(tape)
    out = pd.concat(frames, ignore_index=True) if frames else pd.DataFrame()
    tape_path = run_dir / "return_tape.csv"
    out.to_csv(tape_path, index=False)
    update_manifest(run_dir, tape_path)
    print(f"wrote {tape_path} rows={len(out)} symbols={out['symbol'].nunique() if not out.empty else 0}")
    if missing:
        print(f"missing_symbols={missing}")


if __name__ == "__main__":
    main()
