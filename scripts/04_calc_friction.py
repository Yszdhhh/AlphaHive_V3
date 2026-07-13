"""Calculate round-trip friction and funding cost for a run."""
from __future__ import annotations

import argparse
import sys
from pathlib import Path

import pandas as pd
import yaml

PROJECT_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(PROJECT_ROOT))

from harness.lib.funding_normalize import assert_normalized_funding

LEDGER_DIR = PROJECT_ROOT / "ledger"
CONFIG_DIR = PROJECT_ROOT / "config"
RUNS_DIR = PROJECT_ROOT / "harness" / "runs"
ANOMALY_LEDGER = LEDGER_DIR / "Anomaly_Ledger.csv"
BASELINE_LEDGER = LEDGER_DIR / "Baseline_Ledger.csv"
FRICTION_CONFIG = CONFIG_DIR / "friction_config.yaml"


def load_yaml(path: Path) -> dict:
    with path.open("r", encoding="utf-8") as f:
        return yaml.safe_load(f)


def get_tier_value(turnover_usd: float, tiers: list[dict], value_key: str) -> float:
    sorted_tiers = sorted(tiers, key=lambda t: float(t["min_turnover_usd"]))
    if turnover_usd is None or pd.isna(turnover_usd) or turnover_usd <= 0:
        return sorted_tiers[0][value_key]
    selected = sorted_tiers[0]
    for tier in sorted_tiers:
        if turnover_usd >= float(tier["min_turnover_usd"]):
            selected = tier
    return selected[value_key]


def calc_roundtrip_friction_bps(turnover_usd: float, config: dict) -> tuple[float, dict]:
    taker = float(config["fees"]["taker_fee_bps"])
    slip = float(get_tier_value(turnover_usd, config["slippage_tiers_bps"], "slippage_bps"))
    spread = float(get_tier_value(turnover_usd, config["spread_bps_fallback"]["tiers"], "spread_bps"))
    one_way = taker + slip + spread
    return 2.0 * one_way, {
        "taker_fee_bps": taker,
        "slippage_bps": slip,
        "spread_bps": spread,
        "one_way_bps": one_way,
        "spread_is_estimate": bool(config["spread_bps_fallback"].get("is_estimate", True)),
    }


def calc_funding_cost(funding_rate_8h_decimal: float, holding_hours: float, direction_sign: int) -> float:
    if direction_sign == 0 or pd.isna(funding_rate_8h_decimal):
        return 0.0
    return float(direction_sign) * (float(holding_hours) / 8.0) * float(funding_rate_8h_decimal)


def latest_run_id() -> str:
    runs = sorted([p.name for p in RUNS_DIR.iterdir() if p.is_dir()])
    if not runs:
        raise SystemExit("No harness runs found")
    return runs[-1]


def load_symbol_meta(run_id: str) -> pd.DataFrame:
    path = RUNS_DIR / run_id / "symbol_meta.csv"
    if not path.exists():
        raise SystemExit(f"Missing symbol_meta.csv for run_id={run_id}")
    return pd.read_csv(path)


def meta_turnover(meta: pd.DataFrame, symbol: str) -> tuple[float, str]:
    row = meta[meta["symbol"] == symbol]
    if row.empty:
        return float("nan"), "none"
    turnover = pd.to_numeric(row.iloc[0].get("turnover_24h_usd_effective"), errors="coerce")
    confidence = str(row.iloc[0].get("confidence", "none"))
    return float(turnover) if pd.notna(turnover) else float("nan"), confidence


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--run_id", default=None)
    args = parser.parse_args()
    run_id = args.run_id or latest_run_id()

    config = load_yaml(FRICTION_CONFIG)
    anomaly_all = pd.read_csv(ANOMALY_LEDGER)
    baseline_all = pd.read_csv(BASELINE_LEDGER)
    anomaly = anomaly_all[anomaly_all["run_id"] == run_id].copy()
    baseline = baseline_all[baseline_all["run_id"] == run_id].copy()
    if anomaly.empty:
        raise SystemExit(f"No anomaly rows for run_id={run_id}")

    meta = load_symbol_meta(run_id)
    parent_funding = {}
    anomaly_updates = []

    for _, row in anomaly.iterrows():
        rid = row["record_id"]
        symbol = row["symbol"]
        turnover = float(row.get("turnover_24h_usd", float("nan")))
        rate_raw = row.get("funding_rate_8h", float("nan"))
        rate_dec = float(rate_raw) if pd.notna(rate_raw) and rate_raw != "" else float("nan")
        if pd.notna(rate_dec):
            assert_normalized_funding(pd.Series([rate_dec]))
        parent_funding[rid] = rate_dec
        friction, fees = calc_roundtrip_friction_bps(turnover, config)
        anomaly_updates.append({
            "record_id": rid,
            "symbol": symbol,
            "friction_bps_roundtrip": friction,
            "funding_cost_component": float("nan"),
            "fees": fees,
        })

    baseline_updates = []
    for _, row in baseline.iterrows():
        bid = row["baseline_id"]
        symbol = row["symbol"]
        turnover, confidence = meta_turnover(meta, symbol)
        friction, fees = calc_roundtrip_friction_bps(turnover, config)
        direction_sign = int(row.get("direction_sign", 0)) if pd.notna(row.get("direction_sign", 0)) and row.get("direction_sign", "") != "" else 0
        holding_hours = float(row.get("holding_period_hours", 0))
        parent_rate = parent_funding.get(row.get("parent_record_id"), float("nan"))
        funding_cost = calc_funding_cost(parent_rate, holding_hours, direction_sign)
        baseline_updates.append({
            "baseline_id": bid,
            "symbol": symbol,
            "turnover_24h_usd_used": turnover,
            "turnover_confidence": confidence,
            "friction_bps_roundtrip": friction,
            "funding_cost_component": funding_cost,
            "fees": fees,
        })

    anomaly_out = anomaly_all.copy()
    baseline_out = baseline_all.copy()
    for update in anomaly_updates:
        mask = anomaly_out["record_id"] == update["record_id"]
        anomaly_out.loc[mask, "friction_bps_roundtrip"] = update["friction_bps_roundtrip"]
        anomaly_out.loc[mask, "funding_cost_component"] = update["funding_cost_component"]

    for update in baseline_updates:
        mask = baseline_out["baseline_id"] == update["baseline_id"]
        baseline_out.loc[mask, "friction_bps_roundtrip"] = update["friction_bps_roundtrip"]
        baseline_out.loc[mask, "funding_cost_component"] = update["funding_cost_component"]

    anomaly_out.to_csv(ANOMALY_LEDGER, index=False)
    baseline_out.to_csv(BASELINE_LEDGER, index=False)

    run_baselines = RUNS_DIR / run_id / "baselines.csv"
    if run_baselines.exists():
        bfile = pd.read_csv(run_baselines)
        for update in baseline_updates:
            mask = bfile["baseline_id"] == update["baseline_id"]
            bfile.loc[mask, "friction_bps_roundtrip"] = update["friction_bps_roundtrip"]
            bfile.loc[mask, "funding_cost_component"] = update["funding_cost_component"]
            bfile.loc[mask, "turnover_24h_usd_used"] = update["turnover_24h_usd_used"]
            bfile.loc[mask, "turnover_confidence"] = update["turnover_confidence"]
        bfile.to_csv(run_baselines, index=False)

    print(f"04 complete run_id={run_id}: anomaly={len(anomaly_updates)} baseline={len(baseline_updates)}")
    if baseline_updates:
        values = [u["friction_bps_roundtrip"] for u in baseline_updates]
        print(f"baseline friction range: {min(values):.2f}-{max(values):.2f} bps")


if __name__ == "__main__":
    main()


