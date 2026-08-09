"""Contract anomaly features — 事件型 edge 的特征构造层（Phase 1）。

正交于已测过的状态型指标（OI/funding/持仓）：
- 状态型指标慢、回归时点不可控、挑时期；
- 事件型特征捕捉短时脉冲（强平级联 / CVD 量价背离 / top trader 突变），
  可对完整 24 个月历史做【全序列】计算（不只看 latest 点），供事件研究回测。

统一约定：
- 输入维度帧已 normalize 为 [timestamp(ms int), 源列] 的 1h 长表；
- 输出特征表 index=timestamp(ms int)，含价格上下文列 + 各特征列；
- z = rolling(720h=30d) 自序列 z-score；rank = rolling 分位 [0,1]；
- 全部只用已完成历史窗口，无前视。

只读纯函数，无订单路径（符合宪法）。复用了项目已有的 1h 对齐惯例。
"""
from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Optional

import numpy as np
import pandas as pd

# 30d 自序列窗口（与 scan_rules.quantile.lookback_days 对齐）
WINDOW_BARS = 720
HOUR_MS = 3_600_000

# 各维度 -> (时间列, 需要的源列)
DIMENSION_LAYOUT: dict[str, dict[str, object]] = {
    "klines": {"time_col": "open_time", "cols": ["close", "quote_volume"]},
    "liquidation": {"time_col": "time", "cols": ["long_liquidation_usd", "short_liquidation_usd"]},
    "cvd": {"time_col": "time", "cols": ["cum_vol_delta"]},
    "ls_top_trader": {"time_col": "time", "cols": ["top_position_long_short_ratio"]},
    "net_position": {"time_col": "time", "cols": ["net_position_change_cum"]},
    "funding_ohlc": {"time_col": "time", "cols": ["close"]},
}


@dataclass(frozen=True)
class FeatureWindow:
    """滚动窗口配置（默认 30d/720h）。"""
    z_bars: int = WINDOW_BARS
    rank_bars: int = WINDOW_BARS
    vol_baseline_bars: int = WINDOW_BARS
    vol_agg_bars: int = 72
    min_frac: float = 0.5


def rolling_z(series: pd.Series, window: int, min_periods: Optional[int] = None) -> pd.Series:
    """自序列 rolling z-score（NaN 安全，std=0 置 NaN）。"""
    s = pd.to_numeric(series, errors="coerce")
    min_periods = min_periods if min_periods is not None else max(int(window * 0.5), 2)
    mean = s.rolling(window, min_periods=min_periods).mean()
    std = s.rolling(window, min_periods=min_periods).std()
    z = (s - mean) / std.where(std > 0)
    return z


def rolling_rank(series: pd.Series, window: int, min_periods: Optional[int] = None) -> pd.Series:
    """当前值在滚动窗口内的分位 [0,1]（<= 当前值的占比）。"""
    s = pd.to_numeric(series, errors="coerce")
    min_periods = min_periods if min_periods is not None else max(int(window * 0.5), 2)
    return s.rolling(window, min_periods=min_periods).apply(
        lambda x: float(np.nanmean(x <= x[-1])) if np.isfinite(x[-1]) else np.nan,
        raw=True,
    )


def sign_streak(series: pd.Series) -> pd.Series:
    """连续同号次数（带符号）；0/NaN 视为重置点。适合 funding 连续性。"""
    s = pd.to_numeric(series, errors="coerce")
    arr = s.to_numpy()
    out = np.zeros(len(arr), dtype=float)
    count = 0.0
    sign = 0
    for i, v in enumerate(arr):
        if pd.isna(v) or v == 0:
            count = 0.0
            sign = 0
            out[i] = 0.0
            continue
        vs = 1.0 if v > 0 else -1.0
        if vs == sign:
            count += vs
        else:
            sign = vs
            count = vs
        out[i] = count
    return pd.Series(out, index=s.index)


def load_dim_frames(symbol: str, raw_1h_root: Path) -> dict[str, pd.DataFrame]:
    """加载某 symbol 各维度 parquet，normalize 为 [timestamp, 源列] 长表。"""
    root = Path(raw_1h_root)
    dims: dict[str, pd.DataFrame] = {}
    for name, layout in DIMENSION_LAYOUT.items():
        path = root / name / f"{symbol}.parquet"
        if not path.exists():
            continue
        df = pd.read_parquet(path)
        tc = layout["time_col"]
        cols = [tc] + [c for c in layout["cols"] if c in df.columns]
        if tc not in df.columns:
            continue
        out = df[cols].copy()
        out[tc] = pd.to_numeric(out[tc], errors="coerce")
        for c in layout["cols"]:
            if c in out.columns:
                out[c] = pd.to_numeric(out[c], errors="coerce")
        out = out.rename(columns={tc: "timestamp"}).dropna(subset=["timestamp"])
        out = out.sort_values("timestamp").drop_duplicates(subset=["timestamp"], keep="last")
        dims[name] = out
    return dims


def _sanitize_close(close: pd.Series, window: int = WINDOW_BARS) -> pd.Series:
    """抹掉 close 中的异常假 bar。

    coinglass 停更断点附近偶发假 bar（实测 1000BONKUSDT 在 2026-05-28 出现
    4.95e-06 vs 正常 0.0048，偏离 ~1000x），会污染 forward 收益与 MFE/MAE。
    用 30d rolling median 做稳健参照，偏离 [2%, 50x] 之外的 bar 置 NaN。
    median 对暴涨暴跌鲁棒，50x 对真实市场足够宽，不会误伤正常价格。
    """
    s = pd.to_numeric(close, errors="coerce")
    med = s.rolling(window, min_periods=max(int(window * 0.5), 2)).median()
    ratio = s / med.replace(0, pd.NA)
    return s.where((ratio >= 0.02) & (ratio <= 50.0))


def _align_to_axis(dims: dict[str, pd.DataFrame], axis_ts: np.ndarray) -> dict[str, dict[str, pd.Series]]:
    """把各维度源列 reindex 到统一时间轴（不做 ffill，避免跨缺区虚构）。"""
    aligned: dict[str, dict[str, pd.Series]] = {}
    for name, df in dims.items():
        layout = DIMENSION_LAYOUT[name]
        for col in layout["cols"]:
            if col not in df.columns:
                continue
            series = pd.Series(df[col].to_numpy(), index=df["timestamp"].to_numpy())
            aligned.setdefault(name, {})[col] = series.reindex(axis_ts)
    return aligned


def build_feature_table(dims: dict[str, pd.DataFrame], window: Optional[FeatureWindow] = None) -> pd.DataFrame:
    """构造逐小时特征长表。

    时间轴 = klines 覆盖范围（若无 klines 则取各维度时间轴并集）。
    """
    win = window or FeatureWindow()
    axis: pd.Series | None = None
    if "klines" in dims:
        axis = pd.Series(dims["klines"]["timestamp"].to_numpy()).sort_values().drop_duplicates()
    else:
        all_ts = np.concatenate([df["timestamp"].to_numpy() for df in dims.values()]) if dims else np.array([])
        axis = pd.Series(all_ts).sort_values().drop_duplicates()
    if axis is None or axis.empty:
        return pd.DataFrame()

    axis_ts = axis.to_numpy()
    aligned = _align_to_axis(dims, axis_ts)
    n = len(axis_ts)

    def series_of(name: str, col: str) -> pd.Series:
        s = aligned.get(name, {}).get(col)
        if s is None:
            return pd.Series(np.nan, index=pd.Index(axis_ts), dtype="float64")
        return pd.to_numeric(s, errors="coerce").astype("float64")

    close = series_of("klines", "close")
    quote_volume = series_of("klines", "quote_volume")
    short_liq = series_of("liquidation", "short_liquidation_usd")
    long_liq = series_of("liquidation", "long_liquidation_usd")
    cum_delta = series_of("cvd", "cum_vol_delta")
    top_ratio = series_of("ls_top_trader", "top_position_long_short_ratio")
    net_cum = series_of("net_position", "net_position_change_cum")
    funding = series_of("funding_ohlc", "close")

    table = pd.DataFrame(index=pd.Index(axis_ts, name="timestamp"))
    # 价格上下文（事件研究 forward 收益需要）；先抹假 bar 再派生
    close = _sanitize_close(close)
    table["close"] = close
    table["ret_24h"] = close.pct_change(24).replace([np.inf, -np.inf], pd.NA) * 100.0

    # 1) 强平级联：单边强平的 30d z-score + 空头占比
    table["liq_short_z"] = rolling_z(short_liq, win.z_bars)
    table["liq_long_z"] = rolling_z(long_liq, win.z_bars)
    total_liq = short_liq + long_liq
    table["liq_short_share"] = (short_liq / total_liq.replace(0, pd.NA))

    # 2) CVD 量价背离：price_z − cvd_z
    table["price_z"] = rolling_z(close, win.z_bars)
    table["cvd_z"] = rolling_z(cum_delta, win.z_bars)
    table["cvd_divergence"] = table["price_z"] - table["cvd_z"]

    # 2b) washout 出清：30d z 深跌 或 24h 急跌（A 线事件研究主触发，布尔 0/1）
    _wmask = table["price_z"].notna() & table["ret_24h"].notna()
    table["washout"] = ((table["price_z"] < -2.0) | (table["ret_24h"] < -8.0)).where(_wmask).astype("float64")

    # 3) top trader 拥挤：长/空比的历史分位 + 24h 变化
    table["top_ratio_rank"] = rolling_rank(top_ratio, win.rank_bars)
    table["top_ratio_chg_24h"] = top_ratio.diff(24)

    # 4) 净持仓堆积：累计净持仓变化的 24h 变化
    table["net_pos_chg_24h"] = net_cum.diff(24)

    # 5) 72h 成交异动 vs 30d 基准
    vol_base = quote_volume.rolling(win.vol_baseline_bars, min_periods=max(int(win.vol_baseline_bars * 0.5), 2)).mean()
    vol_agg = quote_volume.rolling(win.vol_agg_bars, min_periods=max(int(win.vol_agg_bars * 0.5), 2)).sum()
    table["vol_72h_ratio"] = (vol_agg / (vol_base * win.vol_agg_bars)).replace([np.inf, -np.inf], pd.NA)

    # 6) funding 连续性（单位无关，只论符号）
    table["funding_streak"] = sign_streak(funding)

    table = table.replace([np.inf, -np.inf], pd.NA)
    return table


def compute_symbol_features(symbol: str, raw_1h_root: Path, window: Optional[FeatureWindow] = None) -> pd.DataFrame:
    """便捷入口：加载维度 + 构造特征表。"""
    dims = load_dim_frames(symbol, raw_1h_root)
    return build_feature_table(dims, window)
