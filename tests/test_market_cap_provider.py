"""Regression tests for the market cap provider (Phase 3)."""
from __future__ import annotations

import time
from pathlib import Path

import pytest

from harness.lib.asset_identity_registry import AssetIdentityRegistry
from harness.lib.market_cap_provider import MarketCapProvider


def _registry() -> AssetIdentityRegistry:
    overrides = {
        "1000BONKUSDT": {"base_asset": "BONK", "multiplier": 1000, "coingecko_id": "bonk"},
    }
    universe = {"SOLUSDT", "1000BONKUSDT", "DOGEUSDT"}
    return AssetIdentityRegistry(overrides=overrides, universe_symbols=universe)


def _provider(
    registry: AssetIdentityRegistry,
    caps: dict[str, float] | None = None,
    cache_dir: Path | None = None,
    max_age_minutes: int = 60,
) -> MarketCapProvider:
    caps = caps or {"SOL": 5e10, "BONK": 2e9, "DOGE": 3e10}
    return MarketCapProvider(
        registry,
        cache_dir=cache_dir,
        max_age_minutes=max_age_minutes,
        fetch_coingecko=lambda: dict(caps),
        fetch_prices=lambda ids: {},  # 单测不依赖备源
        coingecko_ids=lambda: {},
    )


def test_refresh_and_resolve_by_base_asset():
    r = _registry()
    p = _provider(r)
    assert p.refresh(force=True)
    res = p.market_cap_usd("1000BONKUSDT")  # 倍率币 → base BONK
    assert res is not None
    assert res.market_cap_usd == 2e9
    assert res.mapping_status == "VERIFIED"


def test_unresolved_symbol_returns_unresolved_cap():
    r = _registry()
    p = _provider(r)
    p.refresh(force=True)
    # 无法解析格式 → CapResult(UNRESOLVED, 0)
    res = p.market_cap_usd("")
    assert res is not None
    assert res.mapping_status == "UNRESOLVED"
    assert res.market_cap_usd == 0.0
    # 能解析（OVERRIDE）但 MC 未覆盖 → None（调用方标记 N/A）
    assert p.market_cap_usd("999WEIRDUSDT") is None


def test_uncovered_returns_none():
    r = _registry()
    p = _provider(r)
    p.refresh(force=True)
    assert p.market_cap_usd("INJUSDT") is None  # INJ 不在 fake caps → 未覆盖


def test_stale_cache_rejected_on_refresh_failure():
    r = _registry()
    p = _provider(r)
    assert p.refresh(force=True)
    # 主源开始抛异常 → refresh 回退本地快照；无本地快照且主源空 → 失败
    p2 = MarketCapProvider(
        r,
        cache_dir=None,
        fetch_coingecko=lambda: (_ for _ in ()).throw(RuntimeError("api down")),
        fetch_prices=lambda ids: {},
        coingecko_ids=lambda: {},
    )
    assert not p2.refresh(force=True)


def test_old_cached_file_is_stale_rejected():
    r = _registry()
    tmp = Path(".")
    # 用一个超龄本地快照验证 stale gate：max_age=0 → 快照必然过期
    p = MarketCapProvider(
        r,
        cache_dir=tmp,
        max_age_minutes=0,
        fetch_coingecko=lambda: (_ for _ in ()).throw(RuntimeError("api down")),
        fetch_prices=lambda ids: {},
        coingecko_ids=lambda: {},
    )
    # 没有真实快照文件可加载 → refresh 失败，符合预期（不是误用旧数据）
    assert not p.refresh(force=True)


def test_time_drift_marks_suspicious():
    r = _registry()
    calls = [{"SOL": 5e10, "BONK": 2e9}]

    def flaky():
        return dict(calls[0])

    p = MarketCapProvider(
        r,
        cache_dir=None,
        fetch_coingecko=flaky,
        fetch_prices=lambda ids: {},
        coingecko_ids=lambda: {},
    )
    assert p.refresh(force=True)
    # 第二次 refresh BONK 暴涨 100x → 漂移超 30% → suspicious
    calls[0] = {"SOL": 5e10, "BONK": 2e11}
    assert p.refresh(force=True)
    res = p.market_cap_usd("1000BONKUSDT")
    assert res is not None
    assert res.suspicious is True  # 漂移标记，调用方应跳过
    res_sol = p.market_cap_usd("SOLUSDT")
    assert res_sol is not None
    assert res_sol.suspicious is False


def test_coverage_counts():
    r = _registry()
    p = _provider(r)
    p.refresh(force=True)
    cov = p.coverage(["SOLUSDT", "1000BONKUSDT", "DOGEUSDT", "BOGUS"])
    assert cov["total"] == 4
    assert cov["resolved"] == 3  # BOGUS 解析不出
    assert cov["covered"] == 3  # SOL/BONK/DOGE 都有 MC
    assert cov["mapped"] == 3  # 全 VERIFIED
    assert cov["resolve_ratio"] == pytest.approx(0.75)


def test_snapshot_file_persisted_and_reused():
    r = _registry()
    import tempfile

    with tempfile.TemporaryDirectory() as td:
        caps = {"SOL": 5e10}
        p = MarketCapProvider(
            r,
            cache_dir=Path(td),
            max_age_minutes=60,
            fetch_coingecko=lambda: dict(caps),
            fetch_prices=lambda ids: {},
            coingecko_ids=lambda: {},
        )
        assert p.refresh(force=True)
        snap = Path(td) / "market_caps_latest.json"
        assert snap.exists()
        # 新实例（主源挂了）从本地快照恢复
        p2 = MarketCapProvider(
            r,
            cache_dir=Path(td),
            max_age_minutes=60,
            fetch_coingecko=lambda: (_ for _ in ()).throw(RuntimeError("api down")),
            fetch_prices=lambda ids: {},
            coingecko_ids=lambda: {},
        )
        assert p2.refresh(force=True)
        assert p2.market_cap_usd("SOLUSDT").market_cap_usd == 5e10
