"""Apply red-team decisions from the pending-top markdown report.

This updates only decision metadata in Anomaly_Ledger.csv. It never assigns
Long/Short direction; Paper Trade directions remain pending human review.
"""
from __future__ import annotations

import argparse
import csv
import re
from datetime import datetime, timezone
from pathlib import Path

import pandas as pd

PROJECT_ROOT = Path(__file__).resolve().parents[1]
ANOMALY_LEDGER = PROJECT_ROOT / "ledger" / "Anomaly_Ledger.csv"
DEFAULT_REPORT = PROJECT_ROOT / "reports" / "red_team_decisions_pending_top_20260708.md"

VALID_DECISIONS = {"No Trade", "Watch", "Paper Trade"}


def split_markdown_row(line: str) -> list[str]:
    cells = []
    current = []
    escaped = False
    body = line.strip().strip("|")
    for ch in body:
        if escaped:
            current.append(ch)
            escaped = False
        elif ch == "\\":
            current.append(ch)
            escaped = True
        elif ch == "|":
            cells.append("".join(current).strip())
            current = []
        else:
            current.append(ch)
    cells.append("".join(current).strip())
    return cells


def clean_md(text: str) -> str:
    return re.sub(r"\*\*|`", "", text).strip()


def parse_decisions(report_path: Path) -> list[dict]:
    rows = []
    in_table = False
    for raw in report_path.read_text(encoding="utf-8").splitlines():
        line = raw.strip()
        if line.startswith("| # | run_id | record_id |"):
            in_table = True
            continue
        if not in_table:
            continue
        if line.startswith("|---"):
            continue
        if not line.startswith("|"):
            if rows:
                break
            continue
        cells = split_markdown_row(line)
        if len(cells) < 18:
            continue
        decision = clean_md(cells[13])
        if decision not in VALID_DECISIONS:
            continue
        rows.append({
            "run_id": clean_md(cells[1]),
            "record_id_suffix": clean_md(cells[2]),
            "symbol": clean_md(cells[4]),
            "decision": decision,
            "confidence": clean_md(cells[14]),
            "reason_short": clean_md(cells[15]),
            "required_human_check": clean_md(cells[16]),
            "veto_flags": clean_md(cells[17]),
        })
    return rows


def apply(report_path: Path, dry_run: bool = False) -> pd.DataFrame:
    decisions = parse_decisions(report_path)
    if len(decisions) != 20:
        raise SystemExit(f"Expected 20 decisions, parsed {len(decisions)}")

    ledger = pd.read_csv(ANOMALY_LEDGER, dtype=str, keep_default_na=False)
    now = datetime.now(timezone.utc).isoformat()
    ref = str(report_path)
    updates = []

    for item in decisions:
        suffix = item["record_id_suffix"]
        full_record_id = suffix if suffix.startswith(item["run_id"]) else f"{item['run_id']}{suffix}"
        mask = (ledger["run_id"] == item["run_id"]) & (ledger["record_id"] == full_record_id)
        if int(mask.sum()) != 1:
            raise SystemExit(f"Could not uniquely match {item['run_id']} {suffix} -> {full_record_id}; matches={int(mask.sum())}")
        row = ledger[mask].iloc[0]
        if row["symbol"] != item["symbol"]:
            raise SystemExit(f"Symbol mismatch for {full_record_id}: ledger={row['symbol']} report={item['symbol']}")
        if str(row.get("is_top_candidate", "")).lower() != "true":
            raise SystemExit(f"Record is not top candidate: {full_record_id}")
        idx = ledger.index[mask][0]
        updates.append({"record_id": full_record_id, **item})
        if not dry_run:
            ledger.at[idx, "decision"] = item["decision"]
            ledger.at[idx, "red_team_ref"] = ref
            ledger.at[idx, "decision_time_utc"] = now
            note = (
                f"red_team_decision={item['decision']}; confidence={item['confidence']}; "
                f"reason={item['reason_short']}; human_check={item['required_human_check']}; "
                f"veto_flags={item['veto_flags']}"
            )
            ledger.at[idx, "notes"] = note

    if not dry_run:
        ledger.to_csv(ANOMALY_LEDGER, index=False, quoting=csv.QUOTE_MINIMAL)
    return pd.DataFrame(updates)


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--report", default=str(DEFAULT_REPORT))
    parser.add_argument("--dry-run", action="store_true")
    args = parser.parse_args()
    updated = apply(Path(args.report), dry_run=args.dry_run)
    print(f"parsed/applied decisions: {len(updated)} dry_run={args.dry_run}")
    print(updated[["run_id", "record_id", "symbol", "decision", "confidence", "veto_flags"]].to_string(index=False))


if __name__ == "__main__":
    main()
