import json
from pathlib import Path

import pytest

from harness.lib.paper_plan_engine import PaperPlanRejected, build_paper_plan, export_research_job_prompt, preset_hash


FIXTURES = Path(__file__).parents[1] / "fixtures"


def _fixture(name="paper_allow.json"):
    return json.loads((FIXTURES / name).read_text(encoding="utf-8"))


def test_synthetic_allow_plan_is_deterministic_and_bound():
    data = _fixture()
    assert data["owner_decision"]["selected_preset_hash"] == preset_hash(data["preset"])
    first = build_paper_plan(data["job"], data["owner_decision"], data["preset"], data["bars"])
    second = build_paper_plan(data["job"], data["owner_decision"], data["preset"], data["bars"])
    assert first == second
    assert first["schema_version"] == "paper_plan_v1"
    assert first["no_live_order_path"] is True
    assert first["entry_anchor_timestamp_utc"] == "2026-07-01T00:00:00+00:00"


def test_prompt_export_is_local_provider_neutral_and_deterministic():
    package = {"job_id": "job_11111111-1111-4111-8111-111111111111", "schema_version": "deep_research_prompt_package_v1", "rendered_prompt": "fact-only"}
    first = export_research_job_prompt(package["job_id"], package)
    second = export_research_job_prompt(package["job_id"], package)
    assert first == second
    assert first["provider_neutral"] is True
    assert first["provider_calls"] is False
    assert first["artifact_hash"]


def test_prompt_export_rejects_cross_job_binding():
    with pytest.raises(PaperPlanRejected) as exc:
        export_research_job_prompt("job_11111111-1111-4111-8111-111111111111", {"job_id": "job_22222222-2222-4222-8222-222222222222"})
    assert exc.value.code == "prompt_job_binding_mismatch"


def test_historical_bonk_fixture_fails_closed():
    data = _fixture("paper_bonk_block.json")
    with pytest.raises(PaperPlanRejected) as exc:
        build_paper_plan(data["job"], data["owner_decision"], data["preset"], data["bars"])
    assert exc.value.code == "historical_mode_blocked"


@pytest.mark.parametrize("mutation,code", [
    (lambda d: d["job"].update({"mode": "PROSPECTIVE_LIVE", "capabilities": {"paper_plan_capability": "BLOCK"}}), "paper_capability_blocked"),
    (lambda d: d["owner_decision"].update({"owner_authenticated": False}), "owner_authentication_required"),
    (lambda d: d["owner_decision"].update({"selected_preset_hash": "f" * 64}), "preset_hash_mismatch"),
    (lambda d: d["preset"].update({"status": "DRAFT"}), "preset_not_approved"),
])
def test_plan_rejects_unsafe_inputs(mutation, code):
    data = _fixture()
    mutation(data)
    with pytest.raises(PaperPlanRejected) as exc:
        build_paper_plan(data["job"], data["owner_decision"], data["preset"], data["bars"])
    assert exc.value.code == code
