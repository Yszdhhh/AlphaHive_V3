"""Regression tests for 02_scan_anomalies cvd cooldown (Phase 4 接入).

锁住 _in_cooldown 的方向语义：只对晚于（或等于）已记录时点的扫描计冷却，
回拨更早的历史查询不受未来记录约束；非 cvd 行 / 缺失 ledger 不误伤。
"""
from __future__ import annotations

import importlib.util
import sys
from pathlib import Path

import pytest

PROJECT_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(PROJECT_ROOT))
SPEC_PATH = PROJECT_ROOT / "scripts" / "02_scan_anomalies.py"


@pytest.fixture
def mod():
    spec = importlib.util.spec_from_file_location("scan02_mod", SPEC_PATH)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


def _ledger(tmp_path, rows: list[str]) -> Path:
    p = tmp_path / "Anomaly_Ledger.csv"
    p.write_text(
        "scan_time_utc,symbol,trigger_reason,decision\n" + "\n".join(rows) + "\n",
        encoding="utf-8",
    )
    return p


def test_cooldown_direction(tmp_path, mod, monkeypatch):
    ledger = _ledger(tmp_path, [
        "2026-05-13T19:00:00+00:00,ONDOUSDT,cvd_bear_divergence|vol_quantile_high,AutoSkipped",
    ])
    monkeypatch.setattr(mod, "LEDGER_PATH", ledger)
    assert mod._in_cooldown("ONDOUSDT", "2026-05-13T19:00:00Z", 48.0) is True   # 同刻
    assert mod._in_cooldown("ONDOUSDT", "2026-05-10T19:00:00Z", 48.0) is False  # 早于记录，不受未来约束
    assert mod._in_cooldown("ONDOUSDT", "2026-05-14T19:00:00Z", 48.0) is True   # 1d 后，仍 <48h
    assert mod._in_cooldown("ONDOUSDT", "2026-05-15T19:00:00Z", 48.0) is False  # 2d 后，已过 48h
    assert mod._in_cooldown("SUIUSDT", "2026-05-13T19:00:00Z", 48.0) is False   # 其他 symbol


def test_cooldown_missing_ledger(mod, monkeypatch, tmp_path):
    monkeypatch.setattr(mod, "LEDGER_PATH", tmp_path / "nope.csv")
    assert mod._in_cooldown("ONDOUSDT", "2026-05-13T19:00:00Z", 48.0) is False


def test_cooldown_non_cvd_row_ignored(mod, monkeypatch, tmp_path):
    ledger = _ledger(tmp_path, [
        "2026-05-13T19:00:00+00:00,ONDOUSDT,vol_quantile_high,",
    ])
    monkeypatch.setattr(mod, "LEDGER_PATH", ledger)
    assert mod._in_cooldown("ONDOUSDT", "2026-05-13T19:00:00Z", 48.0) is False


def test_cooldown_bad_timestamp_not_fatal(mod, monkeypatch, tmp_path):
    ledger = _ledger(tmp_path, [
        "not-a-timestamp,ONDOUSDT,cvd_bear_divergence,",
    ])
    monkeypatch.setattr(mod, "LEDGER_PATH", ledger)
    assert mod._in_cooldown("ONDOUSDT", "2026-05-13T19:00:00Z", 48.0) is False
