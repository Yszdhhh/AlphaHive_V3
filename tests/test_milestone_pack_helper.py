"""M-C1 safety regressions for the local milestone package helper."""
from __future__ import annotations

import importlib.util
from pathlib import Path

import pytest


PROJECT_ROOT = Path(__file__).resolve().parents[1]
HELPER_PATH = PROJECT_ROOT / "scripts" / "98_milestone_pack_helper.py"


def _helper():
    spec = importlib.util.spec_from_file_location("milestone_pack_helper", HELPER_PATH)
    assert spec and spec.loader
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def test_create_requires_fresh_direct_desktop_package(tmp_path: Path) -> None:
    helper = _helper()
    desktop = tmp_path / "Desktop"
    desktop.mkdir()
    output = desktop / "AlphaHive_V3_C_M-C1_deliverables"

    helper.create_package(output, "C_M-C1", desktop=desktop)

    assert (output / "C_M-C1_DELIVERABLE.md").is_file()
    assert all((output / name).is_dir() for name in helper.REQUIRED_DIRS)
    with pytest.raises(FileExistsError):
        helper.create_package(output, "C_M-C1", desktop=desktop)
    with pytest.raises(ValueError):
        helper.create_package(desktop / "nested" / "AlphaHive_V3_bad_deliverables", "bad", desktop=desktop)


def test_validation_rejects_template_and_accepts_evidence_package(tmp_path: Path) -> None:
    helper = _helper()
    desktop = tmp_path / "Desktop"
    desktop.mkdir()
    output = helper.create_package(desktop / "AlphaHive_V3_C_M-C1_deliverables", "C_M-C1", desktop=desktop)
    deliverable = output / "C_M-C1_DELIVERABLE.md"

    assert helper.validate_package(output, deliverable)
    document = "# Deliverable\n\n" + "\n\n".join(
        f"## {index}. {title}\n\nverified evidence" for index, title in enumerate(helper.SECTIONS, start=1)
    )
    deliverable.write_text(document, encoding="utf-8")
    (output / "reports" / "OWNER_DECISIONS_NEEDED.md").write_text("PARK preserved", encoding="utf-8")
    (output / "regression" / "pytest.txt").write_text("1 passed", encoding="utf-8")
    (output / "commit_diffs" / "change.patch").write_text("commit abc\ndiff --git a/x b/x", encoding="utf-8")

    assert helper.validate_package(output, deliverable) == []


def test_legacy_inspection_accepts_a_nested_standard_package(tmp_path: Path) -> None:
    helper = _helper()
    nested = tmp_path / "outer" / "AlphaHive_V3_F21_DELIVERABLE"
    (nested / "reports").mkdir(parents=True)
    (nested / "commit_diffs").mkdir()
    (nested / "regression").mkdir()
    (nested / "reports" / "OWNER_DECISIONS_NEEDED.md").write_text("PARK", encoding="utf-8")

    assert helper.inspect_legacy_package(nested.parent) == "PASS"
