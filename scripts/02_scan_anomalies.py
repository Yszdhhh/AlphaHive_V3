"""Freeze a 90-day snapshot and append first-pass anomaly candidates."""
from __future__ import annotations

import argparse
import csv
import hashlib
import json
import sys
from datetime import datetime, timezone
from pathlib import Path

import pandas as pd
import yaml

PROJECT_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(PROJECT_ROOT))

from harness.lib.funding_normalize import normalize_funding
from harness.lib.cutoff import (
    KLINE_BAR_RESOLUTION,
    filter_completed_bars,
    resolve_completed_bar_cutoff,
)
from harness.lib.derivative_metrics import compute_metric_summary, empty_metric_summary
from harness.lib.turnover import turnover_map_from_snapshot

DB_ROOT = Path(r"C:\Users\10639\Desktop\加密\coinglass_db")
RAW_1H = DB_ROOT / "raw_1h"
LEDGER_PATH = PROJECT_ROOT / "ledger" / "Anomaly_Ledger.csv"
ARTIFACT_SCHEMA_VERSION = "v2"

HONESTY = [
    "1. This system does not produce alpha or validate direction; it records anomalies, net excess returns, and hypotheses.",
    "2. Any positive excess return is assumed beta or noise until it beats random baselines and bootstrap.",
    "3. Week 1 optimizes for a stable closed loop and reproducible samples, not selection quality.",
]


def print_honesty() -> None:
    for line in HONESTY:
        print(line)


def load_yaml(path: Path) -> dict:
    with path.open("r", encoding="utf-8") as f:
        return yaml.safe_load(f)


def _iso_utc_from_ms(value: int | None) -> str | None:
    if value is None:
        return None
    return pd.to_datetime(int(value), unit="ms", utc=True).isoformat()


def _input_inventory_entry(
    path: Path,
    frame: pd.DataFrame,
    input_type: str,
    symbol: str,
    time_column: str,
) -> dict:
    timestamps = pd.to_numeric(frame.get(time_column), errors="coerce").dropna()
    sorted_timestamps = timestamps.sort_values().drop_duplicates()
    steps = sorted_timestamps.diff().dropna()
    min_ts = int(timestamps.min()) if not timestamps.empty else None
    max_ts = int(timestamps.max()) if not timestamps.empty else None
    median_step = float(steps.median()) if not steps.empty else None
    return {
        "input_type": input_type,
        "symbol": symbol,
        "path": str(path),
        "exists": True,
        "content_sha256": sha256_file(path),
        "row_count": int(len(frame)),
        "time_column": time_column,
        "earliest_time_ms": min_ts,
        "earliest_time_utc": _iso_utc_from_ms(min_ts),
        "latest_time_ms": max_ts,
        "latest_time_utc": _iso_utc_from_ms(max_ts),
        "median_time_step_ms": median_step,
        "min_time_step_ms": float(steps.min()) if not steps.empty else None,
        "max_time_step_ms": float(steps.max()) if not steps.empty else None,
    }


def read_parquet_if_exists(
    path: Path,
    input_inventory: list[dict] | None = None,
    input_type: str | None = None,
    symbol: str | None = None,
    time_column: str = "time",
) -> pd.DataFrame:
    if not path.exists():
        if input_inventory is not None:
            input_inventory.append({
                "input_type": input_type,
                "symbol": symbol,
                "path": str(path),
                "exists": False,
                "content_sha256": None,
                "row_count": None,
                "time_column": time_column,
                "earliest_time_ms": None,
                "earliest_time_utc": None,
                "latest_time_ms": None,
                "latest_time_utc": None,
                "median_time_step_ms": None,
                "min_time_step_ms": None,
                "max_time_step_ms": None,
            })
        return pd.DataFrame()
    frame = pd.read_parquet(path)
    if input_inventory is not None:
        input_inventory.append(_input_inventory_entry(path, frame, input_type or "unknown", symbol or "", time_column))
    return frame


def normalize_kline(df: pd.DataFrame, symbol: str) -> pd.DataFrame:
    cols = ["open_time", "timestamp", "open", "high", "low", "close", "volume", "quote_volume", "volume_usd"]
    out = df[[c for c in cols if c in df.columns]].copy()
    if "open_time" in out.columns:
        out = out.rename(columns={"open_time": "timestamp"})
    if "timestamp" not in out.columns:
        out["timestamp"] = pd.NA
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


def _summary_columns(prefix: str, summary: dict) -> dict:
    return {
        f"{prefix}_status": summary["status"],
        f"{prefix}_n_valid": summary["n_valid"],
        f"{prefix}_window_start": summary["window_start"],
        f"{prefix}_window_end": summary["window_end"],
        f"{prefix}_coverage": summary["coverage"],
        f"{prefix}_reason": summary["reason"],
    }


def _attach_latest_quantile(frame: pd.DataFrame, summary: dict, column: str) -> pd.DataFrame:
    frame[column] = pd.NA
    latest_timestamp = summary.get("latest_timestamp")
    if latest_timestamp is not None:
        frame.loc[pd.to_numeric(frame["timestamp"], errors="coerce") == latest_timestamp, column] = summary["quantile"]
    return frame


def merge_derivatives(
    base: pd.DataFrame,
    symbol: str,
    effective_cutoff_ms: int,
    lookback_hours: int,
    input_inventory: list[dict] | None = None,
) -> tuple[pd.DataFrame, dict[str, dict]]:
    summaries = {
        "oi": empty_metric_summary("oi", "MISSING_SOURCE"),
        "funding": empty_metric_summary("funding", "MISSING_SOURCE"),
    }
    funding_path = RAW_1H / "funding_ohlc" / f"{symbol}.parquet"
    funding = read_parquet_if_exists(
        funding_path,
        input_inventory=input_inventory,
        input_type="funding_ohlc",
        symbol=symbol,
        time_column="time",
    )
    if not funding.empty:
        funding = funding[["time", "close"]].rename(columns={"time": "timestamp", "close": "funding_rate_8h_raw"})
        try:
            funding["funding_rate_8h"] = normalize_funding(funding["funding_rate_8h_raw"])
        except AssertionError as exc:
            raise SystemExit(f"STOP_AND_REPORT_OWNER funding guard failed symbol={symbol}: {exc}") from exc
        summaries["funding"], funding_metric = compute_metric_summary(
            funding,
            metric="funding",
            timestamp_col="timestamp",
            value_col="funding_rate_8h",
            effective_cutoff_ms=effective_cutoff_ms,
            lookback_hours=lookback_hours,
        )
        funding = funding.merge(
            funding_metric.rename(columns={"metric_value": "funding_metric_value"}),
            on="timestamp",
            how="left",
        )
        funding = _attach_latest_quantile(funding, summaries["funding"], "funding_self_quantile")
        base = base.merge(funding, on="timestamp", how="left")
    elif funding_path.exists():
        try:
            normalize_funding(pd.Series(dtype="float64"))
        except AssertionError as exc:
            raise SystemExit(f"STOP_AND_REPORT_OWNER funding guard failed symbol={symbol}: {exc}") from exc
    else:
        base["funding_rate_8h_raw"] = pd.NA
        base["funding_rate_8h"] = pd.NA
        base["funding_metric_value"] = pd.NA
        base["funding_self_quantile"] = pd.NA

    oi = read_parquet_if_exists(
        RAW_1H / "oi_ohlc" / f"{symbol}.parquet",
        input_inventory=input_inventory,
        input_type="oi_ohlc",
        symbol=symbol,
        time_column="time",
    )
    if not oi.empty:
        oi = oi[["time", "close"]].rename(columns={"time": "timestamp", "close": "open_interest"})
        summaries["oi"], oi_metric = compute_metric_summary(
            oi,
            metric="oi_change_24h",
            timestamp_col="timestamp",
            value_col="open_interest",
            effective_cutoff_ms=effective_cutoff_ms,
            lookback_hours=lookback_hours,
            derive_24h_change=True,
        )
        oi = oi.merge(
            oi_metric.rename(columns={"metric_value": "oi_change_pct_24h"}),
            on="timestamp",
            how="left",
        )
        oi = _attach_latest_quantile(oi, summaries["oi"], "oi_self_quantile")
        base = base.merge(oi, on="timestamp", how="left")
    else:
        base["open_interest"] = pd.NA
        base["oi_change_pct_24h"] = pd.NA
        base["oi_self_quantile"] = pd.NA
    return base, summaries


def sha256_file(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as f:
        for chunk in iter(lambda: f.read(1024 * 1024), b""):
            h.update(chunk)
    return h.hexdigest()


def inventory_status(input_inventory: list[dict], input_type: str) -> str:
    entries = [item for item in input_inventory if item.get("input_type") == input_type]
    if not entries:
        return "NOT_COMPUTED"
    if all(item.get("exists") is True for item in entries):
        return "COMPUTED"
    if any(item.get("exists") is True for item in entries):
        return "PARTIAL"
    return "NOT_COMPUTED"


def ledger_header() -> list[str]:
    with LEDGER_PATH.open("r", encoding="utf-8-sig", newline="") as f:
        return next(csv.reader(f))


def append_rows(path: Path, rows: list[dict]) -> None:
    if not rows:
        return
    header = ledger_header()
    with path.open("a", encoding="utf-8", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=header, extrasaction="ignore")
        for row in rows:
            writer.writerow({key: row.get(key, "") for key in header})


def build_symbol_meta(
    snapshot: pd.DataFrame,
    universe_meta: dict,
    min_valid_bars: int,
    min_effective_turnover_usd: float,
    derivative_meta: dict[str, dict[str, dict]],
) -> pd.DataFrame:
    turnover_map = turnover_map_from_snapshot(
        snapshot,
        min_valid_bars=min_valid_bars,
        min_effective_turnover_usd=min_effective_turnover_usd,
    )
    rows = []
    for symbol, result in turnover_map.items():
        meta = universe_meta.get(symbol, {})
        rows.append({
            "symbol": symbol,
            "rank": meta.get("rank"),
            "history_tier": meta.get("history_tier", "Benchmark" if symbol == "BTCUSDT" else ""),
            "eligible_for_paper": meta.get("eligible_for_paper", "No" if symbol == "BTCUSDT" else ""),
            "turnover_24h_usd_effective": result.turnover_24h_usd_effective,
            "n_valid_bars": result.n_valid_bars,
            "threshold_pass": result.threshold_pass,
            "valid_bar_pass": result.valid_bar_pass,
            "confidence": result.confidence,
            "turnover_reason": result.reason,
            **_summary_columns("oi", derivative_meta.get(symbol, {}).get("oi", empty_metric_summary("oi", "MISSING_SUMMARY"))),
            **_summary_columns("funding", derivative_meta.get(symbol, {}).get("funding", empty_metric_summary("funding", "MISSING_SUMMARY"))),
        })
    return pd.DataFrame(rows)


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--run_id", default=None)
    parser.add_argument("--scan_time_utc", default=None, help="Historical replay scan time, e.g. 2026-06-30T00:00:00Z")
    args = parser.parse_args()

    print_honesty()
    scan_rules = load_yaml(PROJECT_ROOT / "config" / "scan_rules.yaml")
    with (PROJECT_ROOT / "config" / "universe.json").open("r", encoding="utf-8") as f:
        universe = json.load(f)["symbols"]

    now = datetime.now(timezone.utc)
    scan_dt = pd.Timestamp(args.scan_time_utc).tz_convert("UTC") if args.scan_time_utc else pd.Timestamp(now)
    run_id = args.run_id or scan_dt.strftime("%Y%m%d_%H%M_utc")
    scan_time = scan_dt.isoformat()
    effective_cutoff_ms, cutoff_blockers = resolve_completed_bar_cutoff(scan_time)
    if cutoff_blockers:
        raise SystemExit(f"STOP_AND_REPORT_OWNER cutoff resolution failed: {cutoff_blockers}")
    run_dir = PROJECT_ROOT / "harness" / "runs" / run_id
    run_dir.mkdir(parents=True, exist_ok=True)

    lookback_hours = int(scan_rules["quantile"]["lookback_days"]) * 24
    min_valid_bars = int(scan_rules.get("baseline_pool", {}).get("min_valid_turnover_bars_24h", 18))
    min_turnover = float(scan_rules.get("baseline_pool", {}).get("min_effective_turnover_usd"))
    frames = []
    input_inventory: list[dict] = []
    derivative_meta: dict[str, dict[str, dict]] = {}
    cutoff_audit = {
        "rows_read": 0,
        "rows_kept": 0,
        "filtered_rows": 0,
        "filtered_incomplete_or_future_rows": 0,
        "filtered_invalid_timestamp_rows": 0,
        "completed_bar_violations": 0,
        "max_kept_bar_end_ms": None,
    }
    meta_by_symbol = {item["symbol"]: item for item in universe}
    benchmark_symbol = "BTCUSDT"

    for item in universe:
        symbol = item["symbol"]
        kline = read_parquet_if_exists(
            RAW_1H / "klines" / f"{symbol}.parquet",
            input_inventory=input_inventory,
            input_type="klines",
            symbol=symbol,
            time_column="open_time",
        )
        if kline.empty:
            continue
        norm = normalize_kline(kline, symbol)
        norm, audit = filter_completed_bars(norm, effective_cutoff_ms)
        for key, value in audit.items():
            if key == "max_kept_bar_end_ms":
                if value is not None:
                    cutoff_audit[key] = max(cutoff_audit[key] or value, value)
            else:
                cutoff_audit[key] += value
        snap = norm.tail(lookback_hours)
        snap, summaries = merge_derivatives(
            snap,
            symbol,
            effective_cutoff_ms=effective_cutoff_ms,
            lookback_hours=lookback_hours,
            input_inventory=input_inventory,
        )
        derivative_meta[symbol] = summaries
        frames.append(snap)

    benchmark_kline = read_parquet_if_exists(
        RAW_1H / "klines" / f"{benchmark_symbol}.parquet",
        input_inventory=input_inventory,
        input_type="klines",
        symbol=benchmark_symbol,
        time_column="open_time",
    )
    if not benchmark_kline.empty:
        benchmark_norm = normalize_kline(benchmark_kline, benchmark_symbol)
        benchmark_norm, audit = filter_completed_bars(benchmark_norm, effective_cutoff_ms)
        for key, value in audit.items():
            if key == "max_kept_bar_end_ms":
                if value is not None:
                    cutoff_audit[key] = max(cutoff_audit[key] or value, value)
            else:
                cutoff_audit[key] += value
        benchmark_snap = benchmark_norm.tail(lookback_hours)
        benchmark_snap, summaries = merge_derivatives(
            benchmark_snap,
            benchmark_symbol,
            effective_cutoff_ms=effective_cutoff_ms,
            lookback_hours=lookback_hours,
            input_inventory=input_inventory,
        )
        derivative_meta[benchmark_symbol] = summaries
        benchmark_snap["is_benchmark"] = True
        frames.append(benchmark_snap)

    snapshot = pd.concat(frames, ignore_index=True) if frames else pd.DataFrame()
    if "is_benchmark" not in snapshot.columns:
        snapshot["is_benchmark"] = False
    snapshot["is_benchmark"] = snapshot["is_benchmark"].fillna(False)

    symbol_meta = (
        build_symbol_meta(snapshot, meta_by_symbol, min_valid_bars, min_turnover, derivative_meta)
        if not snapshot.empty else pd.DataFrame()
    )
    if not snapshot.empty:
        for symbol, summaries in derivative_meta.items():
            mask = snapshot["symbol"] == symbol
            for prefix, summary in summaries.items():
                for column, value in _summary_columns(prefix, summary).items():
                    snapshot.loc[mask, column] = value
    if not symbol_meta.empty:
        meta_cols = symbol_meta[[
            "symbol", "turnover_24h_usd_effective", "n_valid_bars",
            "threshold_pass", "valid_bar_pass", "confidence", "turnover_reason",
        ]]
        snapshot = snapshot.merge(meta_cols, on="symbol", how="left")

    snapshot_path = run_dir / "input_snapshot.csv"
    snapshot.to_csv(snapshot_path, index=False)
    symbol_meta_path = run_dir / "symbol_meta.csv"
    symbol_meta.to_csv(symbol_meta_path, index=False)

    candidates = []
    if not snapshot.empty:
        btc = snapshot[snapshot["symbol"] == benchmark_symbol].sort_values("timestamp")
        btc_ret = 0.0
        if len(btc) >= 25:
            btc_ret = (float(btc["close"].iloc[-1]) / float(btc["close"].iloc[-25]) - 1.0) * 100
        meta_lookup = symbol_meta.set_index("symbol").to_dict("index") if not symbol_meta.empty else {}

        for symbol, df in snapshot.groupby("symbol"):
            if symbol not in meta_by_symbol:
                continue
            smeta = meta_lookup.get(symbol, {})
            effective_turnover = smeta.get("turnover_24h_usd_effective")
            if (
                pd.isna(effective_turnover)
                or effective_turnover is None
                or smeta.get("threshold_pass") is not True
                or smeta.get("valid_bar_pass") is not True
            ):
                continue
            df = df.sort_values("timestamp")
            if len(df) < 25:
                continue
            close = pd.to_numeric(df["close"], errors="coerce")
            ret_24h = (float(close.iloc[-1]) / float(close.iloc[-25]) - 1.0) * 100
            vol_24h = close.pct_change().rolling(24).std().dropna()
            if vol_24h.empty:
                continue
            latest_vol = float(vol_24h.iloc[-1])
            vol_quantile = float((vol_24h <= latest_vol).mean())
            excess = ret_24h - btc_ret
            funding = pd.to_numeric(df["funding_rate_8h"], errors="coerce").dropna()
            latest_funding = float(funding.iloc[-1]) if not funding.empty else ""
            oi_change = pd.to_numeric(df.get("oi_change_pct_24h"), errors="coerce").dropna()
            latest_oi_change = float(oi_change.iloc[-1]) if not oi_change.empty else ""
            triggers = []
            if vol_quantile >= float(scan_rules["triggers"]["vol_quantile_high"]):
                triggers.append("vol_quantile_high")
            if abs(ret_24h) >= float(scan_rules["large_move"]["large_move_threshold_abs_pct_24h"]):
                triggers.append("large_move_abs")
            if abs(excess) >= float(scan_rules["large_move"]["large_move_threshold_excess_pct_24h"]):
                triggers.append("large_move_excess")
            if not triggers:
                continue
            meta = meta_by_symbol[symbol]
            candidates.append({
                "schema_version": ARTIFACT_SCHEMA_VERSION,
                "run_id": run_id,
                "record_id": f"{run_id}_{len(candidates)+1:04d}",
                "scan_time_utc": scan_time,
                "symbol": symbol,
                "rank": meta["rank"],
                "turnover_24h_usd": round(float(effective_turnover), 2),
                "history_tier": meta["history_tier"],
                "eligible_for_paper": meta["eligible_for_paper"],
                "trigger_reason": "|".join(triggers),
                "trigger_metric": "vol_24h",
                "trigger_value": latest_vol,
                "trigger_quantile": vol_quantile,
                "large_move_flag_24h": str("large_move_abs" in triggers or "large_move_excess" in triggers),
                "abs_move_pct_24h": ret_24h,
                "excess_move_pct_24h": excess,
                "funding_sign": "positive" if latest_funding != "" and latest_funding > 0 else "negative" if latest_funding != "" and latest_funding < 0 else "",
                "funding_rate_8h": latest_funding,
                "oi_change_pct_24h": latest_oi_change,
                "oi_status": smeta.get("oi_status", "NOT_COMPUTED"),
                "funding_status": smeta.get("funding_status", "NOT_COMPUTED"),
                "input_inventory_status": "RECORDED",
                "is_top_candidate": "",
                "decision": "",
                "direction": "",
                "direction_sign": "",
            })

    candidates = sorted(candidates, key=lambda r: abs(float(r["excess_move_pct_24h"])), reverse=True)
    candidates = candidates[: int(scan_rules["candidates"]["target_per_scan_max"])]
    top_n = int(scan_rules["candidates"]["top_n_for_review"])
    for idx, row in enumerate(candidates):
        row["is_top_candidate"] = "true" if idx < top_n else "false"
        if idx >= top_n:
            row["decision"] = "AutoSkipped"
            row["direction"] = "Neutral"
            row["direction_sign"] = 0

    candidates_path = run_dir / "candidates.csv"
    pd.DataFrame(candidates).to_csv(candidates_path, index=False)
    append_rows(LEDGER_PATH, candidates)

    manifest = {
        "schema_version": ARTIFACT_SCHEMA_VERSION,
        "run_id": run_id,
        "scan_time_utc": scan_time,
        "requested_scan_time_utc": scan_time,
        "resolved_effective_cutoff_ms": effective_cutoff_ms,
        "resolved_effective_cutoff_utc": pd.to_datetime(effective_cutoff_ms, unit="ms", utc=True).isoformat(),
        "last_completed_bar_ms": int(snapshot["timestamp"].max()) if not snapshot.empty else None,
        "last_completed_bar_utc": (
            pd.to_datetime(int(snapshot["timestamp"].max()), unit="ms", utc=True).isoformat()
            if not snapshot.empty else None
        ),
        "bar_resolution": KLINE_BAR_RESOLUTION,
        "data_cutoff": effective_cutoff_ms,
        "input_inventory_status": "RECORDED",
        "derivative_inventory": {
            "funding_status": inventory_status(input_inventory, "funding_ohlc"),
            "oi_status": inventory_status(input_inventory, "oi_ohlc"),
        },
        "input_inventory": input_inventory,
        "snapshot_path": str(snapshot_path),
        "snapshot_sha256": sha256_file(snapshot_path),
        "symbol_meta_path": str(symbol_meta_path),
        "symbol_meta_sha256": sha256_file(symbol_meta_path),
        "return_tape_path": None,
        "return_tape_sha256": None,
        "benchmark_symbol": benchmark_symbol,
        "known_list_version": "v1",
        "known_list_source": "config/universe.json:known_list",
        "migration_history_status": "NOT_AVAILABLE",
        "known_symbols": sorted(set(meta_by_symbol) | {benchmark_symbol}),
        "benchmark_frozen_in_snapshot": bool((snapshot["symbol"] == benchmark_symbol).any()) if not snapshot.empty else False,
        "candidate_count": len(candidates),
        "integrity": {
            "no_lookahead_attested": bool(
                cutoff_audit["completed_bar_violations"] == 0
                and cutoff_audit["rows_kept"] <= cutoff_audit["rows_read"]
                and (
                    cutoff_audit["max_kept_bar_end_ms"] is None
                    or cutoff_audit["max_kept_bar_end_ms"] <= effective_cutoff_ms
                )
            ),
            "snapshot_is_90d_long_table": True,
            "completed_bar_rule": "bar_open_time + 1h <= resolved_effective_cutoff",
            "cutoff_audit": cutoff_audit,
        },
    }
    (run_dir / "run_manifest.json").write_text(json.dumps(manifest, indent=2), encoding="utf-8")
    print(f"wrote run={run_id} snapshot_rows={len(snapshot)} candidates={len(candidates)}")


if __name__ == "__main__":
    main()



