"""Event study core for contract anomaly features (Phase 2).

纯函数事件研究：触发检测（无前视 + 冷却期）→ forward 收益 + MFE/MAE →
随机基线对照 → bootstrap 置信区间。不预设方向，输出两组方向的收益，
由 105_event_study.py 汇总成 Go/No-Go 报告。

复用约定：
- 特征表来自 contract_anomaly_features.build_feature_table（index=timestamp ms）
- 时间戳一律 ms int；forward horizon 以小时计
- 所有统计对 NaN 安全；事件 ts 自动限制在 forward 窗口完整处
"""
from __future__ import annotations

from typing import Iterable, Optional

import numpy as np
import pandas as pd

HOUR_MS = 3_600_000
DEFAULT_HORIZONS = [4, 24, 72, 168]


def _as_int_ts(series: pd.Series) -> pd.Series:
    return pd.to_numeric(series, errors="coerce").astype("Int64")


def apply_price_filter(mask: pd.Series, rule: dict, table: pd.DataFrame) -> pd.Series:
    pf = rule.get("price_filter")
    if not pf:
        return mask
    col = pf["feature"]
    if col not in table.columns:
        return mask
    pv = pd.to_numeric(table[col], errors="coerce")
    if pf.get("direction", "above") == "above":
        return mask & (pv >= float(pf["threshold"]))
    return mask & (pv <= float(pf["threshold"]))


def detect_events(
    table: pd.DataFrame,
    symbol: str,
    rule: dict,
    max_forward_hours: int = 168,
) -> pd.DataFrame:
    """按单条触发规则找事件时点。

    无前视：只依赖当行及之前的特征值（特征本身已是 rolling 过去窗口）。
    冷却：同 symbol 事件间隔 >= cooldown_hours。
    事件 ts 上限：表尾 - max_forward_hours，保证 forward 收益完整。
    """
    feature = rule["feature"]
    if feature not in table.columns:
        return pd.DataFrame(columns=["symbol", "timestamp", "feature", "feature_value", "ret_24h_at_event"])
    values = pd.to_numeric(table[feature], errors="coerce")
    threshold = float(rule["threshold"])
    if rule.get("direction", "above") == "above":
        hit = values >= threshold
    else:
        hit = values <= threshold
    hit = apply_price_filter(hit & values.notna(), rule, table)

    cooldown_ms = int(rule.get("cooldown_hours", 48)) * HOUR_MS
    valid_ts = hit[hit].index.to_numpy(dtype=np.int64)
    events: list[int] = []
    last: Optional[int] = None
    for ts in valid_ts:
        if last is None or (ts - last) >= cooldown_ms:
            events.append(int(ts))
            last = int(ts)
    if not events:
        return pd.DataFrame(columns=["symbol", "timestamp", "feature", "feature_value", "ret_24h_at_event"])

    ev = pd.Series(events, dtype=np.int64)
    ret24 = pd.to_numeric(table["ret_24h"], errors="coerce").reindex(ev)
    return pd.DataFrame({
        "symbol": symbol,
        "timestamp": ev.to_numpy(),
        "feature": feature,
        "feature_value": values.reindex(ev).to_numpy(),
        "ret_24h_at_event": ret24.to_numpy(),
    })


def _future_prices_at(ts_index: pd.Index, close_arr: np.ndarray, ev_ts: np.ndarray, h_ms: int) -> np.ndarray:
    """事件 h 小时后最近已收盘 bar 的 close（时间对齐 asof，无前视）。

    用 searchsorted 找 index <= target 的最后一个已完成 bar；若该 bar 不在
    事件与 target 之间（或数据截止早于 target）→ NaN。避免 shift(-h) 跨
    数据 gap 拉到更久远未来的虚增问题。

    gap 阈值：target 距该 bar 超过 2 个 bar 周期 → 视为数据断档，返回 NaN
    （否则数据截止早于 target 时会错误返回数据最后一根的 close）。
    """
    ts_arr = ts_index.to_numpy(dtype=np.int64)
    targets = ev_ts + h_ms
    pos = np.searchsorted(ts_arr, targets, side="right") - 1
    valid = (
        (pos >= 0)
        & (ts_arr[pos] <= targets)
        & (ts_arr[pos] > ev_ts)
        & ((targets - ts_arr[pos]) < 2 * HOUR_MS)
    )
    out = np.full(len(ev_ts), np.nan)
    out[valid] = close_arr[pos[valid]]
    return out


def _window_extremes(ts_index: pd.Index, close_arr: np.ndarray, ev_ts: np.ndarray, h_ms: int) -> tuple[np.ndarray, np.ndarray]:
    """事件 ts..ts+h 时间窗内 close 的 max/min（窗口按时间边界，非按行数）。"""
    ts_arr = ts_index.to_numpy(dtype=np.int64)
    lo = np.searchsorted(ts_arr, ev_ts, side="left")
    hi = np.searchsorted(ts_arr, ev_ts + h_ms, side="right")
    n = len(ev_ts)
    mfe = np.full(n, np.nan)
    mae = np.full(n, np.nan)
    for i in range(n):
        a, b = lo[i], hi[i]
        if b - a < 2:
            continue
        seg = close_arr[a:b]
        base = close_arr[a]
        if not np.isfinite(base) or base <= 0:
            continue
        mfe[i] = (np.nanmax(seg) / base - 1.0) * 100.0
        mae[i] = (np.nanmin(seg) / base - 1.0) * 100.0
    return mfe, mae


def forward_stats(table: pd.DataFrame, events: pd.DataFrame, horizons: Iterable[int] = DEFAULT_HORIZONS) -> pd.DataFrame:
    """给事件表追加各 horizon 收益 + MFE/MAE（基于 close）。

    收益 = 事件后 h 小时最近已收盘 bar 相对事件收盘的百分比变化（时间对齐）。
    MFE/MAE = 事件后 max_forward 时间窗内 close 的极值。均无前视。
    """
    out = events.copy()
    if out.empty:
        out["mfe_pct"] = []
        out["mae_pct"] = []
        for h in horizons:
            out[f"ret_{h}h"] = []
        return out

    horizons = list(horizons)
    h_max = max(horizons)
    close = pd.to_numeric(table["close"], errors="coerce")
    ts_index = pd.Index(table.index.to_numpy(dtype=np.int64))
    close_arr = close.to_numpy(dtype=float)

    ev_ts = out["timestamp"].to_numpy(dtype=np.int64)
    base_pos = ts_index.get_indexer(ev_ts)
    base = np.full(len(ev_ts), np.nan)
    ok = base_pos >= 0
    base[ok] = close_arr[base_pos[ok]]

    for h in horizons:
        future = _future_prices_at(ts_index, close_arr, ev_ts, h * HOUR_MS)
        with np.errstate(divide="ignore", invalid="ignore"):
            out[f"ret_{h}h"] = (future / base - 1.0) * 100.0

    mfe, mae = _window_extremes(ts_index, close_arr, ev_ts, h_max * HOUR_MS)
    out["mfe_pct"] = mfe
    out["mae_pct"] = mae
    return out


def draw_random_events(
    all_tables: dict[str, pd.DataFrame],
    n: int,
    rng: np.random.Generator,
    max_forward_hours: int = 168,
    start_ms: Optional[int] = None,
    end_ms: Optional[int] = None,
) -> pd.DataFrame:
    """从全池均匀采样 n 个随机 (symbol, ts) 事件。

    时间对齐：ts 限定在每 symbol 表的可用前向范围内，保证可比性。
    区间对齐：start_ms/end_ms 把采样池限制在事件研究区间内（与事件组一致），
    否则基线会纳入区间外的数据异常（如 coinglass 停更断点后的假 bar）。
    """
    h_max = max_forward_hours * HOUR_MS
    keys = sorted(all_tables)
    if not keys:
        return pd.DataFrame()
    pools: list[tuple[str, np.ndarray]] = []
    for k in keys:
        t = all_tables[k].index.to_numpy(dtype=np.int64)
        if len(t) == 0:
            continue
        max_ts = int(t.max()) - h_max
        valid = t[t <= max_ts]
        if start_ms is not None:
            valid = valid[valid >= start_ms]
        if end_ms is not None:
            valid = valid[valid <= end_ms]
        if len(valid) >= 24:
            pools.append((k, valid))
    if not pools:
        return pd.DataFrame()

    total = sum(len(p) for _, p in pools)
    out_sym: list[str] = []
    out_ts: list[int] = []
    # 按池大小加权采样，避免大 symbol 垄断
    weights = np.array([len(p) for _, p in pools], dtype=float)
    while len(out_sym) < n:
        k = rng.choice(len(pools), p=weights / weights.sum())
        sym, pool = pools[k]
        out_sym.append(sym)
        out_ts.append(int(rng.choice(pool)))
    return pd.DataFrame({"symbol": out_sym, "timestamp": out_ts})


def bootstrap_ci(
    event_rets: np.ndarray,
    baseline_rets: np.ndarray,
    n_boot: int = 1000,
    alpha: float = 0.05,
    seed: int = 0,
) -> dict:
    """重采样差异（事件均值 − 基线均值）的置信区间。返回 dict。"""
    e = np.asarray(event_rets, dtype=float)
    b = np.asarray(baseline_rets, dtype=float)
    e = e[np.isfinite(e)]
    b = b[np.isfinite(b)]
    if len(e) == 0 or len(b) == 0:
        return {"mean_diff": np.nan, "ci_lo": np.nan, "ci_hi": np.nan, "n_event": len(e), "n_baseline": len(b)}
    rng = np.random.default_rng(seed)
    diffs = np.empty(n_boot)
    for i in range(n_boot):
        es = rng.choice(e, size=len(e), replace=True)
        bs = rng.choice(b, size=len(b), replace=True)
        diffs[i] = np.mean(es) - np.mean(bs)
    return {
        "mean_diff": float(np.mean(e) - np.mean(b)),
        "ci_lo": float(np.quantile(diffs, alpha / 2)),
        "ci_hi": float(np.quantile(diffs, 1 - alpha / 2)),
        "n_event": len(e),
        "n_baseline": len(b),
    }


def summarize_events(events: pd.DataFrame, horizons: Iterable[int] = DEFAULT_HORIZONS) -> dict:
    """单组事件的基础统计（均值/中位数/胜率）。"""
    horizons = list(horizons)
    out: dict = {"n": len(events)}
    for h in horizons:
        col = f"ret_{h}h"
        v = pd.to_numeric(events[col], errors="coerce").dropna()
        out[f"ret_{h}h_mean"] = float(v.mean()) if len(v) else np.nan
        out[f"ret_{h}h_median"] = float(v.median()) if len(v) else np.nan
        out[f"ret_{h}h_win"] = float((v > 0).mean()) if len(v) else np.nan
    if "mfe_pct" in events.columns:
        out["mfe_mean"] = float(pd.to_numeric(events["mfe_pct"], errors="coerce").mean())
        out["mae_mean"] = float(pd.to_numeric(events["mae_pct"], errors="coerce").mean())
    return out
