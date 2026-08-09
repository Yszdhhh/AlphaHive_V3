"""171_basis_carry.py — 期现中性 carry 审计（A3）：BTC/ETH 现货多 + 永续空收 funding。

外部调研 A3：在 |funding| 覆盖摩擦时中性持有吃 funding。本脚本先做 BTC/ETH
（现货必然可得）的真实 carry 回测：
- 现货日线（binance spot API，免费）+ 永续日线（binance_free_db）→ 基差
- funding（110 回填）
- 简化策略：每周一次展期（周五），现货多 + 永续空（delta 中性），持有 7 天
  收益 = funding 收入 + 基差变化 − 双边成本（永续 54bps + 现货 ~20bps round-trip）
- 输出年化/回撤/胜率——判断 BTC/ETH 期现 carry 是否覆盖成本

输出：reports/basis_carry.md
用法：python scripts/171_basis_carry.py
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
sys.path.insert(0, str(PROJECT_ROOT))

REPORT = PROJECT_ROOT / "reports" / "basis_carry.md"
BINANCE_ROOT = Path(r"C:\Users\10639\Desktop\加密\binance_free_db\raw_1h")
FUND_DIR = Path(r"C:\Users\10639\Desktop\加密\binance_free_db\history\funding")
COST_PERP = 54.0 / 10000.0    # 永续开平 round-trip
COST_SPOT = 20.0 / 10000.0    # 现货开平（taker 10bp×2）
REBAL_DAYS = 90


def spot_daily(sym: str) -> pd.Series:
    """币安现货日线（2022-01 起，免费 API）。"""
    url = (f"https://api.binance.com/api/v3/klines?symbol={sym}&interval=1d"
           f"&startTime=1640995200000&limit=1000")
    all_rows = []
    start = 1640995200000
    while True:
        req = urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0"})
        with urllib.request.urlopen(req, timeout=20) as r:
            data = json.loads(r.read())
        if not data:
            break
        all_rows.extend(data)
        last = int(data[-1][0])
        if len(data) < 1000:
            break
        start = last + 86400_000
        url = (f"https://api.binance.com/api/v3/klines?symbol={sym}&interval=1d"
               f"&startTime={start}&limit=1000")
    if not all_rows:
        return pd.Series(dtype=float)
    ts = [int(k[0]) for k in all_rows]
    cl = [float(k[4]) for k in all_rows]
    s = pd.Series(cl, index=pd.to_datetime(ts, unit="ms", utc=True).tz_localize(None).normalize())
    return s[~s.index.duplicated(keep="last")].sort_index()


def perp_daily(sym: str) -> pd.Series:
    p = BINANCE_ROOT / "klines" / f"{sym}.parquet"
    if not p.exists():
        return pd.Series(dtype=float)
    kl = pd.read_parquet(p, columns=["open_time", "close"])
    ts = pd.to_numeric(kl["open_time"], errors="coerce").to_numpy(dtype=np.int64)
    cl = pd.to_numeric(kl["close"], errors="coerce").to_numpy(dtype=float)
    s = pd.Series(cl, index=pd.to_datetime(ts, unit="ms", utc=True).tz_localize(None).normalize())
    return s[~s.index.duplicated(keep="last")].sort_index()


def funding_daily(sym: str) -> pd.Series:
    p = FUND_DIR / f"{sym}.parquet"
    if not p.exists():
        return pd.Series(dtype=float)
    df = pd.read_parquet(p)
    ts = pd.to_numeric(df["fundingTime"], errors="coerce").to_numpy(dtype=np.int64)
    r = pd.to_numeric(df["fundingRate"], errors="coerce").to_numpy(dtype=float)
    s = pd.Series(r, index=pd.to_datetime(ts, unit="ms", utc=True).tz_localize(None).normalize())
    return s[~s.index.duplicated(keep="last")].sort_index()


SPOT_MAP = {
    "BTCUSDT": "BTCUSDT", "ETHUSDT": "ETHUSDT",
    "ARBUSDT": "ARBUSDT", "1000PEPEUSDT": "PEPEUSDT",
    "KITEUSDT": "KITEUSDT", "TRUMPUSDT": "TRUMPUSDT",
    "ENAUSDT": "ENAUSDT", "MUUSDT": "MUBUSDT",
    "CRCLUSDT": "CRCLBUSDT", "SNDKUSDT": "SNDKBUSDT",
}
# 1000PEPE 永续名义 = 1000×PEPE → 现货价需 ×1000 对齐
SCALE = {"1000PEPEUSDT": 1000.0}


def main() -> int:
    lines = ["# 期现中性 carry 审计：双腿合约（171，A3 扩展）\n",
             f"- 生成：{datetime.now(timezone.utc):%Y-%m-%d %H:%M UTC}",
             "- 策略：现货多 + 永续空（delta 中性），每 90 天展期；收益 = funding + 基差变化 − 成本",
             f"- 成本：永续 {COST_PERP * 10000:.0f}bps + 现货 {COST_SPOT * 10000:.0f}bps round-trip/展期\n",
             "| symbol | 现货对 | 区间 | funding 年化 | 净 carry 年化 | 周胜率 | 最大回撤 | 展期数 |",
             "|---|---|---|---|---:|---:|---:|---|"]

    for sym, spot_t in SPOT_MAP.items():
        spot = spot_daily(spot_t)
        if sym in SCALE:
            spot = spot * SCALE[sym]
        perp = perp_daily(sym)
        fund = funding_daily(sym)
        if spot.empty or perp.empty or fund.empty:
            lines.append(f"| {sym} | {spot_t} | 数据不足 | - | - | - | - | - |")
            print(f"[171] {sym} 数据不足")
            continue
        df = pd.DataFrame({"spot": spot, "perp": perp}).dropna()
        df["basis"] = df["perp"] / df["spot"] - 1.0
        fday = fund.groupby(fund.index).sum() * 3
        df["fund_daily"] = fday.reindex(df.index).ffill().fillna(0)
        df["week"] = (df.index - df.index[0]).days // REBAL_DAYS
        pnls = []
        for w, g in df.groupby("week"):
            if len(g) < 3:
                continue
            b0, b1 = g["basis"].iloc[0], g["basis"].iloc[-1]
            gross = g["fund_daily"].sum() + (b1 - b0)
            pnls.append(gross - COST_PERP - COST_SPOT)
        p = np.array(pnls)
        if len(p) == 0:
            lines.append(f"| {sym} | {spot_t} | 无展期 | - | - | - | - | - |")
            continue
        ann = p.mean() * (365 / REBAL_DAYS) * 100
        eq = np.cumprod(1 + p)
        mdd = float((eq / np.maximum.accumulate(eq) - 1).min() * 100)
        win = 100 * (p > 0).mean()
        fund_ann = df["fund_daily"].mean() * 365 * 100
        span = f"{df.index.min().date()}→{df.index.max().date()}"
        lines.append(f"| {sym} | {spot_t} | {span} | {fund_ann:+.1f}% "
                     f"| {ann:+.1f}% | {win:.0f}% | {mdd:.1f}% | {len(p)} |")
        print(f"[171] {sym}: funding {fund_ann:+.1f}%/yr 净 carry {ann:+.1f}%/yr 胜率 {win:.0f}% 回撤 {mdd:.1f}%")

    lines.extend(["\n## 解读\n",
                   "- 净 carry 年化 > 5% 且回撤可控 → 该合约期现收租可作非方向现金流腿。",
                   "- 小币 funding 高但现货深度薄 → 容量有限（$1k-10k 级），符合个人定位。",
                   "- 1000PEPE 已按 ×1000 对齐；展期 90 天摊薄成本。"])
    REPORT.parent.mkdir(parents=True, exist_ok=True)
    REPORT.write_text("\n".join(lines) + "\n", encoding="utf-8")
    print(f"wrote {REPORT}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
