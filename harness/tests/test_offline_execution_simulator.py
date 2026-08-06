import json
from pathlib import Path

import pytest

from harness.lib.offline_execution_simulator import SimulationRejected, run_simulation
from harness.lib.paper_plan_engine import build_paper_plan, content_hash


FIXTURES = Path(__file__).parents[1] / "fixtures"


def _plan():
    data = json.loads((FIXTURES / "paper_allow.json").read_text(encoding="utf-8"))
    return build_paper_plan(data["job"], data["owner_decision"], data["preset"], data["bars"]), data["bars"]


def test_simulator_has_deterministic_targets_and_pnl(tmp_path):
    plan, bars = _plan()
    ledger = tmp_path / "events.jsonl"
    first = run_simulation(plan, bars, ledger_path=ledger)
    second = run_simulation(plan, bars, ledger_path=ledger)
    assert first["idempotent_replay"] is False
    assert second["idempotent_replay"] is True
    assert first["simulation_id"] == second["simulation_id"]
    assert first["exit_reason"] == "TARGETS_COMPLETE"
    assert len(first["fills"]) == 3
    assert first["realized_pnl"] > 0
    assert len(ledger.read_text(encoding="utf-8").splitlines()) == len(first["events"])


def test_same_bar_stop_wins_over_target():
    plan, _ = _plan()
    plan["take_profit_targets"] = [{"r_multiple": 1.0, "exit_weight_pct": 100}]
    plan["artifact_hash"] = content_hash({key: value for key, value in plan.items() if key != "artifact_hash"})
    bars = [
        {"timestamp": "2026-07-01T00:00:00Z", "open": 100.0, "high": 101.5, "low": 98.5, "close": 100.0},
    ]
    result = run_simulation(plan, bars)
    assert result["exit_reason"] == "STOP"
    assert result["fills"][-1]["type"] == "STOP"


def test_simulator_rejects_live_order_plan():
    plan, bars = _plan()
    plan["no_live_order_path"] = False
    with pytest.raises(SimulationRejected) as exc:
        run_simulation(plan, bars)
    assert exc.value.code == "invalid_or_live_plan"


def test_simulator_rejects_tampered_plan():
    plan, bars = _plan()
    plan["stop_distance_pct"] = 9.0
    with pytest.raises(SimulationRejected) as exc:
        run_simulation(plan, bars)
    assert exc.value.code == "plan_hash_mismatch"
