"""Local-only proof that the three new infrastructure boundaries compose."""
import json
from pathlib import Path

from harness.lib.candidate_research_job_bridge import preview_research_job_creation
from harness.lib.local_notification_outbox import enqueue_local_notification, process_one_local_notification
from harness.lib.local_paper_plan_ledger import publish_local_paper_plan
from harness.lib.offline_execution_simulator import run_simulation
from harness.lib.paper_plan_engine import build_paper_plan


FIXTURES = Path(__file__).parents[1] / "fixtures"


def test_local_workflow_remains_preview_simulation_and_dry_run_only(tmp_path: Path) -> None:
    preview = preview_research_job_creation(
        {"record_id": "prospective_001_0001", "symbol": "SOLUSDT", "quality_status": "WARN", "decision": "", "direction": ""},
        {
            "run_id": "prospective_001", "mode": "PROSPECTIVE_LIVE", "registry_status": "clean",
            "registry_eligible_for_judgment": True, "scan_time_utc": "2026-07-19T08:00:00+00:00",
            "last_completed_bar_utc": "2026-07-19T08:00:00+00:00", "integrity": {"no_lookahead_attested": True},
        },
        now_utc="2026-07-19T09:00:00+00:00",
    )
    assert preview["verdict"] == "READY"
    assert preview["candidate_package_preview"]["paper_plan_capability"] == "BLOCK"

    fixture = json.loads((FIXTURES / "paper_allow.json").read_text(encoding="utf-8"))
    plan = build_paper_plan(fixture["job"], fixture["owner_decision"], fixture["preset"], fixture["bars"])
    published = publish_local_paper_plan(tmp_path / "paper_ledger", plan)
    simulation = run_simulation(plan, fixture["bars"], ledger_path=tmp_path / "simulation_events.jsonl")
    event = json.loads((tmp_path / "paper_ledger" / "events.jsonl").read_text(encoding="utf-8"))
    queued = enqueue_local_notification(tmp_path / "outbox", {"event_id": event["event_id"], "event_type": event["event_type"], "payload": {"plan_id": plan["plan_id"]}})
    delivered = process_one_local_notification(tmp_path / "outbox")

    assert published["idempotent_replay"] is False
    assert simulation["exit_reason"] == "TARGETS_COMPLETE"
    assert queued["idempotent_replay"] is False
    assert delivered["delivery_mode"] == "DRY_RUN_NO_NETWORK"
