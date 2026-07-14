"""Build the Phase 1 universe from local coinglass_db files only."""
from __future__ import annotations

import json
import sys
from datetime import datetime, timezone
from pathlib import Path

import pandas as pd
import yaml

PROJECT_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(PROJECT_ROOT))

from harness.lib.funding_normalize import raw_funding_hard_bounds


DB_ROOT = Path(r"C:\Users\10639\Desktop\加密\coinglass_db")
RAW_1H = DB_ROOT / "raw_1h"


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


def read_symbols() -> list[str]:
    with (DB_ROOT / "universe.json").open("r", encoding="utf-8") as f:
        data = json.load(f)
    return list(data.get("binance_symbols", []))


def funding_unit_report(symbols: list[str]) -> dict:
    lower, upper = raw_funding_hard_bounds()
    rows = []
    for symbol in symbols[:20]:
        path = RAW_1H / "funding_ohlc" / f"{symbol}.parquet"
        if not path.exists():
            continue
        df = pd.read_parquet(path, columns=["close"])
        values = df["close"].dropna().astype(float).abs()
        if not values.empty:
            rows.append(float(values.median()))
    if not rows:
        return {"status": "fail", "reason": "no funding samples"}
    median_abs = float(pd.Series(rows).median())
    status = "ok" if lower <= median_abs <= upper else "fail"
    return {
        "status": status,
        "sample_symbols": min(len(rows), 20),
        "median_abs_raw": median_abs,
        "expected_abs_range": [lower, upper],
        "unit_check": "within_spec" if status == "ok" else "outside_spec",
        "divided_by_100_risk": median_abs < lower,
        "multiplied_by_100_risk": median_abs > upper,
    }


def history_tier(hours: int, full_min_days: int, partial_min_days: int) -> str:
    days = hours / 24
    if days >= full_min_days:
        return "Full"
    if days >= partial_min_days:
        return "Partial"
    return "Insufficient"


def main() -> None:
    print_honesty()
    config = load_yaml(PROJECT_ROOT / "config" / "universe_config.yaml")
    symbols = read_symbols()
    rank_min = int(config["rank"]["min"])
    rank_max = int(config["rank"]["max"])
    min_turnover = float(config["liquidity"]["min_24h_turnover_usd"])
    majors = {f"{s}USDT" for s in config["exclude"]["majors"]}
    full_days = int(config["history_tiers"]["full_min_days"])
    partial_days = int(config["history_tiers"]["partial_min_days"])

    funding_report = funding_unit_report(symbols)
    if funding_report["status"] != "ok":
        raise SystemExit(f"STOP_AND_REPORT_OWNER funding unit check failed: {funding_report}")

    universe = []
    for idx, symbol in enumerate(symbols, start=1):
        if idx < rank_min or idx > rank_max or symbol in majors:
            continue
        kline_path = RAW_1H / "klines" / f"{symbol}.parquet"
        if not kline_path.exists():
            continue
        df = pd.read_parquet(kline_path)
        if df.empty:
            continue
        turnover_col = "quote_volume" if "quote_volume" in df.columns else "volume_usd"
        turnover = float(df[turnover_col].dropna().tail(24).sum())
        if turnover < min_turnover:
            continue
        universe.append(
            {
                "symbol": symbol,
                "rank": idx,
                "turnover_24h_usd": turnover,
                "history_tier": history_tier(len(df), full_days, partial_days),
                "eligible_for_paper": "Yes" if len(df) >= full_days * 24 else "No",
                "klines_path": str(kline_path),
                "funding_path": str(RAW_1H / "funding_ohlc" / f"{symbol}.parquet"),
                "oi_path": str(RAW_1H / "oi_ohlc" / f"{symbol}.parquet"),
            }
        )

    out = {
        "schema_version": "v1",
        "universe_config_version": config["universe_config_version"],
        "created_at_utc": datetime.now(timezone.utc).isoformat(),
        "source_db": str(DB_ROOT),
        "funding_unit_report": funding_report,
        "symbols": universe,
    }
    out_path = PROJECT_ROOT / "config" / "universe.json"
    out_path.write_text(json.dumps(out, indent=2, ensure_ascii=False), encoding="utf-8")
    print(f"wrote {out_path} symbols={len(universe)} funding={funding_report}")


if __name__ == "__main__":
    main()

