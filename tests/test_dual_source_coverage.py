"""Regression tests for the read-only dual-source coverage validator."""
from __future__ import annotations

import importlib.util
from pathlib import Path
from unittest.mock import patch

import pandas as pd


PROJECT_ROOT = Path(__file__).resolve().parents[1]


def _load_coverage_module():
    path = PROJECT_ROOT / "scripts" / "100_dual_source_coverage.py"
    spec = importlib.util.spec_from_file_location("alpha_hive_dual_source_coverage", path)
    module = importlib.util.module_from_spec(spec)
    assert spec.loader is not None
    spec.loader.exec_module(module)
    return module


coverage = _load_coverage_module()


def _klines_frame(*, invalid_tail: bool = False) -> pd.DataFrame:
    closes = [100.0, 101.0, "bad"] if invalid_tail else [100.0, 101.0, 102.0]
    return pd.DataFrame(
        {
            "open_time": [1_700_000_000_000, 1_700_003_600_000, 1_700_007_200_000],
            "open": [99.0, 100.0, 101.0],
            "high": [101.0, 102.0, 103.0],
            "low": [98.0, 99.0, 100.0],
            "close": closes,
            "volume": [1.0, 2.0, 3.0],
        }
    )


def test_adapter_checks_every_discovered_file(tmp_path):
    directory = tmp_path / "raw_1h" / "klines"
    directory.mkdir(parents=True)
    first = directory / "BTCUSDT.parquet"
    second = directory / "ETHUSDT.parquet"
    first.touch()
    second.touch()

    frames = {first: _klines_frame(), second: _klines_frame()}
    with patch.object(coverage.pd, "read_parquet", side_effect=lambda path: frames[Path(path)]):
        result = coverage.inspect_dimension(tmp_path, "coinglass", "klines", ["BTCUSDT", "ETHUSDT"])

    assert result["adapter"] == "PASS"
    assert result["adapter_checked_files"] == 2
    assert result["adapter_failures"] == []


def test_adapter_rejects_invalid_tail_row_in_second_file(tmp_path):
    directory = tmp_path / "raw_1h" / "klines"
    directory.mkdir(parents=True)
    first = directory / "BTCUSDT.parquet"
    second = directory / "ETHUSDT.parquet"
    first.touch()
    second.touch()

    frames = {first: _klines_frame(), second: _klines_frame(invalid_tail=True)}
    with patch.object(coverage.pd, "read_parquet", side_effect=lambda path: frames[Path(path)]):
        result = coverage.inspect_dimension(tmp_path, "coinglass", "klines", ["BTCUSDT", "ETHUSDT"])

    assert result["adapter"] == "FAIL"
    assert result["adapter_checked_files"] == 2
    assert result["adapter_failures"][0]["file"] == "ETHUSDT.parquet"
