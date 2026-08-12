r"""s017 — Token Unlock 数据可得性审计（轻量，非回测）。

探针：Mobula demo metadata.release_schedule
输出：reports/s017_unlock_data_audit.md
       G:\Quant test\derived_data\token_unlocks\sample_events.parquet（有数据时）
用法：python scripts/s017_unlock_data_audit.py
"""
from __future__ import annotations

import json
import sys
import urllib.parse
import urllib.request
from datetime import datetime, timezone
from pathlib import Path

import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
DERIVED = Path(r"G:\Quant test\derived_data\token_unlocks")
OUT_MD = ROOT / "reports" / "s017_unlock_data_audit.md"
MOBULA = "https://demo-api.mobula.io/api/1/metadata?asset={}"

# 山寨映射（有 coinglass klines 优先）；BTC/ETH 不作交易腿
ASSET_MAP = {
    "SUIUSDT": "Sui",
    "ARBUSDT": "Arbitrum",
    "ENAUSDT": "Ethena",
    "ONDOUSDT": "Ondo",
    "PENDLEUSDT": "Pendle",
    "INJUSDT": "Injective",
    "TIAUSDT": "Celestia",
    "LINKUSDT": "Chainlink",
    "AAVEUSDT": "Aave",
    "UNIUSDT": "Uniswap",
    "RENDERUSDT": "Render",
    "AVAXUSDT": "Avalanche",
    "OPUSDT": "Optimism",
    "LDOUSDT": "Lido DAO",
    "CRVUSDT": "Curve DAO",
    "FILUSDT": "Filecoin",
    "ATOMUSDT": "Cosmos",
    "APTUSDT": "Aptos",
    "WLDUSDT": "Worldcoin",
    "STRKUSDT": "Starknet",
    "SEIUSDT": "Sei",
    "JUPUSDT": "Jupiter",
    "PYTHUSDT": "Pyth Network",
    "JTOUSDT": "Jito",
    "WUSDT": "Wormhole",
    "ALTUSDT": "Altlayer",
    "MANTAUSDT": "Manta Network",
    "DYMUSDT": "Dymension",
    "PIXELUSDT": "Pixels",
    "PORTALUSDT": "Portal",
    "AEVOUSDT": "Aevo",
    "ENAUSDT": "Ethena",
    "ETHFIUSDT": "ether.fi",
    "REZUSDT": "Renzo",
    "BBUSDT": "BounceBit",
    "NOTUSDT": "Notcoin",
    "ZKUSDT": "ZKsync",
    "LISTAUSDT": "Lista DAO",
    "IOUSDT": "io.net",
    "ZROUSDT": "LayerZero",
    "DOGEUSDT": "Dogecoin",
    "ADAUSDT": "Cardano",
    "NEARUSDT": "NEAR Protocol",
    "ICPUSDT": "Internet Computer",
    "HBARUSDT": "Hedera",
    "ALGOUSDT": "Algorand",
    "SANDUSDT": "The Sandbox",
    "MANAUSDT": "Decentraland",
    "AXSUSDT": "Axie Infinity",
    "IMXUSDT": "Immutable",
    "GALAUSDT": "Gala",
    "APEUSDT": "ApeCoin",
    "LTCUSDT": "Litecoin",
    "BCHUSDT": "Bitcoin Cash",
    "DOTUSDT": "Polkadot",
    "TRXUSDT": "TRON",
    "XLMUSDT": "Stellar",
    "VETUSDT": "VeChain",
    "FTMUSDT": "Fantom",
    "SFPUSDT": "SafePal",
    "CFXUSDT": "Conflux",
    "ROSEUSDT": "Oasis Network",
    "1INCHUSDT": "1inch",
    "SNXUSDT": "Synthetix",
    "COMPUSDT": "Compound",
    "MKRUSDT": "Maker",
    "GRTUSDT": "The Graph",
    "ENSUSDT": "Ethereum Name Service",
    "LRCUSDT": "Loopring",
    "BLURUSDT": "Blur",
    "MASKUSDT": "Mask Network",
    "SSVUSDT": "ssv.network",
    "RPLUSDT": "Rocket Pool",
    "ARUSDT": "Arweave",
    "KASUSDT": "Kaspa",
    "TAOUSDT": "Bittensor",
    "FETUSDT": "Artificial Superintelligence Alliance",
    "RNDRUSDT": "Render",
}


def fetch_meta(asset: str) -> dict:
    url = MOBULA.format(urllib.parse.quote(asset, safe=""))
    req = urllib.request.Request(url, headers={"User-Agent": "AlphaHive-s017/1.0"})
    with urllib.request.urlopen(req, timeout=20) as r:
        return json.loads(r.read())


def main() -> int:
    rows = []
    events = []
    errors = []
    for sym, asset in ASSET_MAP.items():
        try:
            raw = fetch_meta(asset)
            data = raw.get("data") or {}
            rs = data.get("release_schedule") or []
            circ = data.get("circulating_supply")
            mcap = data.get("market_cap")
            n = len(rs) if isinstance(rs, list) else 0
            rows.append(
                {
                    "symbol": sym,
                    "asset": asset,
                    "n_schedule": n,
                    "has_circ": circ is not None,
                    "has_mcap": mcap is not None,
                    "circulating_supply": circ,
                    "market_cap": mcap,
                    "ok": True,
                }
            )
            if isinstance(rs, list):
                for x in rs:
                    if not isinstance(x, dict) or x.get("unlock_date") is None:
                        continue
                    tokens = float(x.get("tokens_to_unlock") or 0)
                    alloc = x.get("allocation_details") or x.get("allocation") or {}
                    if isinstance(alloc, dict):
                        alloc_keys = ",".join(sorted(str(k) for k in alloc.keys())[:8])
                    else:
                        alloc_keys = str(alloc)[:80]
                    pct_circ = (tokens / float(circ)) if circ and float(circ) > 0 else None
                    events.append(
                        {
                            "symbol": sym,
                            "asset": asset,
                            "unlock_ms": int(x["unlock_date"]),
                            "tokens_to_unlock": tokens,
                            "pct_circ": pct_circ,
                            "alloc_keys": alloc_keys,
                            "circulating_supply": circ,
                            "market_cap": mcap,
                        }
                    )
            print(f"[s017] {sym}: schedule={n}")
        except Exception as e:
            errors.append({"symbol": sym, "asset": asset, "error": str(e)})
            rows.append(
                {
                    "symbol": sym,
                    "asset": asset,
                    "n_schedule": 0,
                    "has_circ": False,
                    "has_mcap": False,
                    "circulating_supply": None,
                    "market_cap": None,
                    "ok": False,
                }
            )
            print(f"[s017] {sym}: FAIL {e}")

    cov = pd.DataFrame(rows)
    ev = pd.DataFrame(events)
    DERIVED.mkdir(parents=True, exist_ok=True)
    cov.to_csv(DERIVED / "coverage_probe.csv", index=False)
    if len(ev):
        ev["unlock_utc"] = pd.to_datetime(ev["unlock_ms"], unit="ms", utc=True)
        # 主规格过滤预览（描述性，非判定）
        ev["pass_pct_05"] = ev["pct_circ"].fillna(0) >= 0.005
        try:
            ev.to_parquet(DERIVED / "sample_events.parquet", index=False)
        except Exception:
            ev.to_csv(DERIVED / "sample_events.csv", index=False)

    n_sym = len(cov)
    n_ok = int(cov["ok"].sum()) if len(cov) else 0
    n_with = int((cov["n_schedule"] > 0).sum()) if len(cov) else 0
    n_ev = len(ev)
    n_ge05 = int(ev["pass_pct_05"].sum()) if n_ev and "pass_pct_05" in ev.columns else 0
    fields_ok = {
        "unlock_date": n_ev > 0,
        "tokens_to_unlock": n_ev > 0 and ev["tokens_to_unlock"].notna().any(),
        "circulating_for_pct": int(cov["has_circ"].sum()) if len(cov) else 0,
        "allocation_details": int((ev["alloc_keys"].astype(str).str.len() > 0).sum()) if n_ev else 0,
    }
    # team/investor 粗分：alloc_keys 含 team/investor 字样
    if n_ev:
        ak = ev["alloc_keys"].fillna("").str.lower()
        n_team_inv = int(ak.str.contains("team|investor|seed|private|vc", regex=True).sum())
    else:
        n_team_inv = 0

    verdict = "PASS_LIGHT" if n_with >= 8 and n_ev >= 20 else "PARTIAL"
    if n_with == 0:
        verdict = "FAIL_NO_DATA"

    now = datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M UTC")
    md = f"""# s017 Token Unlock — 数据可得性审计（轻量）

- date: {now}
- script: `scripts/s017_unlock_data_audit.py`
- source: Mobula demo `metadata.release_schedule`（免费路径；非 Tokenomist）
- **非回测**；不宣布 GO

## 结论

| 项 | 值 |
|---|---|
| 探针币数 | {n_sym} |
| API 成功 | {n_ok} |
| 有 release_schedule | {n_with} |
| 展开事件行 | {n_ev} |
| 可算 pct_circ≥0.5% | {n_ge05} |
| alloc 粗含 team/investor 类 | {n_team_inv} |
| **审计判定** | **{verdict}** |

## 字段可用性

- unlock_date: {fields_ok['unlock_date']}
- tokens_to_unlock: {fields_ok['tokens_to_unlock']}
- circulating_supply 覆盖币数: {fields_ok['circulating_for_pct']}
- allocation_details 非空事件: {fields_ok['allocation_details']}
- cliff vs linear: **弱**（Mobula 不标；需 Tokenomist daily-emission 或人工）

## 覆盖表（节选）

```
{cov[['symbol','asset','n_schedule','has_circ','ok']].to_string(index=False) if len(cov) else 'empty'}
```

## 缺口 / 下一跳

1. **接收方 team/investor**：Mobula allocation 命名不标准，主规格过滤需映射表或升级 Tokenomist。
2. **ADV ≥ $2M**：需 join binance 1h 成交额（本探针未做）。
3. **n≥80 主规格事件**：全量拉 watchlist + 历史 schedule 后才可估；当前 sample 仅探针。
4. 派生目录：`G:\\Quant test\\derived_data\\token_unlocks\\`（不改 coinglass/binance 源结构）。
5. 大型全量日历回填 → **VPS / Grok Bot 侧** 跑，本地只维护探针与规格。

## 错误

```
{pd.DataFrame(errors).to_string(index=False) if errors else 'none'}
```
"""
    OUT_MD.parent.mkdir(parents=True, exist_ok=True)
    OUT_MD.write_text(md, encoding="utf-8")
    print(md)
    print(f"Wrote {OUT_MD}")
    print(f"Derived {DERIVED}")
    return 0 if verdict != "FAIL_NO_DATA" else 2


if __name__ == "__main__":
    raise SystemExit(main())
