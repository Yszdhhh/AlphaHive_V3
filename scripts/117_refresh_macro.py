r"""117_refresh_macro.py — SP500 日线刷新（FRED 免费源，无 API key）。

问题：coinglass macro 目录 SP500.parquet 停在 2026-06-26（puller 停更），
106/108 的 risk_off regime 判定因 SP500 超过 7 天未更而降级。

修复：用 FRED 公开 CSV 端点（fredgraph.csv?id=SP500，无需 key）拉全历史日线，
与现有 SP500.parquet 合并追加新日期。regime 引擎只读 close 列，追加行
open/high/low 置为 close（不虚构 OHLC，诚实标注）。

用法：
  python scripts/117_refresh_macro.py [--source fred]
输出：
  更新 C:\Users\10639\Desktop\🔒 加密资产\coinglass_db\macro\SP500.parquet
"""
from __future__ import annotations

import argparse
import io
import sys
from pathlib import Path

import numpy as np
import pandas as pd
import requests

SP500_PATH = Path(r"C:\Users\10639\Desktop\🔒 加密资产\coinglass_db\macro\SP500.parquet")
FRED_URL = "https://fred.stlouisfed.org/graph/fredgraph.csv?id=SP500"
MAX_GAP_DAYS = 5  # 拉到的最近日期距今天超过该天数视为失败


def fetch_fred_sp500() -> pd.Series:
    """FRED SP500 日线 → Series(index=DatetimeIndex, close)。"""
    r = requests.get(FRED_URL, timeout=20)
    r.raise_for_status()
    df = pd.read_csv(io.StringIO(r.text))
    df["observation_date"] = pd.to_datetime(df["observation_date"])
    s = df.set_index("observation_date")["SP500"].astype(float)
    s = s[~s.index.duplicated(keep="last")].sort_index()
    return s


def refresh_sp500(path: Path, source: str = "fred") -> dict:
    if source == "fred":
        new_close = fetch_fred_sp500()
    else:
        raise ValueError(source)
    if new_close.empty:
        raise RuntimeError("FRED 返回空数据")

    last_date = new_close.index.max()
    today = pd.Timestamp.now()
    if (today - last_date).days > MAX_GAP_DAYS:
        raise RuntimeError(f"FRED 数据太旧（最近 {last_date:%Y-%m-%d}，今天 {today:%Y-%m-%d}）")

    if path.exists():
        old = pd.read_parquet(path)
        old_close = pd.to_numeric(old["close"], errors="coerce")
        old_idx = pd.DatetimeIndex(old.index)
        old_ser = pd.Series(old_close.to_numpy(dtype=float), index=old_idx).sort_index()
        merged = old_ser.combine_first(new_close)
    else:
        merged = new_close
        old = pd.DataFrame()

    merged = merged[~merged.index.duplicated(keep="last")].sort_index()
    new_rows = merged[merged.index > (old.index.max() if len(old) else pd.Timestamp.min)]

    # 写回：close 为真值，open/high/low 追加行置为 close（诚实不虚构 OHLC）
    df_out = pd.DataFrame(index=merged.index)
    df_out["close"] = merged
    df_out["open"] = merged.where(merged.index <= (old.index.max() if len(old) else pd.Timestamp.min), merged)
    df_out["high"] = df_out["open"]
    df_out["low"] = df_out["open"]
    df_out.to_parquet(path)
    return {
        "rows_total": len(merged),
        "rows_appended": len(new_rows),
        "last_date": str(merged.index.max().date()),
        "first_date": str(merged.index.min().date()),
    }


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--source", default="fred")
    args = parser.parse_args()
    try:
        info = refresh_sp500(SP500_PATH, args.source)
    except Exception as exc:
        print(f"[117] FAIL: {exc}")
        sys.exit(1)
    print(f"[117] SP500 刷新完成: 共 {info['rows_total']} 行，追加 {info['rows_appended']} 行，"
          f"覆盖 {info['first_date']} → {info['last_date']}")


if __name__ == "__main__":
    main()
