"""Regime engine core — 市场 regime 判定纯函数（Phase 2 门控）。

把事件研究结果按触发时点的市场状态分层。判定优先级 btc_recovery > risk_off > default。
macro 只用 SP500 + BTC 状态（DXY/VIX 为合成数据，诚实排除）。

只读纯函数，无订单路径（符合宪法）。
"""
from __future__ import annotations

from pathlib import Path
from typing import Optional

import numpy as np
import pandas as pd
import yaml

REGIMES_PATH = Path(__file__).resolve().parents[2] / "config" / "market_regimes.yaml"
HOUR_MS = 3_600_000


def load_regimes(path: Optional[Path] = None) -> dict:
    p = Path(path) if path else REGIMES_PATH
    with p.open("r", encoding="utf-8") as f:
        return yaml.safe_load(f)


def btc_state(btc_close: pd.Series) -> tuple[np.ndarray, np.ndarray]:
    """返回与 btc_close 对齐的 (drawdown_20d%, above_5d_ma 布尔)。index 为 ms ts。

    drawdown = (close / 20d(480h)滚动最高点 - 1) * 100，即距 20d 高点的回撤；
    above = close > 5d(120h) MA。无完整窗口时 NaN/False。
    """
    ts = btc_close.index.to_numpy(dtype=np.int64)
    arr = btc_close.to_numpy(dtype=float)
    hi20 = pd.Series(arr, index=ts).rolling(480, min_periods=240).max()
    drawdown = (arr / hi20.to_numpy() - 1.0) * 100.0
    ma5 = pd.Series(arr, index=ts).rolling(120, min_periods=60).mean()
    above_5d = arr > ma5.to_numpy()
    return drawdown, above_5d


def sp500_below_50d(sp_close: pd.Series) -> np.ndarray:
    """SP500 收盘 < 50 交易日均线的布尔序列（按 SP 自身 index）。"""
    ma50 = sp_close.rolling(50, min_periods=25).mean()
    return (sp_close < ma50).to_numpy()


def assign_regime(
    ev_ts: np.ndarray,
    btc_dd: np.ndarray,
    btc_above5d: np.ndarray,
    btc_ts: np.ndarray,
    sp_below50d: np.ndarray,
    sp_ts: np.ndarray,
    cfg: dict,
) -> list[str]:
    """对每个事件 ts，asof 取 ts 前最近的 BTC/SP500 状态 → regime 标签。

    无前视：searchsorted(side='right')-1 只取 ts 前已完成的 bar。
    优先级 btc_recovery > risk_off > default。
    """
    btc_pos = np.searchsorted(btc_ts, ev_ts, side="right") - 1
    sp_pos = np.searchsorted(sp_ts, ev_ts, side="right") - 1
    cond = cfg["regimes"]
    out = []
    for i in range(len(ev_ts)):
        b = btc_pos[i]
        s = sp_pos[i]
        if b >= 0:
            dd = btc_dd[b]
            above = btc_above5d[b]
            rc = cond["btc_recovery"]["conditions"]
            if dd < float(rc["btc_drawdown_20d_below"]) and (above if rc.get("btc_close_above_5d_ma", True) else True):
                out.append("btc_recovery")
                continue
        if s >= 0 and sp_below50d[s]:
            out.append("risk_off")
            continue
        out.append("default")
    return out
