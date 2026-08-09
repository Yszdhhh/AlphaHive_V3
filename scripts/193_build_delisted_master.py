r"""193_build_delisted_master.py — 下架永续完整 symbol master（binance.vision S3 枚举 ∪ exchangeInfo）。

动机：幸存者偏差对冲需要"含下架币的完整研究 universe"。侦察（parallel_delisted_history.md）
已实测：S3 枚举 = 近全集（986 UM 月档符号），exchangeInfo = 当前登记（854，含 SETTLING 127）。
本脚本把两源差分成可持久化的 master，并给每个符号贴类别/状态/上市/结算时间戳。

分类规则（与侦察一致）：
- TRADING / SETTLING / PENDING_TRADING : 当前 exchangeInfo 状态
- USDT_PERP_GONE : 仅 vision、名字像 USDT 永续（= 核心幸存者集合）
- BUSD / USDC : 非 USDT 报价对（视研究定义，默认排除）
- QUARTERLY_DELIVERY : *_YYYYMM 交割合约
- SETTLED_RENAME : *SETTLED 别名（映射回原符号）

只读（HTTP + 本地写 master CSV），不碰 config/触发/纸面执行。
输出：data/delisted_master.csv
用法：python scripts/193_build_delisted_master.py
"""
from __future__ import annotations

import json
import re
import sys
import urllib.request
import xml.etree.ElementTree as ET
from datetime import datetime, timezone
from pathlib import Path

import pandas as pd

PROJECT_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(PROJECT_ROOT))

OUT = PROJECT_ROOT / "data" / "delisted_master.csv"

S3_LIST = ("https://s3-ap-northeast-1.amazonaws.com/data.binance.vision"
           "?delimiter=/&prefix=data/futures/um/monthly/klines/&max-keys=1000")
FAPI_INFO = "https://fapi.binance.com/fapi/v1/exchangeInfo"
UA = {"User-Agent": "Mozilla/5.0"}


def http_json(url: str) -> dict:
    req = urllib.request.Request(url, headers=UA)
    with urllib.request.urlopen(req, timeout=30) as r:
        return json.loads(r.read())


def list_vision_symbols() -> list[str]:
    """S3 ListBucket → UM monthly klines 顶层符号目录。"""
    req = urllib.request.Request(S3_LIST, headers=UA)
    with urllib.request.urlopen(req, timeout=60) as r:
        root = ET.fromstring(r.read())
    ns = {"s3": "http://s3.amazonaws.com/doc/2006-03-01/"}
    syms: list[str] = []
    for cp in root.findall("s3:CommonPrefixes", ns):
        prefix = cp.find("s3:Prefix", ns).text  # type: ignore[union-attr]
        # data/futures/um/monthly/klines/{SYMBOL}/
        parts = [p for p in prefix.split("/") if p]
        if parts and parts[-1]:
            syms.append(parts[-1])
    return sorted(set(syms))


def main() -> int:
    vision = list_vision_symbols()
    print(f"vision UM monthly klines symbols: {len(vision)}")

    info = http_json(FAPI_INFO)
    live = {s["symbol"]: s for s in info["symbols"]}
    print(f"fapi exchangeInfo symbols: {len(live)}")

    rows: list[dict] = []
    for sym in sorted(set(vision) | set(live)):
        meta = live.get(sym)
        if meta is not None:
            status = meta["status"]
            category = status  # TRADING / SETTLING / PENDING_TRADING
            onboard = meta.get("onboardDate")
            delivery = meta.get("deliveryDate")
            contract = meta.get("contractType")
            quote = meta.get("quoteAsset")
        else:
            status = "GONE_FROM_EXCHANGEINFO"
            onboard = delivery = None
            contract = quote = None
            if "SETTLED" in sym:
                category = "SETTLED_RENAME"
            elif re.search(r"_\d{6}$", sym):
                category = "QUARTERLY_DELIVERY"
            elif sym.endswith("BUSD"):
                category = "BUSD"
            elif sym.endswith("USDC"):
                category = "USDC"
            else:
                category = "USDT_PERP_GONE"
        rows.append({
            "symbol": sym, "status": status, "category": category,
            "contract_type": contract or "", "quote_asset": quote or "",
            "onboard_date": (datetime.fromtimestamp(onboard / 1000, tz=timezone.utc)
                             .strftime("%Y-%m-%d") if onboard else ""),
            "delivery_date": (datetime.fromtimestamp(delivery / 1000, tz=timezone.utc)
                              .strftime("%Y-%m-%d") if delivery else ""),
            "in_vision": sym in vision, "in_exchange_info": meta is not None,
        })

    df = pd.DataFrame(rows).sort_values("symbol")
    OUT.parent.mkdir(parents=True, exist_ok=True)
    df.to_csv(OUT, index=False, encoding="utf-8")
    print(f"wrote {OUT} ({len(df)} rows)")

    print("\n类别统计:")
    print(df["category"].value_counts().to_string())
    gone = df[df["category"] == "USDT_PERP_GONE"]["symbol"].tolist()
    settling = df[df["category"] == "SETTLING"]["symbol"].tolist()
    print(f"\nUSDT_PERP_GONE ({len(gone)}): {', '.join(gone)}")
    print(f"SETTLING ({len(settling)})")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
