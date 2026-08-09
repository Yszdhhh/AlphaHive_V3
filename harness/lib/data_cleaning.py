"""data_cleaning.py — 统一多源小时级数据清洗管线（2026-08-08 建立，Phase 1/U2）。

吸收此前分散在 108(_sanitize_close)、183/194(vol>0 截断)、196(hourly_grid 零填充)、
109(_future_prices_at gap) 的清洗逻辑为单一管线。gemini 外部调研的 5 步金字塔落地：
  Raw → 1.时间网格对齐/去重 → 2.硬+软离群规则 → 3.gap 策略/零填充 → 4.(跨源对账见 199)
  → Clean Parquet + quality_flag 位掩码

quality_flag 位掩码：
  0: OK, 1: Gap_ForwardFilled, 2: Outlier_Cleaned, 4: Zero_Filled, 8: Hard_Invalid

用法：
    from harness.lib.data_cleaning import clean_hourly_klines, hourly_grid
"""
from __future__ import annotations

import numpy as np
import pandas as pd

HOUR_MS = 3_600_000
PRICE_COLS = ("o", "h", "l", "c")
KLINE_COLS = ("t", "o", "h", "l", "c", "v", "qv", "tbv", "tbqv")

# 软校验：30d(720h) 滚动中位数偏离比率（gemini 建议 5x 预警 / 10x 剔除；本项目历史 50x 脏值）
OUTLIER_RATIO_WARN = 5.0
OUTLIER_RATIO_KILL = 10.0
FFILL_MAX_H = 3  # 价格 gap 前向填充上限（小时）
ROLL_WIN = 720
ROLL_MINP = 24


def hourly_grid(df: pd.DataFrame, ts_col: str = "t", val_cols: tuple[str, ...] = ("l", "s"),
                fill: float = 0.0) -> pd.DataFrame:
    """稀疏事件序列 → 整点网格（缺 bar = 无事件 = 0）。Coinalyze 清算等稀疏源必须此步。"""
    t = pd.to_numeric(df[ts_col], errors="coerce").dropna().astype("int64")
    if t.empty:
        return pd.DataFrame(columns=[ts_col, *val_cols])
    lo = int(np.floor(t.min() / HOUR_MS) * HOUR_MS)
    hi = int(np.ceil(t.max() / HOUR_MS) * HOUR_MS)
    full = pd.DataFrame({ts_col: np.arange(lo, hi + HOUR_MS, HOUR_MS, dtype=np.int64)})
    sub = df.assign(**{c: pd.to_numeric(df[c], errors="coerce").fillna(0) for c in val_cols})
    out = full.merge(sub[[ts_col, *val_cols]].drop_duplicates(ts_col), on=ts_col, how="left")
    for c in val_cols:
        out[c] = out[c].fillna(fill)
    return out


def _sanitize_close(close: np.ndarray, ratio_kill: float = OUTLIER_RATIO_KILL) -> np.ndarray:
    """软校验：30d 滚动中位数偏离 > ratio_kill 置 NaN（吸收 108 _sanitize_close）。"""
    s = pd.Series(close, dtype=float)
    med = s.rolling(ROLL_WIN, min_periods=ROLL_MINP).median()
    ratio = s / med.replace(0, np.nan)
    out = s.copy()
    out[(ratio > ratio_kill) | (ratio < 1.0 / ratio_kill)] = np.nan
    return out.to_numpy()


def clean_hourly_klines(df: pd.DataFrame, ts_col: str = "t",
                        drop_zero_vol: bool = True) -> pd.DataFrame:
    """统一清洗：整点对齐 → 去重 → 硬校验 → 软校验 → vol>0 截断 → ffill≤3h → quality_flag。

    输入列：t/o/h/l/c/v/qv/tbv/tbqv（fapi/coinglass/vision 同构）或 time/open/high/low/close。
    输出：原列 + quality_flag（位掩码）+ is_unresolved_gap。
    """
    d = df.copy()
    if "time" in d.columns and "t" not in d.columns:
        d = d.rename(columns={"time": "t"})
    for src, dst in [("open_time", "t")]:
        if src in d.columns and "t" not in d.columns:
            d = d.rename(columns={src: dst})
    for old, new in [("open", "o"), ("high", "h"), ("low", "l"),
                     ("close", "c"), ("volume", "v"), ("quote_volume", "qv")]:
        if old in d.columns and new not in d.columns:
            d = d.rename(columns={old: new})

    t = pd.to_numeric(d["t"], errors="coerce")
    d = d.assign(t=t)
    d = d.dropna(subset=["t"])
    d["t"] = (d["t"] / HOUR_MS).round().astype("int64") * HOUR_MS  # 整点对齐
    d = d.sort_values("t").drop_duplicates(subset="t", keep="last")

    d["quality_flag"] = 0
    for c in PRICE_COLS:
        if c in d.columns:
            d[c] = pd.to_numeric(d[c], errors="coerce")

    # 软校验先行：30d 中位数偏离（离群 close 会先触发硬校验的 high<close 假违例，
    # 2026-08-08 调试确认 → 必须先清离群再做物理一致性校验）
    if "c" in d.columns:
        s = pd.Series(d["c"], dtype=float)
        med = s.rolling(ROLL_WIN, min_periods=ROLL_MINP).median()
        ratio = s / med.replace(0, np.nan)
        outlier = (ratio > OUTLIER_RATIO_KILL) | (ratio < 1.0 / OUTLIER_RATIO_KILL)
        d.loc[outlier, list(PRICE_COLS)] = np.nan
        d.loc[outlier, "quality_flag"] |= 2

    # 硬校验（gemini kill rules，软校验后执行）
    if all(c in d.columns for c in PRICE_COLS):
        hard = ((d["h"] < d["l"]) | (d["h"] < d["o"]) | (d["h"] < d["c"])
                | (d["l"] > d["o"]) | (d["l"] > d["c"]))
        if "v" in d.columns:
            hard = hard | (d["v"] < 0)
        d.loc[hard, list(PRICE_COLS)] = np.nan
        d.loc[hard, "quality_flag"] |= 8

    # vol>0 截断（183/194：下架/停更后 0 量幽灵 bar）
    if drop_zero_vol and "v" in d.columns:
        zero_vol = d["v"].fillna(0) <= 0
        d.loc[zero_vol, list(PRICE_COLS)] = np.nan
        d.loc[zero_vol, "quality_flag"] |= 8

    # gap：ffill ≤ 3h
    gap_mask = d["c"].isna() if "c" in d.columns else pd.Series(False, index=d.index)
    for c in PRICE_COLS:
        if c in d.columns:
            d[c] = d[c].ffill(limit=FFILL_MAX_H)
    interp = gap_mask & d["c"].notna() if "c" in d.columns else pd.Series(False, index=d.index)
    d.loc[interp, "quality_flag"] |= 1
    d["is_unresolved_gap"] = d["c"].isna() if "c" in d.columns else True

    if "v" in d.columns:
        d["v"] = d["v"].fillna(0.0)
    return d


def forward_return_safe(ts_index: np.ndarray, close: np.ndarray, ev_ts: np.ndarray,
                        h_ms: int, gap_threshold_h: float = 2.0) -> np.ndarray:
    """事件 h 小时后最近已收盘 bar 的收益；数据断档（>gap_threshold_h×bar 周期）→ NaN。

    吸收 109 的 _future_prices_at 断档语义（数据截止早于 target 时不虚增未来收益）。
    """
    out = np.full(len(ev_ts), np.nan)
    for i, t in enumerate(ev_ts):
        j = int(np.searchsorted(ts_index, t, side="right")) - 1
        if j < 0 or j + h_ms // HOUR_MS >= len(ts_index):
            continue
        k = j + h_ms // HOUR_MS
        # 断档检测：事件 ts 与目标 bar 之间不允许超过阈值缺口
        gap_h = (ts_index[k] - t) / HOUR_MS
        if gap_h > h_ms / HOUR_MS + gap_threshold_h:
            continue
        out[i] = close[k] / close[j] - 1.0
    return out
