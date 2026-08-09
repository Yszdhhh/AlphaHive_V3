"""173_cex_dex_scan.py — CEX-DEX 价差扫描（B1，只读日志，不下单）。

每小时/手动扫描：币安 bookTicker（买一卖一）vs Uniswap v3 池价（slot0，公共 RPC）。
只记录价差分布，不做任何交易决策。append 到 reports/cex_dex_spread.csv。

池配置（token0/token1/decimals，地址需验证）：
- ETH/USDC 0x88e6A0c2dDD26FEEb64F039a2c41296FcB3f5640（侦察实测）：token0=USDC(6) token1=WETH(18)，CEX 对 ETHUSDT

解码：price_token1_per_token0 = (sqrtPriceX96/2^96)^2；再按 decimals 换 USD。
用法：python scripts/173_cex_dex_scan.py [--append]
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
CSV = REPORTS / "cex_dex_spread.csv"
RPC = "https://ethereum.publicnode.com"
SQRT_2_96 = 2.0 ** 96

POOLS = [
    {
        "name": "ETH_USDC", "pool": "0x88e6A0c2dDD26FEEb64F039a2c41296FcB3f5640",
        "t0_dec": 6, "t1_dec": 18, "cex_symbol": "ETHUSDT",
    },
]


def dex_price(pool: str, t0_dec: int, t1_dec: int) -> float | None:
    payload = json.dumps({
        "jsonrpc": "2.0", "id": 1, "method": "eth_call",
        "params": [{"to": pool, "data": "0x3850c7bd"}, "latest"],
    }).encode()
    req = urllib.request.Request(RPC, data=payload,
                                 headers={"Content-Type": "application/json",
                                          "User-Agent": "Mozilla/5.0"})
    with urllib.request.urlopen(req, timeout=15) as r:
        d = json.loads(r.read())
    raw = d.get("result")
    if not raw or raw == "0x":
        return None
    sqrt = int(raw[2:66], 16) / SQRT_2_96
    px = (sqrt * sqrt) * (10.0 ** (t0_dec - t1_dec))
    # px = token1 per token0；若 token1 是 ETH（px < 0.01）→ USD 价 = 1/px
    return 1.0 / px if px < 0.01 else px


def cex_mid(sym: str) -> tuple[float, float, float] | None:
    req = urllib.request.Request(
        f"https://api.binance.com/api/v3/ticker/bookTicker?symbol={sym}",
        headers={"User-Agent": "Mozilla/5.0"})
    with urllib.request.urlopen(req, timeout=15) as r:
        d = json.loads(r.read())
    bid, ask = float(d["bidPrice"]), float(d["askPrice"])
    return bid, ask, (bid + ask) / 2


def cex_triangle_imbalance() -> float | None:
    """CEX 合成三角失衡（TDI，gemini 建议）：ETHUSDT/(BTCUSDT×ETHBTC) − 1。

    理论为 0；显著偏离 = 结构性定价失衡（充提暂停/流动性枯竭/洗盘）。
    前向积累作 wash_cvd 环境信号（无历史，不事后补造）。
    """
    try:
        eth = cex_mid("ETHUSDT")
        btc = cex_mid("BTCUSDT")
        ethbtc = cex_mid("ETHBTC")
        if None in (eth, btc, ethbtc):
            return None
        implied = btc[2] * ethbtc[2]
        return (eth[2] / implied - 1.0) * 1e4 if implied > 0 else None
    except Exception:  # noqa: BLE001
        return None


def main() -> int:
    now = datetime.now(timezone.utc)
    tdi = cex_triangle_imbalance()
    print(f"[173] CEX 三角失衡(ETHUSDT/(BTCUSDT×ETHBTC)−1): {tdi:+.2f}bps" if tdi is not None else "[173] TDI 不可得")
    rows = []
    for p in POOLS:
        try:
            dp = dex_price(p["pool"], p["t0_dec"], p["t1_dec"])
            cb = cex_mid(p["cex_symbol"])
        except Exception as exc:
            print(f"[173] {p['name']} ERR {exc}")
            continue
        if dp is None or cb is None:
            continue
        bid, ask, mid = cb
        spread_bps = (dp / mid - 1.0) * 1e4
        rows.append({
            "ts": now.isoformat(), "pool": p["name"],
            "dex_price": round(dp, 6), "cex_bid": bid, "cex_ask": ask, "cex_mid": round(mid, 6),
            "spread_bps": round(spread_bps, 2),
            "cex_triangle_bps": round(tdi, 2) if tdi is not None else None,
        })
        print(f"[173] {p['name']}: DEX {dp:.4f} vs CEX {mid:.4f} → 价差 {spread_bps:+.2f}bps | TDI {tdi:+.2f}bps" if tdi is not None
              else f"[173] {p['name']}: DEX {dp:.4f} vs CEX {mid:.4f} → 价差 {spread_bps:+.2f}bps")
    if not rows:
        return 1
    df = pd.DataFrame(rows)
    if CSV.exists() and "--append" in sys.argv:
        old = pd.read_csv(CSV)
        df = pd.concat([old, df], ignore_index=True)
    df.to_csv(CSV, index=False, encoding="utf-8")
    print(f"[173] wrote {CSV}（累计 {len(df)} 行）")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
