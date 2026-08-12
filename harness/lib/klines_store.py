"""统一 K 线读取（研究 / 可视化 / 策略沙盒）。

优先 binance history → raw_1h → coinglass 对照。
输出标准列：open_time(ms), open, high, low, close, volume, quote_volume（若有）。
"""
from __future__ import annotations

from pathlib import Path
from typing import Literal, Optional

import pandas as pd

from harness.lib.data_registry import paths

Source = Literal["auto", "binance_history", "binance_raw", "coinglass"]

_STD = ["open_time", "open", "high", "low", "close", "volume", "quote_volume"]


def _bn_root() -> Path:
    return Path(str(paths.binance_free.raw_1h)).parent


def resolve_path(symbol: str, source: Source = "auto") -> Path:
    sym = symbol.upper()
    if not sym.endswith("USDT") and not any(sym.endswith(x) for x in ("USD", "BUSD")):
        # allow bare; still try as-is
        pass
    hist = _bn_root() / "history" / "klines" / f"{sym}.parquet"
    raw = Path(str(paths.binance_free.raw_1h)) / "klines" / f"{sym}.parquet"
    cg = Path(str(paths.coinglass.raw_1h)) / "klines" / f"{sym}.parquet"
    if source == "binance_history":
        return hist
    if source == "binance_raw":
        return raw
    if source == "coinglass":
        return cg
    # auto: longest / freshest preference history > raw > cg
    for p in (hist, raw, cg):
        if p.exists():
            return p
    raise FileNotFoundError(f"no klines for {sym} under history/raw/coinglass")


def _normalize(df: pd.DataFrame) -> pd.DataFrame:
    d = df.copy()
    if "open_time" not in d.columns and "t" in d.columns:
        d = d.rename(columns={"t": "open_time"})
    if "open_time" not in d.columns and "time" in d.columns:
        d = d.rename(columns={"time": "open_time"})
    ren = {
        "o": "open", "h": "high", "l": "low", "c": "close",
        "v": "volume", "qv": "quote_volume",
    }
    for a, b in ren.items():
        if a in d.columns and b not in d.columns:
            d = d.rename(columns={a: b})
    d["open_time"] = pd.to_numeric(d["open_time"], errors="coerce")
    for c in ("open", "high", "low", "close", "volume"):
        if c in d.columns:
            d[c] = pd.to_numeric(d[c], errors="coerce")
    if "quote_volume" in d.columns:
        d["quote_volume"] = pd.to_numeric(d["quote_volume"], errors="coerce")
    d = d.dropna(subset=["open_time", "open", "high", "low", "close"]).sort_values("open_time")
    d = d.drop_duplicates(subset=["open_time"], keep="last")
    cols = [c for c in _STD if c in d.columns]
    return d[cols].reset_index(drop=True)


def load_klines(
    symbol: str,
    *,
    source: Source = "auto",
    start: Optional[str] = None,
    end: Optional[str] = None,
) -> pd.DataFrame:
    """读 1h K 线。start/end 为 UTC 日期或时间字符串（可解析 by pandas）。"""
    path = resolve_path(symbol, source)
    df = _normalize(pd.read_parquet(path))
    if start:
        t0 = int(pd.Timestamp(start, tz="UTC").timestamp() * 1000)
        df = df[df["open_time"] >= t0]
    if end:
        t1 = int(pd.Timestamp(end, tz="UTC").timestamp() * 1000)
        df = df[df["open_time"] <= t1]
    return df.reset_index(drop=True)


def to_datetime_index(df: pd.DataFrame) -> pd.DataFrame:
    """可视化常用：index = UTC datetime。"""
    out = df.copy()
    out["dt"] = pd.to_datetime(out["open_time"], unit="ms", utc=True)
    return out.set_index("dt").drop(columns=["open_time"], errors="ignore")
