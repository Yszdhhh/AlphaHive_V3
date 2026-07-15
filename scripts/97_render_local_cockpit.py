"""Render local candidate CSV rows as a static, non-sending cockpit page."""
from __future__ import annotations

import argparse
import csv
import html
from pathlib import Path


SAFE_FIELDS = ("record_id", "symbol", "scan_time_utc", "history_tier", "eligible_for_paper", "trigger_reason")


def render_local_cockpit(input_csv: Path, output_html: Path) -> int:
    """Read a local candidate CSV and write static cards without network behavior."""
    with input_csv.open("r", encoding="utf-8-sig", newline="") as handle:
        rows = list(csv.DictReader(handle))
    cards = []
    for row in rows:
        values = "".join(
            f"<li><b>{html.escape(field)}</b>: {html.escape(str(row.get(field, '')))}</li>"
            for field in SAFE_FIELDS
        )
        cards.append(f"<article class=\"card\"><ul>{values}</ul></article>")
    page = "\n".join((
        "<!doctype html>",
        "<html><head><meta charset=\"utf-8\"><title>AlphaHive local cockpit</title>",
        "<style>body{background:#111;color:#eee;font-family:system-ui;margin:2rem}.card{border:1px solid #555;margin:1rem 0;padding:1rem}li{margin:.3rem 0}</style>",
        "</head><body><h1>AlphaHive local cockpit</h1>",
        f"<p>source: {html.escape(str(input_csv))}</p><p>send_enabled=false; no network calls.</p>",
        *cards,
        "</body></html>",
    ))
    output_html.write_text(page, encoding="utf-8")
    return len(rows)


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--input", required=True, type=Path)
    parser.add_argument("--output", required=True, type=Path)
    args = parser.parse_args()
    print(f"rendered_cards={render_local_cockpit(args.input, args.output)}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
