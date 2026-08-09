r"""118_fred_macro.py — 宏观数据多系列拉取（FRED 官方 API + yfinance 黄金）。

在 117（SP500 单系列，公开 CSV 端点无 key）基础上扩展为全宏观系列：
FRED API（需 key，见 config/local_secrets.yaml 或环境变量 FRED_API_KEY）拉
SP500/CPI/GDP/WTI/美元指数/联邦基金利率/VIX + 国债收益率曲线；
黄金用 yfinance GC=F（FRED 已停发日频金价）。

写入 Desktop\🔒 加密资产\coinglass_db\macro\：
- 每系列 macro/<key>.parquet（index=日期, close 列）
- treasury 组合 macro/TREASURY.parquet（us_2y/5y/10y/30y + us_10y_2y_spread）

幂等：增量合并（保留已存历史，只追加新日期）。--force 全量重建。
用法：
  python scripts/118_fred_macro.py [--force]
"""
from __future__ import annotations

import argparse
import os
import sys
from pathlib import Path

import numpy as np
import pandas as pd
import requests
import yaml

CONFIG_DIR = Path(__file__).resolve().parents[1] / "config"
MACRO_ROOT = Path(r"C:\Users\10639\Desktop\🔒 加密资产\coinglass_db\macro")
SOURCES_PATH = CONFIG_DIR / "macro_sources.yaml"
SECRETS_PATH = CONFIG_DIR / "local_secrets.yaml"
FRED_LIMIT = 100_000  # 单次返回上限（足够全历史）

FRED_FREQ = {
    "daily": "D", "monthly": "ME", "quarterly": "QE",
}


def load_api_key() -> str:
    if SECRETS_PATH.exists():
        d = yaml.safe_load(SECRETS_PATH.read_text(encoding="utf-8")) or {}
        k = (d.get("fred") or {}).get("api_key")
        if k:
            return str(k)
    k = os.environ.get("FRED_API_KEY")
    if k:
        return k
    raise RuntimeError("FRED API key 缺失：config/local_secrets.yaml 或环境变量 FRED_API_KEY")


def fetch_fred_series(base_url: str, series_id: str, api_key: str) -> pd.Series:
    r = requests.get(
        f"{base_url}/series/observations",
        params={"series_id": series_id, "api_key": api_key, "file_type": "json",
                "sort_order": "asc", "limit": FRED_LIMIT},
        timeout=25,
    )
    r.raise_for_status()
    obs = r.json().get("observations", [])
    rows = [(o["date"], o["value"]) for o in obs if o["value"] not in (".", "", None)]
    if not rows:
        raise RuntimeError(f"{series_id} 无观测")
    df = pd.DataFrame(rows, columns=["date", "value"])
    df["date"] = pd.to_datetime(df["date"])
    df["value"] = pd.to_numeric(df["value"], errors="coerce")
    return df.dropna().set_index("date")["value"]


def merge_series(path: Path, new: pd.Series) -> pd.Series:
    if path.exists():
        old = pd.read_parquet(path)
        old_idx = pd.DatetimeIndex(old.index)
        old_ser = pd.Series(pd.to_numeric(old["close"], errors="coerce").to_numpy(), index=old_idx)
        merged = old_ser.combine_first(new)
    else:
        merged = new
    merged = merged[~merged.index.duplicated(keep="last")].sort_index()
    return merged


def write_close(path: Path, s: pd.Series) -> int:
    df_out = pd.DataFrame({"close": s})
    df_out.to_parquet(path)
    return len(s)


def fetch_gold_yfinance(last_existing: pd.Timestamp | None) -> pd.Series:
    import yfinance as yf
    today = pd.Timestamp.now().normalize()
    if last_existing is not None and last_existing >= today:
        return pd.Series(dtype="float64", name="close")  # 已到最新，无新数据
    start = (last_existing + pd.Timedelta(days=1)).strftime("%Y-%m-%d") if last_existing is not None else "2015-01-01"
    df = yf.download("GC=F", start=start, interval="1d", auto_adjust=True, progress=False, threads=False)
    if df is None or df.empty:
        raise RuntimeError("yfinance GC=F 无数据")
    close = df["Close"]
    # 新版 yfinance 单 ticker 返回 MultiIndex 列 → squeeze 成 Series；
    # 但仅 1 行时 squeeze 会降维成标量（float64），需还原为带日期索引的 Series
    if isinstance(close, pd.DataFrame):
        close = close.squeeze()
        if isinstance(close, pd.Series):
            close.name = "close"
        elif isinstance(close, (int, float, np.integer, np.floating)):
            idx = df.index.get_level_values(0) if isinstance(df.index, pd.MultiIndex) else df.index
            close = pd.Series([float(close)], index=idx, name="close")
        else:
            close = close.to_frame().iloc[:, 0]
    close.index = pd.DatetimeIndex(close.index).tz_localize(None).normalize()
    return close.astype(float)


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--force", action="store_true", help="全量重建（忽略合并）")
    args = parser.parse_args()

    cfg = yaml.safe_load(SOURCES_PATH.read_text(encoding="utf-8"))
    base_url = cfg["fred"]["base_url"]
    api_key = load_api_key()
    MACRO_ROOT.mkdir(parents=True, exist_ok=True)

    summary: list[tuple[str, str, int, str]] = []

    # 1) 单系列
    for key, meta in cfg["series"].items():
        p = MACRO_ROOT / f"{key}.parquet"
        new = fetch_fred_series(base_url, meta["id"], api_key)
        merged = new if args.force else merge_series(p, new)
        n_old = 0
        if not args.force and p.exists():
            n_old = len(pd.read_parquet(p))
        write_close(p, merged)
        summary.append((key, meta["name"], len(merged), f"append={len(merged) - n_old}"))

    # 2) 国债组合
    tr_old = pd.DataFrame()
    if (MACRO_ROOT / "TREASURY.parquet").exists():
        tr_old = pd.read_parquet(MACRO_ROOT / "TREASURY.parquet")
    tr_parts = {}
    for k, meta in cfg["treasury"].items():
        new = fetch_fred_series(base_url, meta["id"], api_key)
        if not args.force and (MACRO_ROOT / f"{k}.parquet").exists():
            new = merge_series(MACRO_ROOT / f"{k}.parquet", new)
        write_close(MACRO_ROOT / f"{k}.parquet", new)
        tr_parts[k] = new
    comb = pd.DataFrame({k: v for k, v in tr_parts.items()}).ffill()
    comb.columns = [c.lower() for c in comb.columns]
    # 统一为 us_2y/us_5y/us_10y/us_30y（与旧 TREASURY 格式一致）
    comb = comb.rename(columns={"us2y": "us_2y", "us5y": "us_5y", "us10y": "us_10y", "us30y": "us_30y"})
    comb["us_10y_2y_spread"] = comb.get("us_10y") - comb.get("us_2y") if {"us_10y", "us_2y"}.issubset(comb.columns) else pd.Series(index=comb.index)
    if not tr_old.empty:
        for c in comb.columns:
            if c in tr_old.columns:
                merged_c = pd.to_numeric(tr_old[c], errors="coerce").combine_first(comb[c])
                comb[c] = merged_c
    comb = comb[~comb.index.duplicated(keep="last")].sort_index()
    comb.to_parquet(MACRO_ROOT / "TREASURY.parquet")
    summary.append(("TREASURY", "美债收益率曲线", len(comb), f"append={len(comb) - len(tr_old) if not tr_old.empty else len(comb)}"))

    # 3) 黄金（yfinance）
    gold_p = MACRO_ROOT / "GOLD.parquet"
    last_ex = None
    if not args.force and gold_p.exists():
        last_ex = pd.DatetimeIndex(pd.read_parquet(gold_p).index).max()
    g = fetch_gold_yfinance(None if args.force else last_ex)
    if not args.force and gold_p.exists():
        g = merge_series(gold_p, g)
    n_old_g = len(pd.read_parquet(gold_p)) if gold_p.exists() and not args.force else 0
    write_close(gold_p, g)
    summary.append(("GOLD", "COMEX黄金期货", len(g), f"append={len(g) - n_old_g}"))

    print(f"[118] 宏观数据刷新完成（FRED key 已配置）")
    for key, name, n, extra in summary:
        print(f"  {key:10s} {name:14s} rows={n:6d}  {extra}")
    print(f"[118] 目录: {MACRO_ROOT}")


if __name__ == "__main__":
    main()
