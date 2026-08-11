"""199_data_health 周末豁免逻辑（美股/期货周末无数据属预期，非故障）。"""
import importlib.util
import sys
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
spec = importlib.util.spec_from_file_location(
    "dh", ROOT / "scripts" / "199_data_health.py")
dh = importlib.util.module_from_spec(spec)
sys.modules["dh"] = dh
spec.loader.exec_module(dh)


def test_weekend_exempt_friday_lastbar_saturday():
    """周五最后 bar + 周六检查 → 豁免（cme 期货周末无交易）。"""
    last = "2026-08-07 00:00"  # 周五
    now = datetime(2026, 8, 8, 12, 0, tzinfo=timezone.utc)  # 周六
    assert dh._weekend_exempt("cme_bitcoin", last, now)


def test_weekend_exempt_friday_lastbar_monday():
    """周五最后 bar + 周一晨检查 → 豁免（周末数据未到仍属预期）。"""
    last = "2026-08-07 00:00"  # 周五
    now = datetime(2026, 8, 10, 6, 0, tzinfo=timezone.utc)  # 周一
    assert dh._weekend_exempt("cme_bitcoin", last, now)


def test_weekend_exempt_not_friday_lastbar():
    """最后 bar 非周五（如周三）→ 不豁免，仍算过期。"""
    last = "2026-08-05 00:00"  # 周三
    now = datetime(2026, 8, 8, 12, 0, tzinfo=timezone.utc)  # 周六
    assert not dh._weekend_exempt("cme_bitcoin", last, now)


def test_weekend_exempt_friday_now_friday():
    """周五当天检查：最后 bar 周五但数据确实老于阈值 → 不豁免（当天拉取应已更新）。"""
    last = "2026-08-07 00:00"
    now = datetime(2026, 8, 7, 12, 0, tzinfo=timezone.utc)  # 周五
    assert not dh._weekend_exempt("cme_bitcoin", last, now)


def test_weekend_exempt_scope():
    """豁免仅限 WEEKEND_SOURCES（币安 klines 不受周末豁免）。"""
    last = "2026-08-07 00:00"
    now = datetime(2026, 8, 8, 12, 0, tzinfo=timezone.utc)
    assert not dh._weekend_exempt("binance_klines", last, now)


def test_weekend_exempt_missing_last():
    """无 last 值 → 不豁免。"""
    now = datetime(2026, 8, 8, 12, 0, tzinfo=timezone.utc)
    assert not dh._weekend_exempt("cme_bitcoin", "", now)
