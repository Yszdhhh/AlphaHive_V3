"""110_backfill_history.py — 币安历史数据回填（funding，一次性）。

数据缺口（2026-08-06 核实）：
- coinglass funding_ohlc 覆盖 2024-06-05 → 2026-06-23；
- 前向 puller funding_aligned 从 2026-07-02 起；
- 中间 2022-01 → 2024-06（含 2022 磨底、2022-11 FTX 底、2023 平台）缺 funding。

本脚本用币安公开 `fapi/v1/fundingRate` 回填 **2022-01-01 → 今天** 的 funding
（老币可到上市日），存 `binance_free_db/history/funding/{symbol}.parquet`，
供 A2 funding-reset 事件研究做全 episode 验证。

已实测（2026-08-06）：
- fundingRate 支持 startTime 回填到 2022-01-01（无 API key，公开）。
- openInterestHist 历史回填不可用（该部署只返回最新，忽略 startTime）；
  binance.vision 只有 klines/aggTrades/trades，无 OI/funding 历史文件。
  → OI 历史缺口（2024-06 前 + 2026-05-26→07-11）公开渠道无法补，诚实接受。

只读公开 API，无订单路径。一次性运行，不设定时。
"""
from __future__ import annotations

import argparse
import json
import sys
import time
from pathlib import Path

import pandas as pd
import requests

PROJECT_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(PROJECT_ROOT))

# 与 binance_data_config.py 保持一致（无 emoji 路径，puller 实际写入处）
DB_ROOT = Path(r"C:\Users\10639\Desktop\加密\binance_free_db")
OUT_DIR = DB_ROOT / "history" / "funding"

FUNDING_API = "https://www.binance.info/fapi/v1/fundingRate"
BACKFILL_START_MS = 1_640_995_200_000  # 2022-01-01 00:00 UTC
PAGE_LIMIT = 1000
REQUEST_TIMEOUT_S = 20
BATCH_SLEEP_S = 0.15  # 69 symbols × ~5 页 ≈ 345 calls，60-90s 完成
BENCHMARK_SYMBOLS = ("BTCUSDT", "ETHUSDT", "SOLUSDT")


def load_universe_symbols() -> list[str]:
    with (PROJECT_ROOT / "config" / "universe.json").open("r", encoding="utf-8") as f:
        universe = json.load(f)["symbols"]
    return [item["symbol"] for item in universe]


def fetch_funding_history(symbol: str, start_ms: int, session: requests.Session) -> pd.DataFrame:
    """分页拉取 symbol 的 fundingRate 历史，返回 [fundingTime(ms), fundingRate] 表。"""
    rows: list[dict] = []
    cur = start_ms
    while True:
        params = {"symbol": symbol, "startTime": cur, "limit": PAGE_LIMIT}
        for attempt in range(3):
            try:
                r = session.get(FUNDING_API, params=params, timeout=REQUEST_TIMEOUT_S)
                r.raise_for_status()
                batch = r.json()
                break
            except Exception:
                if attempt == 2:
                    raise
                time.sleep(2 + attempt * 3)
        if not batch:
            break
        rows.extend(batch)
        last = batch[-1]["fundingTime"]
        if len(batch) < PAGE_LIMIT:
            break
        cur = last + 1  # 下一条严格大于 last
    if not rows:
        return pd.DataFrame(columns=["fundingTime", "fundingRate", "rateType"])
    df = pd.DataFrame(rows)
    df["fundingTime"] = pd.to_numeric(df["fundingTime"], errors="coerce")
    df["fundingRate"] = pd.to_numeric(df["fundingRate"], errors="coerce")
    df = df.dropna(subset=["fundingTime", "fundingRate"])
    df = df.drop_duplicates(subset=["fundingTime"], keep="last").sort_values("fundingTime")
    return df[["fundingTime", "fundingRate", "rateType"]].reset_index(drop=True)


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--start", type=int, default=BACKFILL_START_MS,
                        help="回填起点 ms（默认 2022-01-01）")
    parser.add_argument("--symbols", type=str, default=None,
                        help="逗号分隔 symbol 子集（默认 universe + 基准 3 币）")
    args = parser.parse_args()

    symbols = (args.symbols.split(",") if args.symbols
               else load_universe_symbols() + list(BENCHMARK_SYMBOLS))
    OUT_DIR.mkdir(parents=True, exist_ok=True)

    session = requests.Session()
    session.headers.update({"User-Agent": "AlphaHive-V3/110"})
    summary: list[dict] = []
    for i, sym in enumerate(symbols, 1):
        t0 = time.time()
        try:
            df = fetch_funding_history(sym, args.start, session)
        except Exception as e:
            summary.append({"symbol": sym, "n": 0, "error": str(e)[:80]})
            print(f"[{i}/{len(symbols)}] {sym}: FAIL {e}")
            continue
        if df.empty:
            summary.append({"symbol": sym, "n": 0, "error": "no funding (未上市?)"})
            print(f"[{i}/{len(symbols)}] {sym}: 无数据")
            continue
        df.to_parquet(OUT_DIR / f"{sym}.parquet", index=False)
        lo, hi = df["fundingTime"].min(), df["fundingTime"].max()
        n = len(df)
        summary.append({"symbol": sym, "n": n, "error": ""})
        print(f"[{i}/{len(symbols)}] {sym}: {n} 条 "
              f"{pd.Timestamp(int(lo), unit='ms'):%Y-%m-%d} → "
              f"{pd.Timestamp(int(hi), unit='ms'):%Y-%m-%d} ({time.time()-t0:.1f}s)")
        time.sleep(BATCH_SLEEP_S)

    # 汇总报告
    ok = [s for s in summary if s["n"] > 0]
    cov = [s for s in summary if s["n"] == 0]
    print("\n=== 回填完成 ===")
    print(f"成功 {len(ok)}/{len(symbols)}，共 {sum(s['n'] for s in ok)} 条 funding 记录")
    if cov:
        print(f"无数据 {len(cov)} 个: {[s['symbol'] for s in cov]}")
    # 早期覆盖检查（判断能否覆盖 2022/2023 磨底）
    early_2022 = []
    for s in ok:
        df = pd.read_parquet(OUT_DIR / f"{s['symbol']}.parquet")
        if df["fundingTime"].min() <= pd.Timestamp("2023-01-01").value // 1_000_000:
            early_2022.append(s["symbol"])
    print(f"覆盖 2023-01 前的 symbol（可测 2022 磨底/FTX 底）: {len(early_2022)} 个")
    print(f"  {sorted(early_2022)}")


if __name__ == "__main__":
    main()
