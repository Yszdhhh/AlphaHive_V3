"""P0 engineering and research-validity gates for AlphaHive V3."""
from __future__ import annotations

import argparse
import hashlib
import json
import sys
from datetime import datetime, timezone
from pathlib import Path

import pandas as pd
import yaml

PROJECT_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(PROJECT_ROOT))

from harness.lib.baseline_pool import pool_diversity, pool_status
from harness.lib.funding_normalize import assert_normalized_funding
from harness.lib.run_registry import run_entry, run_status

LEDGER_DIR = PROJECT_ROOT / "ledger"
RUNS_DIR = PROJECT_ROOT / "harness" / "runs"
REPORTS_DIR = PROJECT_ROOT / "reports"
CONFIG_DIR = PROJECT_ROOT / "config"
ANOMALY_LEDGER = LEDGER_DIR / "Anomaly_Ledger.csv"
BASELINE_LEDGER = LEDGER_DIR / "Baseline_Ledger.csv"


def load_yaml(path: Path) -> dict:
    with path.open("r", encoding="utf-8") as f:
        return yaml.safe_load(f)


def sha256_file(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as f:
        for chunk in iter(lambda: f.read(1024 * 1024), b""):
            h.update(chunk)
    return h.hexdigest()


def latest_run_id() -> str:
    runs = sorted([p.name for p in RUNS_DIR.iterdir() if p.is_dir()])
    if not runs:
        raise SystemExit("No runs found")
    return runs[-1]


def add(result: list[dict], gate: str, status: str, detail: str) -> None:
    result.append({"gate": gate, "status": status, "detail": detail})


def check_registry(run_id: str, results: list[dict]) -> None:
    status = run_status(run_id)
    if status == "clean":
        add(results, "G1 run_registry", "PASS", f"{run_id} is clean")
    elif status == "unregistered":
        add(results, "G1 run_registry", "FAIL", f"{run_id} is not registered")
    else:
        add(results, "G1 run_registry", "FAIL", f"{run_id} status={status}; not eligible")


def check_hashes(run_id: str, results: list[dict]) -> None:
    run_dir = RUNS_DIR / run_id
    manifest_path = run_dir / "run_manifest.json"
    if not manifest_path.exists():
        add(results, "G5 snapshot hash", "FAIL", "run_manifest.json missing")
        return
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    snapshot = run_dir / "input_snapshot.csv"
    expected = manifest.get("snapshot_sha256") or manifest.get("input_snapshot_sha256")
    if not snapshot.exists() or not expected:
        add(results, "G5 snapshot hash", "FAIL", "snapshot or manifest hash missing")
    else:
        actual = sha256_file(snapshot)
        add(results, "G5 snapshot hash", "PASS" if actual == expected else "FAIL", f"snapshot hash {'matched' if actual == expected else 'mismatch'}")
    tape = manifest.get("return_tape_path")
    tape_hash = manifest.get("return_tape_sha256")
    if tape:
        tape_path = Path(tape)
        if not tape_path.exists() or sha256_file(tape_path) != tape_hash:
            add(results, "G5 return tape hash", "FAIL", "return tape hash mismatch or missing")
        else:
            try:
                tape_df = pd.read_csv(tape_path)
                if tape_df.empty:
                    add(results, "G5 return tape hash", "FAIL", "return tape hash matched but tape is empty")
                else:
                    add(results, "G5 return tape hash", "PASS", f"return tape hash matched rows={len(tape_df)} symbols={tape_df['symbol'].nunique() if 'symbol' in tape_df.columns else 'unknown'}")
            except Exception as exc:
                add(results, "G5 return tape hash", "FAIL", f"return tape unreadable: {exc}")
    else:
        add(results, "G5 return tape hash", "WARN", "return tape pending")


def check_funding_contract(
    run_id: str,
    anomaly: pd.DataFrame,
    results: list[dict],
    derivative_use_mode: str | None = None,
) -> None:
    try:
        rates = pd.to_numeric(anomaly["funding_rate_8h"], errors="coerce").dropna()
        if derivative_use_mode == "LIVE_DISABLED":
            # Prospective runs keep derivatives dormant until the Owner ignites
            # them; funding values appearing here would violate that boundary.
            if rates.empty:
                add(results, "G4 funding contract", "PASS", "funding dormant by design: derivative_use_mode=LIVE_DISABLED")
            else:
                add(results, "G4 funding contract", "FAIL", f"{len(rates)} funding samples present despite LIVE_DISABLED")
            return
        if rates.empty:
            add(results, "G4 funding contract", "FAIL", "no funding samples in anomaly rows")
            return
        assert_normalized_funding(rates)
        add(results, "G4 funding contract", "PASS", f"{len(rates)} ledger samples are decimal-normalized")
    except Exception as exc:
        add(results, "G4 funding contract", "FAIL", str(exc))


def check_pool(run_id: str, baseline_run: pd.DataFrame, results: list[dict]) -> None:
    pool_path = RUNS_DIR / run_id / "pool_status.json"
    if pool_path.exists():
        report = json.loads(pool_path.read_text(encoding="utf-8"))
        candidate = report.get("candidate_pool", {})
        metrics = candidate.get("drawn_metrics", {})
        status = candidate.get("status", "missing")
        detail = (
            f"source_unique={candidate.get('source_unique_symbols')}, "
            f"drawn_unique={metrics.get('unique')}, "
            f"max_share={float(metrics.get('max_share', 0.0)):.3f}, "
            f"entropy={float(metrics.get('entropy_ratio', 0.0)):.3f}, status={status}"
        )
        add(results, "G2 candidate pool diversity", "PASS" if status == "ok" else "FAIL", detail)
        return

    rules = load_yaml(CONFIG_DIR / "scan_rules.yaml").get("baseline_pool", {})
    cp = baseline_run[baseline_run["baseline_type"] == "candidate_pool_random"]
    if cp.empty:
        add(results, "G2 candidate pool diversity", "FAIL", "candidate_pool_random rows missing and pool_status.json missing")
        return
    symbols = cp["symbol"].dropna().astype(str).tolist()
    metrics = pool_diversity(symbols)
    status = pool_status(metrics, rules)
    detail = f"pool_status.json missing; fallback unique={metrics['unique']}, max_share={metrics['max_share']:.3f}, entropy={metrics['entropy_ratio']:.3f}, status={status}"
    add(results, "G2 candidate pool diversity", "PASS" if status == "ok" else "FAIL", detail)


def check_baseline_friction(baseline: pd.DataFrame, results: list[dict]) -> None:
    bad = baseline[pd.to_numeric(baseline["friction_bps_roundtrip"], errors="coerce").isna() | (pd.to_numeric(baseline["friction_bps_roundtrip"], errors="coerce") <= 0)]
    add(results, "G3 baseline friction", "PASS" if bad.empty else "FAIL", f"bad={len(bad)} / {len(baseline)}")


def check_autoskip(anomaly: pd.DataFrame, results: list[dict]) -> None:
    completed_cols = [c for c in ["dir_excess_ret_net_4h", "dir_excess_ret_net_24h"] if c in anomaly.columns]
    if not completed_cols:
        add(results, "G6 AutoSkipped excluded", "WARN", "no completed return columns present")
        return
    autos = anomaly[anomaly["decision"] == "AutoSkipped"]
    bad_sign = int((pd.to_numeric(autos.get("direction_sign", 0), errors="coerce").fillna(0) != 0).sum()) if not autos.empty else 0
    nonzero_returns = 0
    for col in completed_cols:
        vals = pd.to_numeric(autos[col], errors="coerce").fillna(0)
        nonzero_returns += int((vals.abs() > 1e-12).sum())
    status = "PASS" if bad_sign == 0 and nonzero_returns == 0 else "FAIL"
    add(results, "G6 AutoSkipped excluded", status, f"autos={len(autos)}, bad_sign={bad_sign}, nonzero_completed_returns={nonzero_returns}")


def check_entry_no_lookahead(anomaly: pd.DataFrame, baseline: pd.DataFrame, results: list[dict]) -> None:
    issues = 0
    for df in [anomaly, baseline]:
        if "entry_timestamp" not in df.columns:
            continue
        rows = df[df["entry_timestamp"].notna()]
        if rows.empty:
            continue
        entry_ts = pd.to_datetime(rows["entry_timestamp"], utc=True, errors="coerce")
        scan_ts = pd.to_datetime(rows["scan_time_utc"], utc=True, errors="coerce")
        issues += int((entry_ts <= scan_ts).sum())
    if issues == 0:
        add(results, "G7 entry after scan", "PASS", "no scan-before entry detected; timestamp columns absent or clean")
    else:
        add(results, "G7 entry after scan", "FAIL", f"{issues} entries <= scan_time")


def check_static_code(results: list[dict]) -> None:
    scripts = [PROJECT_ROOT / "scripts" / name for name in ["02_scan_anomalies.py", "03_generate_baselines.py", "04_calc_friction.py", "05_update_returns.py", "99_validate_schema.py"]]
    offenders = []
    for path in scripts:
        text = path.read_text(encoding="utf-8")
        if "/ 100" in text or "/100" in text:
            if path.name != "99_validate_schema.py" and "funding_normalize" not in str(path):
                offenders.append(path.name)
    add(results, "S1 no scattered funding /100", "PASS" if not offenders else "FAIL", f"offenders={offenders}")

    turnover_offenders = []
    for path in [PROJECT_ROOT / "scripts" / "03_generate_baselines.py", PROJECT_ROOT / "scripts" / "04_calc_friction.py"]:
        text = path.read_text(encoding="utf-8")
        if "tail(24)" in text or "dropna(subset=[\"turnover_usd\"])" in text:
            turnover_offenders.append(path.name)
    add(results, "S2 no local turnover recalc", "PASS" if not turnover_offenders else "FAIL", f"offenders={turnover_offenders}")


def write_report(run_id: str, results: list[dict]) -> Path:
    timestamp = datetime.now(timezone.utc).strftime("%Y%m%d_%H%M_utc")
    REPORTS_DIR.mkdir(parents=True, exist_ok=True)
    path = REPORTS_DIR / f"research_gate_{run_id}_{timestamp}.md"
    lines = [
        f"# AlphaHive V3 Research Gate Report",
        "",
        f"Generated: {timestamp}",
        f"Run: {run_id}",
        "",
        "| Gate | Status | Detail |",
        "|---|---|---|",
    ]
    for row in results:
        lines.append(f"| {row['gate']} | {row['status']} | {row['detail']} |")
    fails = [r for r in results if r["status"] == "FAIL"]
    lines += ["", f"Result: {'FAIL' if fails else 'PASS'}"]
    path.write_text("\n".join(lines), encoding="utf-8")
    return path


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--run_id", default=None)
    args = parser.parse_args()
    run_id = args.run_id or latest_run_id()

    anomaly_all = pd.read_csv(ANOMALY_LEDGER)
    baseline_all = pd.read_csv(BASELINE_LEDGER)
    anomaly = anomaly_all[anomaly_all["run_id"] == run_id].copy()
    baseline = baseline_all[baseline_all["run_id"] == run_id].copy()
    baseline_run_path = RUNS_DIR / run_id / "baselines.csv"
    baseline_run = pd.read_csv(baseline_run_path) if baseline_run_path.exists() else baseline.copy()

    results = []
    if anomaly.empty:
        add(results, "DATA anomaly rows", "FAIL", f"no anomaly rows for {run_id}")
    if baseline.empty:
        add(results, "DATA baseline rows", "FAIL", f"no baseline rows for {run_id}")

    manifest_path = RUNS_DIR / run_id / "run_manifest.json"
    derivative_use_mode = None
    if manifest_path.exists():
        derivative_use_mode = json.loads(manifest_path.read_text(encoding="utf-8")).get("derivative_use_mode")

    check_registry(run_id, results)
    check_hashes(run_id, results)
    if not anomaly.empty:
        check_funding_contract(run_id, anomaly, results, derivative_use_mode)
        check_autoskip(anomaly, results)
    if not baseline.empty:
        check_baseline_friction(baseline, results)
        check_pool(run_id, baseline_run, results)
        check_entry_no_lookahead(anomaly, baseline, results)
    check_static_code(results)

    report = write_report(run_id, results)
    print(f"Report written to: {report}")
    for row in results:
        print(f"{row['status']:5} {row['gate']}: {row['detail']}")
    if any(r["status"] == "FAIL" for r in results):
        raise SystemExit(1)


if __name__ == "__main__":
    main()







