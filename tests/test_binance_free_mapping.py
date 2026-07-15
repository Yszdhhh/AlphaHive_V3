"""M-A1 regressions for pure Binance-free contract mappings."""
from __future__ import annotations

import pandas as pd
import pytest

from harness.lib.binance_free_mapping import (
    binance_funding_decimal_to_contract_raw,
    map_binance_open_interest,
)
from harness.lib.funding_normalize import normalize_funding


def test_binance_decimal_funding_maps_to_existing_contract_raw_percent() -> None:
    decimal = pd.Series([4.1725e-05, -5.0e-05, 6.0e-05, -4.5e-05, 5.5e-05])

    raw = binance_funding_decimal_to_contract_raw(decimal)

    assert raw.tolist() == pytest.approx([0.0041725, -0.005, 0.006, -0.0045, 0.0055])
    assert normalize_funding(raw).tolist() == pytest.approx(decimal.tolist())


def test_binance_open_interest_mapping_keeps_absolute_unit_undeclared() -> None:
    source = pd.DataFrame({
        "time": [0, 3_600_000],
        "sumOpenInterest": [100.0, 120.0],
        "sumOpenInterestValue": [1_000.0, 1_200.0],
    })

    mapped = map_binance_open_interest(source)

    assert mapped.to_dict("records") == [
        {"timestamp": 0, "open_interest": 100.0},
        {"timestamp": 3_600_000, "open_interest": 120.0},
    ]
    assert "sumOpenInterestValue" not in mapped.columns


def test_binance_open_interest_mapping_rejects_missing_series() -> None:
    with pytest.raises(ValueError, match="sumOpenInterest"):
        map_binance_open_interest(pd.DataFrame({"time": [0]}))
