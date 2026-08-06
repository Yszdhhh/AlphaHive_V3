import json
from pathlib import Path

import pytest

from harness.lib.local_paper_plan_ledger import (
    LocalPaperPlanLedgerError,
    publish_local_paper_plan,
    validate_local_paper_plan_ledger,
)
from harness.lib.paper_plan_engine import build_paper_plan, content_hash


FIXTURES = Path(__file__).parents[1] / "fixtures"


def _plan():
    data = json.loads((FIXTURES / "paper_allow.json").read_text(encoding="utf-8"))
    return build_paper_plan(data["job"], data["owner_decision"], data["preset"], data["bars"])


def test_local_ledger_is_immutable_and_idempotent(tmp_path: Path) -> None:
    first = publish_local_paper_plan(tmp_path, _plan())
    second = publish_local_paper_plan(tmp_path, _plan())
    assert first == {"status": "ACCEPTED", "version": "v0001", "plan_file": "plans/v0001.json", "idempotent_replay": False}
    assert second["idempotent_replay"] is True
    assert validate_local_paper_plan_ledger(tmp_path) is True


def test_local_ledger_rejects_second_active_or_tampered_plan(tmp_path: Path) -> None:
    plan = _plan()
    publish_local_paper_plan(tmp_path, plan)
    changed = dict(plan)
    changed["direction"] = "SHORT"
    changed["plan_id"] = "plan_other"
    changed["artifact_hash"] = content_hash({key: value for key, value in changed.items() if key != "artifact_hash"})
    with pytest.raises(LocalPaperPlanLedgerError) as exc:
        publish_local_paper_plan(tmp_path, changed)
    assert exc.value.code == "active_plan_exists"
    path = tmp_path / "plans" / "v0001.json"
    path.write_text(path.read_text(encoding="utf-8").replace("LONG", "SHORT", 1), encoding="utf-8")
    assert validate_local_paper_plan_ledger(tmp_path) is False
