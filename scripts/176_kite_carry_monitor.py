"""176_kite_carry_monitor.py — KITE 期现 carry 观察项积累（A3 唯一正净 carry 合约）。

每日记录：KITE funding 近 30 天年化均值 + 基差（永续 vs 现货）+ 推断净 carry。
append 到 reports/kite_carry.csv。只观察不下单。
用法：python scripts/176_kite_carry_monitor.py
"""
from __future__ import annotations

import json
import sys
import urllib.request
from datetime import datetime, timezone
from pathlib import Path

import numpy as np
import pandas as pd

PROJECT_ROOT = Path(__file__).resolve().parents[1]
REPORTS = PROJECT_ROOT / "reports"
CSV = REPORTS / "kite_carry.csv"
FUND_DIR = Path(r"C:\Users\10639\Desktop\加密\binance_free_db\history\funding")
BINANCE_ROOT = Path(r"C:\Users\10639\Desktop\加密\binance_free_db\raw_1h")


def main() -> int:
    now = datetime.now(timezone.utc)
    # funding 近 30 天
    p = FUND_DIR / "KITEUSDT.parquet"
    if not p.exists():
        print("[176] KITE funding 缺失")
        return 1
    df = pd.read_parquet(p)
    ft = pd.to_numeric(df["fundingTime"], errors="coerce").to_numpy(dtype=np.int64)
    fr = pd.to_numeric(df["fundingRate"], errors="coerce").to_numpy(dtype=float)
    cutoff = now.timestamp() * 1000 - 30 * 86400_000
    m = ft >= cutoff
    if m.sum() < 10:
        print("[176] KITE funding 近 30 天样本不足")
        return 1
    fund_ann = fr[m].mean() * 3 * 365 * 100
    # 永续 vs 现货基差
    basis = np.nan
    try:
        pp = BINANCE_ROOT / "klines" / "KITEUSDT.parquet"
        perp = pd.read_parquet(pp, columns=["open_time", "close"])
        pclose = float(perp["close"].iloc[-1])
        req = urllib.request.Request("https://api.binance.com/api/v3/ticker/price?symbol=KITEUSDT",
                                     headers={"User-Agent": "Mozilla/5.0"})
        with urllib.request.urlopen(req, timeout=15) as r:
            sclose = float(json.loads(r.read())["price"])
        basis = (pclose / sclose - 1) * 1e4
    except Exception as exc:
        print(f"[176] 基差 ERR {exc}")
    row = {"ts": now.isoformat(),
           "funding_ann_pct": round(fund_ann, 2),
           "basis_bps": round(basis, 2) if np.isfinite(basis) else None,
           "note": "净 carry ≈ funding − 基差收敛 − 74bps/展期"}
    if CSV.exists():
        old = pd.read_csv(CSV)
        out = pd.concat([old, pd.DataFrame([row])], ignore_index=True)
    else:
        out = pd.DataFrame([row])
    out.to_csv(CSV, index=False, encoding="utf-8")
    print(f"[176] KITE: funding {fund_ann:+.1f}%/yr 基差 {basis:+.1f}bps → {CSV}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
