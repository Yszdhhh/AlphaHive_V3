r"""197_otc_premium.py — U 场外溢价（P2P）日快照（P7 数据层，只读日志，不下单）。

场外溢价 = 中国 P2P 渠道 USDT/CNY 报价 vs 离岸人民币汇率（USDCNH）的偏离：
  premium_bps = (P2P 买价 / USDCNH − 1) × 1e4
- 溢价 > 0：场外资金付溢价买 USDT = 入场/抄底需求（散户先买 U 再场内买币 → 现货买盘前置）
- 溢价 < 0：折价 = 出金/离场
关联命题（P7，198 检验）：BTC 大跌（抄底语境）时场外溢价突然转正/飙升 → BTC 短期反弹？
数据（2026-08-08 实测）：
- Binance P2P 公开端点（无 key）：POST /bapi/c2c/v2/friendly/c2c/adv/search
- OKX P2P 公开端点（无 key）：GET /v3/c2c/tradingOrders/books
- USDCNH：yfinance CNH=X（118 已用 yfinance，同款）
⚠️ 无免费历史（P2P 只给当前报价）→ 只能日快照前向积累，198 事件框架等样本。
幂等：每天一行（date 主键），同日重跑更新。

输出：data/otc_premium.csv
用法：python scripts/197_otc_premium.py
"""
from __future__ import annotations

import json
import sys
import urllib.request
from datetime import datetime, timezone
from pathlib import Path

import pandas as pd

PROJECT_ROOT = Path(__file__).resolve().parents[1]
CSV = PROJECT_ROOT / "data" / "otc_premium.csv"
UA = {"User-Agent": "Mozilla/5.0"}

BINANCE_P2P = "https://p2p.binance.com/bapi/c2c/v2/friendly/c2c/adv/search"
OKX_P2P = ("https://www.okx.com/v3/c2c/tradingOrders/books"
           "?baseCurrency=USDT&quoteCurrency=CNY&side=buy&paymentMethod=all"
           "&userType=all&showTrade=false&showFollow=false&showAlreadyTraded=false")


def binance_p2p_prices() -> tuple[float, float] | None:
    """返回 (买入价, 卖出价)。买入价 = tradeType=BUY 挂单最低价（你付的价）。"""
    def fetch(trade_type: str) -> float | None:
        body = json.dumps({"page": 1, "rows": 8, "payTypes": [],
                           "asset": "USDT", "tradeType": trade_type,
                           "fiat": "CNY"}).encode()
        req = urllib.request.Request(BINANCE_P2P, data=body,
                                     headers={"Content-Type": "application/json", **UA})
        with urllib.request.urlopen(req, timeout=20) as r:
            d = json.loads(r.read())
        prices = [float(a["adv"]["price"]) for a in (d.get("data") or [])]
        return min(prices) if prices else None  # 买 USDT 取最低挂单价
    buy = fetch("BUY")
    sell = fetch("SELL")
    if buy is None and sell is None:
        return None
    return buy, sell


def okx_p2p_prices() -> tuple[float, float] | None:
    """OKX P2P：data.buy = 可买入的卖家挂单（取最低价）；data.sell = 可卖出的买家挂单（取最高价）。"""
    req = urllib.request.Request(OKX_P2P, headers=UA)
    with urllib.request.urlopen(req, timeout=20) as r:
        d = json.loads(r.read())
    data = d.get("data") or {}
    buys = [float(a["price"]) for a in (data.get("buy") or []) if a.get("price")]
    sells = [float(a["price"]) for a in (data.get("sell") or []) if a.get("price")]
    buy = min(buys) if buys else None
    sell = max(sells) if sells else None
    if buy is None and sell is None:
        return None
    return buy, sell


def usdcnh() -> float | None:
    try:
        import yfinance as yf
        h = yf.Ticker("CNH=X").history(period="5d")
        if len(h):
            return float(h["Close"].iloc[-1])
    except Exception:  # noqa: BLE001
        pass
    return None


def main() -> int:
    now = datetime.now(timezone.utc)
    date_key = now.strftime("%Y-%m-%d")
    cnh = usdcnh()
    bin_ = binance_p2p_prices()
    okx = okx_p2p_prices()

    buy = (bin_[0] if bin_ and bin_[0] else okx[0] if okx and okx[0] else None)
    sell = (bin_[1] if bin_ and bin_[1] else okx[1] if okx and okx[1] else None)
    if buy is None or cnh is None:
        print(f"[197] {date_key}: 数据不足（cnh={cnh} binance={bin_} okx={okx}）")
        return 1
    prem_buy_bps = (buy / cnh - 1.0) * 1e4
    prem_sell_bps = (sell / cnh - 1.0) * 1e4 if sell else None
    print(f"[197] {date_key} {now:%H:%M}Z: P2P买 {buy} / 卖 {sell} vs CNH {cnh:.4f} "
          f"→ 买侧溢价 {prem_buy_bps:+.1f}bps" + (f" / 卖侧 {prem_sell_bps:+.1f}bps" if prem_sell_bps else ""))

    row = pd.DataFrame([{
        "date": date_key, "ts": now.isoformat(),
        "binance_p2p_buy": bin_[0] if bin_ else None, "binance_p2p_sell": bin_[1] if bin_ else None,
        "okx_p2p_buy": okx[0] if okx else None, "okx_p2p_sell": okx[1] if okx else None,
        "usdcnh": cnh, "premium_buy_bps": round(prem_buy_bps, 2),
        "premium_sell_bps": round(prem_sell_bps, 2) if prem_sell_bps is not None else None,
    }])
    if CSV.exists():
        old = pd.read_csv(CSV)
        row = pd.concat([old[old["date"] != date_key], row], ignore_index=True)
    row.to_csv(CSV, index=False, encoding="utf-8")
    print(f"[197] wrote {CSV}（累计 {len(row)} 天）")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
