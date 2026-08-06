from harness.lib.candidate_research_job_bridge import preview_research_job_creation


def _run(**overrides):
    run = {
        "run_id": "prospective_001",
        "mode": "PROSPECTIVE_LIVE",
        "registry_status": "clean",
        "registry_eligible_for_judgment": True,
        "scan_time_utc": "2026-07-19T08:00:00+00:00",
        "last_completed_bar_utc": "2026-07-19T08:00:00+00:00",
        "integrity": {"no_lookahead_attested": True},
    }
    run.update(overrides)
    return run


def _candidate(**overrides):
    candidate = {"record_id": "prospective_001_0001", "symbol": "SOLUSDT", "quality_status": "WARN", "decision": "", "direction": ""}
    candidate.update(overrides)
    return candidate


def test_fresh_live_candidate_generates_only_a_creation_preview():
    result = preview_research_job_creation(_candidate(), _run(), now_utc="2026-07-19T09:00:00+00:00")
    assert result["verdict"] == "READY"
    assert result["create_request_draft"] == {"record_id": "prospective_001_0001"}
    package = result["candidate_package_preview"]
    assert package["paper_plan_capability"] == "BLOCK"
    assert package["performance_eligible"] is False
    assert "no_job_directory_write" in result["hard_exclusions"]


def test_historical_stale_blocked_or_directional_candidate_is_parked():
    result = preview_research_job_creation(
        _candidate(quality_status="BLOCK", direction="LONG"),
        _run(mode="HISTORICAL_REPLAY", last_completed_bar_utc="2026-07-16T08:00:00+00:00"),
        now_utc="2026-07-19T09:00:00+00:00",
    )
    assert result["verdict"] == "PARK"
    assert result["create_request_draft"] is None
    assert {"not_prospective_live", "completed_bar_stale", "quality_blocked", "candidate_contains_decision_or_direction"} <= set(result["blockers"])


def test_invalid_candidate_or_run_shape_fails_closed_to_park():
    result = preview_research_job_creation([], {"integrity": "not-an-object"}, now_utc="2026-07-19T09:00:00+00:00")
    assert result["verdict"] == "PARK"
    assert {"candidate_invalid", "record_id_missing", "symbol_missing", "run_not_registry_authorized", "no_lookahead_not_attested"} <= set(result["blockers"])
