"""Regression tests for the asset identity registry (Phase 3)."""
from __future__ import annotations

import numpy as np
import pytest

from harness.lib.asset_identity_registry import (
    AssetIdentityRegistry,
    parse_contract_symbol,
)


def test_parse_plain_contract():
    i = parse_contract_symbol("SOLUSDT")
    assert i.base_asset == "SOL"
    assert i.multiplier == 1.0
    assert i.quote == "USDT"
    assert i.mapping_status == "UNVERIFIED"


def test_parse_multiplier_coins():
    assert parse_contract_symbol("1000BONKUSDT").base_asset == "BONK"
    assert parse_contract_symbol("1000BONKUSDT").multiplier == 1000.0
    # 10000 前缀不能被子 1000 吃掉
    assert parse_contract_symbol("10000LADYSUSDT").base_asset == "LADYS"
    assert parse_contract_symbol("10000LADYSUSDT").multiplier == 10_000.0
    assert parse_contract_symbol("1000000BOBUSDT").base_asset == "BOB"
    assert parse_contract_symbol("1000000BOBUSDT").multiplier == 1_000_000.0


def test_parse_unresolvable_returns_none():
    assert parse_contract_symbol("") is None
    assert parse_contract_symbol("BTC") is None  # 无 quote 后缀
    assert parse_contract_symbol("BTCUSDTX") is None  # 尾缀不认识
    assert parse_contract_symbol("USDT") is None  # 只有 quote


def test_parse_is_case_and_space_insensitive():
    i = parse_contract_symbol("  1000bonkusdt  ")
    assert i.base_asset == "BONK"
    assert i.symbol == "1000BONKUSDT"


def _registry() -> AssetIdentityRegistry:
    overrides = {
        "1000BONKUSDT": {"base_asset": "BONK", "multiplier": 1000, "coingecko_id": "bonk"},
        "999WEIRDUSDT": {"base_asset": "WEIRD", "coingecko_id": "weird-token"},  # 不在 universe
    }
    universe = {"SOLUSDT", "1000BONKUSDT"}
    return AssetIdentityRegistry(overrides=overrides, universe_symbols=universe)


def test_resolve_universe_verified():
    r = _registry()
    assert r.resolve("SOLUSDT").mapping_status == "VERIFIED"


def test_resolve_unverified_outside_universe():
    r = _registry()
    assert r.resolve("DOGEUSDT").mapping_status == "UNVERIFIED"
    assert r.resolve("DOGEUSDT").base_asset == "DOGE"


def test_resolve_override_in_universe_stays_verified():
    # universe 内的覆写 = 人工审核确认 → VERIFIED，过 OI/MC 门控
    r = _registry()
    i = r.resolve("1000BONKUSDT")
    assert i.mapping_status == "VERIFIED"
    assert i.coingecko_id == "bonk"
    assert i.multiplier == 1000.0


def test_resolve_override_outside_universe_is_override():
    r = _registry()
    i = r.resolve("999WEIRDUSDT")
    assert i.mapping_status == "OVERRIDE"
    assert i.base_asset == "WEIRD"


def test_resolve_unknown_returns_none():
    r = _registry()
    assert r.resolve("FOOUSDTX") is None  # 尾缀不认识
    assert r.resolve("12345") is None  # 纯数字无 quote
    assert r.resolve("!@#USDT") is None  # 非法字符
    assert r.resolve("") is None


def test_mapping_ratio_and_rows():
    r = _registry()
    syms = ["SOLUSDT", "DOGEUSDT", "1000BONKUSDT", "BOGUS"]
    assert r.mapping_ratio(syms) == pytest.approx(3 / 4)
    rows = r.to_rows(syms)
    assert len(rows) == 4
    assert rows[-1]["mapping_status"] == "UNRESOLVED"
    assert rows[2]["base_asset"] == "BONK"
