"""Generate deterministic A/B random baselines for one run."""
from __future__ import annotations

import argparse
import csv
import json
import sys
from pathlib import Path

import pandas as pd
import yaml

PROJECT_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(PROJECT_ROOT))
sys.path.insert(0, str(PROJECT_ROOT / "harness"))

import seed  # noqa: E402
from harness.lib.baseline_pool import build_candidate_pool, build_full_pool, pool_diversity, pool_status

LEDGER_PATH = PROJECT_ROOT / "ledger" / "Baseline_Ledger.csv"

HONESTY = [
    "1. This system does not produce alpha or validate direction; it records anomalies, net excess returns, and hypotheses.",
    "2. Any positive excess return is assumed beta or noise until it beats random baselines and bootstrap.",
    "3. Week 1 optimizes for a stable closed loop and reproducible samples, not selection quality.",
]


def print_honesty() -> None:
    for line in HONESTY:
        print(line)


def ledger_header() -> list[str]:
    with LEDGER_PATH.open("r", encoding="utf-8-sig", newline="") as f:
        return next(csv.reader(f))


def load_yaml(path: Path) -> dict:
    with path.open("r", encoding="utf-8") as f:
        return yaml.safe_load(f)


def append_rows(rows: list[dict]) -> None:
    if not rows:
        return
    header = ledger_header()
    with LEDGER_PATH.open("a", encoding="utf-8", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=header, extrasaction="ignore")
        for row in rows:
            writer.writerow({key: row.get(key, "") for key in header})


def choose_symbol(pool: list[str], rng) -> str | None:
    if not pool:
        return None
    return pool[int(rng.randint(0, len(pool)))]


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--run_id", default=None)
    args = parser.parse_args()

    print_honesty()
    runs_root = PROJECT_ROOT / "harness" / "runs"
    run_dir = runs_root / args.run_id if args.run_id else sorted([p for p in runs_root.iterdir() if p.is_dir()])[-1]
    run_id = run_dir.name

    candidates_path = run_dir / "candidates.csv"
    symbol_meta_path = run_dir / "symbol_meta.csv"
    if not candidates_path.exists() or not symbol_meta_path.exists():
        raise SystemExit(f"Missing candidates or symbol_meta for run_id={run_id}")

    candidates = pd.read_csv(candidates_path)
    symbol_meta = pd.read_csv(symbol_meta_path)
    scan_rules = load_yaml(PROJECT_ROOT / "config" / "scan_rules.yaml")
    pool_rules = scan_rules.get("baseline_pool", {})
    min_turnover = float(pool_rules.get("min_effective_turnover_usd", 10_000_000))
    holding_periods = [int(v) for v in scan_rules["holding_periods_hours"]]

    candidate_symbols = set(build_candidate_pool(candidates))
    eligible_meta = symbol_meta[
        pd.to_numeric(symbol_meta["turnover_24h_usd_effective"], errors="coerce") >= min_turnover
    ]
    candidate_pool = sorted(set(eligible_meta[eligible_meta["symbol"].isin(candidate_symbols)]["symbol"].astype(str)))
    full_pool = build_full_pool(symbol_meta, min_turnover)

    print(f"\n--- Pool construction ({run_id}) ---")
    print(f"  candidate_pool: {len(candidate_pool)} symbols")
    print(f"  full_pool: {len(full_pool)} symbols")

    if not full_pool:
        raise SystemExit("full_pool_random cannot be built: no eligible symbols in frozen symbol_meta")
    if not candidate_pool:
        print("  WARNING: candidate_pool_random is empty; candidate baselines will be marked insufficient_pool")

    rows = []
    drawn_candidate = []
    drawn_full = []
    for _, cand in candidates.iterrows():
        for holding_period in holding_periods:
            for baseline_type, pool in [("candidate_pool_random", candidate_pool), ("full_pool_random", full_pool)]:
                seed_record_id = f"{cand['record_id']}_{holding_period}h"
                rng = seed.baseline_rng(str(cand["scan_time_utc"]), seed_record_id, baseline_type)
                symbol = choose_symbol(pool, rng)
                direction, direction_sign = seed.random_direction(rng)
                random_seed = seed.baseline_seed(str(cand["scan_time_utc"]), seed_record_id, baseline_type)
                if baseline_type == "candidate_pool_random" and symbol:
                    drawn_candidate.append(symbol)
                if baseline_type == "full_pool_random" and symbol:
                    drawn_full.append(symbol)
                rows.append({
                    "schema_version": "v2",
                    "run_id": run_id,
                    "baseline_id": f"{cand['record_id']}_{holding_period}h_{baseline_type}",
                    "parent_record_id": cand["record_id"],
                    "baseline_type": baseline_type,
                    "scan_time_utc": cand["scan_time_utc"],
                    "symbol": symbol or "",
                    "random_seed": random_seed,
                    "direction": direction if symbol else "",
                    "direction_sign": direction_sign if symbol else "",
                    "holding_period_hours": holding_period,
                    "pool_status": "pending",
                    "pool_unique_n": "",
                    "pool_entropy_ratio": "",
                    "notes": "three-way aligned: scan_time, holding_period, random direction",
                })

    cand_metrics = pool_diversity(drawn_candidate)
    full_metrics = pool_diversity(drawn_full)
    cand_status = pool_status(cand_metrics, pool_rules) if drawn_candidate else "insufficient_pool"
    full_status = "ok" if full_metrics["unique"] >= 1 else "insufficient_pool"

    for row in rows:
        if row["baseline_type"] == "candidate_pool_random":
            row["pool_status"] = cand_status
            row["pool_unique_n"] = cand_metrics["unique"]
            row["pool_entropy_ratio"] = cand_metrics["entropy_ratio"]
            if cand_status != "ok":
                row["notes"] += "; insufficient_pool: excluded from judgment"
        else:
            row["pool_status"] = full_status
            row["pool_unique_n"] = full_metrics["unique"]
            row["pool_entropy_ratio"] = full_metrics["entropy_ratio"]

    out_path = run_dir / "baselines.csv"
    pd.DataFrame(rows).to_csv(out_path, index=False)
    append_rows(rows)

    pool_report = {
        "run_id": run_id,
        "candidate_pool": {
            "source_unique_symbols": len(candidate_pool),
            "drawn_metrics": cand_metrics,
            "status": cand_status,
            "symbols": candidate_pool,
        },
        "full_pool": {
            "source_unique_symbols": len(full_pool),
            "drawn_metrics": full_metrics,
            "status": full_status,
            "symbols": full_pool,
        },
        "thresholds": pool_rules,
    }
    pool_status_path = run_dir / "pool_status.json"
    pool_status_path.write_text(json.dumps(pool_report, indent=2), encoding="utf-8")

    print(f"wrote {out_path} baselines={len(rows)}")
    print(f"wrote {pool_status_path}")
    print(f"candidate_pool drawn metrics: {cand_metrics}, status={cand_status}")
    print(f"full_pool drawn metrics: {full_metrics}, status={full_status}")


if __name__ == "__main__":
    main()



