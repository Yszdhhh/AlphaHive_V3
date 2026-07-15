from __future__ import annotations

import importlib.util
from pathlib import Path


PROJECT_ROOT = Path(__file__).resolve().parents[1]


def _renderer():
    spec = importlib.util.spec_from_file_location("render_local_cockpit", PROJECT_ROOT / "scripts" / "97_render_local_cockpit.py")
    assert spec and spec.loader
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def test_renderer_reads_local_candidate_csv_without_network_behavior(tmp_path: Path) -> None:
    source = tmp_path / "candidates.csv"
    source.write_text(
        "record_id,symbol,scan_time_utc,history_tier,eligible_for_paper,trigger_reason\n"
        "r-1,ETHUSDT,2026-07-15T00:00:00Z,Full,yes,large_move_abs\n",
        encoding="utf-8",
    )
    output = tmp_path / "cockpit.html"

    assert _renderer().render_local_cockpit(source, output) == 1

    page = output.read_text(encoding="utf-8")
    assert "ETHUSDT" in page
    assert "send_enabled=false" in page
    assert "fetch(" not in page
    assert "http" not in page.lower()
