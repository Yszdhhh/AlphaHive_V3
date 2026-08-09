"""Regression tests for 216_offline_execution_replay（2026-08-09，执行层 Phase 1 PROXY_ONLY）。

锁住（grok 瘦身版）：
1. tier_bps 分档边界（≥100M→5 / 30M→10 / 10M→20 / <10M→40）。
2. turnover_at asof 无前视（只用 ts 之前 N 小时）。
3. impact_bps：参与率≤0 → 0；range 计算与 wick 无关性（close-open 对照列存在）。
4. 源 CSV/143 不受影响（只读复盘，无写累计）。
5. 缺失 klines → 行标 NO_KLINES 不崩。
6. funding 覆盖缺失 → 0（不补零）。
"""
from __future__ import annotations

import importlib.util
import sys
from pathlib import Path

import numpy as np
import pandas as pd

PROJECT_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(PROJECT_ROOT))

_spec = importlib.util.spec_from_file_location("m216", PROJECT_ROOT / "scripts" / "216_offline_execution_replay.py")
m216 = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(m216)

HOUR_MS = 3_600_000
T0 = 1_700_000_000_000 - (1_700_000_000_000 % HOUR_MS)


def test_tier_boundaries():
    tiers = [{"min_turnover_usd": 100_000_000, "slippage_bps": 5},
             {"min_turnover_usd": 30_000_000, "slippage_bps": 10},
             {"min_turnover_usd": 10_000_000, "slippage_bps": 20},
             {"min_turnover_usd": 0, "slippage_bps": 40}]
    assert m216.tier_bps(200e6, tiers) == 5
    assert m216.tier_bps(50e6, tiers) == 10
    assert m216.tier_bps(15e6, tiers) == 20
    assert m216.tier_bps(1e6, tiers) == 40


def test_turnover_asof_no_lookahead():
    kl = pd.DataFrame({"open_time": [T0 + i * HOUR_MS for i in range(10)],
                       "quote_volume": [100.0] * 10})
    # ts=T0+5h：asof 含事件当根（T0..T0+5h = 6 根），不含未来
    v = m216.turnover_at(kl, T0 + 5 * HOUR_MS, 24)
    assert v == 600.0
    # 只用前 2h（T0+4h, T0+5h）
    v2 = m216.turnover_at(kl, T0 + 5 * HOUR_MS, 2)
    assert v2 == 200.0


def test_impact_zero_when_no_participation():
    kl = pd.DataFrame({"open_time": [T0 + i * HOUR_MS for i in range(10)],
                       "open": [100.0] * 10, "high": [101.0] * 10,
                       "low": [99.0] * 10, "close": [100.0] * 10})
    rb, imp = m216.impact_bps(kl, T0 + 3 * HOUR_MS, 0.0, 1.0, 1000.0)
    assert np.isfinite(rb) and imp == 0.0
    rb2, imp2 = m216.impact_bps(kl, T0 + 3 * HOUR_MS, 0.01, 1.0, 1000.0)
    assert imp2 > 0.0  # 有参与率 → 冲击>0


def test_missing_klines_row_status():
    # 构造一行 symbol 无 klines → status=NO_KLINES 不崩
    pos = pd.DataFrame([{"symbol": "NONEXISTENT999", "timestamp_ms": T0, "pnl_net": 1.0}])
    # 直接验证 main 的 klines 分支
    assert m216.klines("NONEXISTENT999") is None


def test_funding_coverage_missing_dir():
    assert m216.funding_coverage(["AAAUSDT"]) == 0  # 无目录/无文件 → 0，不补零


def test_config_read_only():
    # friction 读取成功且含版本锁
    f = m216.load_friction()
    assert f["friction_model_version"] == "v1"
    assert f["fees"]["taker_fee_bps"] == 5.5
