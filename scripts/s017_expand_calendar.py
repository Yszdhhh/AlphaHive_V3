r"""s017 — 扩 Token Unlock 日历（Mobula）并合并派生库。

- 候选 = coinglass 1h klines 全 symbol（有价才可测）
- 不改 S1 选中 pct；只扩数据
- 输出：derived_data/token_unlocks/sample_events.parquet（备份旧版）
用法：python scripts/s017_expand_calendar.py
"""
from __future__ import annotations

import json
import time
import urllib.error
import urllib.parse
import urllib.request
from datetime import datetime, timezone
from pathlib import Path

import pandas as pd

DERIVED = Path(r"G:\Quant test\derived_data\token_unlocks")
KLINES = Path(r"C:\Users\10639\Desktop\🔒 加密资产\coinglass_db\raw_1h\klines")
MOBULA = "https://demo-api.mobula.io/api/1/metadata?asset={}"
OUT_MD = Path(r"G:\Quant test\AlphaHive_V3\reports\s017_expand_calendar.md")
SLEEP_S = 0.35  # demo API 友好

# 人工映射优先；其余用 stem 启发式
KNOWN = {
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
    "RNDRUSDT": "Render",
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
    "AEVOUSDT": "Aevo",
    "ETHFIUSDT": "ether.fi",
    "NOTUSDT": "Notcoin",
    "ZKUSDT": "ZKsync",
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
    "1INCHUSDT": "1inch",
    "SNXUSDT": "Synthetix",
    "COMPUSDT": "Compound",
    "MKRUSDT": "Maker",
    "GRTUSDT": "The Graph",
    "ENSUSDT": "Ethereum Name Service",
    "LRCUSDT": "Loopring",
    "BLURUSDT": "Blur",
    "MASKUSDT": "Mask Network",
    "ARUSDT": "Arweave",
    "KASUSDT": "Kaspa",
    "TAOUSDT": "Bittensor",
    "FETUSDT": "Fetch.ai",
    "AGIXUSDT": "SingularityNET",
    "OCEANUSDT": "Ocean Protocol",
    "ORDIUSDT": "ORDI",
    "STXUSDT": "Stacks",
    "INJUSDT": "Injective",
    "SUIUSDT": "Sui",
    "TIAUSDT": "Celestia",
    "WIFUSDT": "dogwifhat",
    "BONKUSDT": "Bonk",
    "1000BONKUSDT": "Bonk",
    "1000PEPEUSDT": "Pepe",
    "PEPEUSDT": "Pepe",
    "FLOKIUSDT": "FLOKI",
    "1000FLOKIUSDT": "FLOKI",
    "SHIBUSDT": "Shiba Inu",
    "1000SHIBUSDT": "Shiba Inu",
    "SOLUSDT": "Solana",
    "BNBUSDT": "BNB",
    "XRPUSDT": "XRP",
    "TONUSDT": "Toncoin",
    "TRUMPUSDT": "Official Trump",
    "MOVEUSDT": "Movement",
    "EIGENUSDT": "EigenLayer",
    "SAGAUSDT": "Saga",
    "OMNIUSDT": "Omni Network",
    "REZUSDT": "Renzo",
    "BBUSDT": "BounceBit",
    "LISTAUSDT": "Lista DAO",
    "IOUSDT": "io.net",
    "PIXELUSDT": "Pixels",
    "PORTALUSDT": "Portal",
    "ACEUSDT": "Fusionist",
    "NFPUSDT": "NFPrompt",
    "XAIUSDT": "Xai",
    "AIUSDT": "Sleepless AI",
    "NTRNUSDT": "Neutron",
    "CYBERUSDT": "CyberConnect",
    "ARKMUSDT": "Arkham",
    "WLDUSDT": "Worldcoin",
    "PENDLEUSDT": "Pendle",
    "RDNTUSDT": "Radiant Capital",
    "MAGICUSDT": "Magic",
    "GMXUSDT": "GMX",
    "SSVUSDT": "ssv.network",
    "RPLUSDT": "Rocket Pool",
    "LPTUSDT": "Livepeer",
    "YGGUSDT": "Yield Guild Games",
    "BIGTIMEUSDT": "Big Time",
    "BEAMXUSDT": "Beam",
    "PRIMEUSDT": "Echelon Prime",
    "ILVUSDT": "Illuvium",
    "SUPERUSDT": "SuperVerse",
    "GMTUSDT": "STEPN",
    "GSTUSDT": "Green Satoshi Token",
    "HOOKUSDT": "Hooked Protocol",
    "IDUSDT": "SPACE ID",
    "EDUUSDT": "Open Campus",
    "MAVUSDT": "Maverick Protocol",
    "PENDLEUSDT": "Pendle",
    "ARKUSDT": "ARK",
    "KAVAUSDT": "Kava",
    "ROSEUSDT": "Oasis Network",
    "ZILUSDT": "Zilliqa",
    "ONEUSDT": "Harmony",
    "CELOUSDT": "Celo",
    "KSMUSDT": "Kusama",
    "RUNEUSDT": "THORChain",
    "THETAUSDT": "Theta Network",
    "EGLDUSDT": "MultiversX",
    "FLOWUSDT": "Flow",
    "MINAUSDT": "Mina",
    "QNTUSDT": "Quant",
    "CHZUSDT": "Chiliz",
    "BATUSDT": "Basic Attention Token",
    "ZRXUSDT": "0x",
    "IOTAUSDT": "IOTA",
    "NEOUSDT": "Neo",
    "QTUMUSDT": "Qtum",
    "WAVESUSDT": "Waves",
    "DASHUSDT": "Dash",
    "ZECUSDT": "Zcash",
    "XMRUSDT": "Monero",
    "ETCUSDT": "Ethereum Classic",
    "BCHUSDT": "Bitcoin Cash",
    "BSVUSDT": "Bitcoin SV",
    "CAKEUSDT": "PancakeSwap",
    "DYDXUSDT": "dYdX",
    "SUSHIUSDT": "SushiSwap",
    "1INCHUSDT": "1inch",
    "CRVUSDT": "Curve DAO",
    "BALUSDT": "Balancer",
    "YFIUSDT": "yearn.finance",
    "UMAUSDT": "UMA",
    "BANDUSDT": "Band Protocol",
    "STORJUSDT": "Storj",
    "ANKRUSDT": "Ankr",
    "CTSIUSDT": "Cartesi",
    "SKLUSDT": "SKALE",
    "CELRUSDT": "Celer Network",
    "HOTUSDT": "Holo",
    "VTHOUSDT": "VeThor Token",
    "ONTUSDT": "Ontology",
    "IOSTUSDT": "IOST",
    "DENTUSDT": "Dent",
    "KEYUSDT": "SelfKey",
    "STMXUSDT": "StormX",
    "COTIUSDT": "COTI",
    "CHRUSDT": "Chromia",
    "ALICEUSDT": "MyNeighborAlice",
    "TLMUSDT": "Alien Worlds",
    "SLPUSDT": "Smooth Love Potion",
    "ALPHAUSDT": "Stella",
    "BAKEUSDT": "BakeryToken",
    "LINAUSDT": "Linear",
    "BELUSDT": "Bella Protocol",
    "UNFIUSDT": "Unifi Protocol DAO",
    "REEFUSDT": "Reef",
    "RVNUSDT": "Ravencoin",
    "KNCUSDT": "Kyber Network Crystal",
    "LRCUSDT": "Loopring",
    "OGNUSDT": "Origin Protocol",
    "NKNUSDT": "NKN",
    "OGUSDT": "OG Fan Token",
    "PSGUSDT": "Paris Saint-Germain Fan Token",
    "JUVUSDT": "Juventus Fan Token",
    "ATMUSDT": "Atletico de Madrid Fan Token",
    "ASRUSDT": "AS Roma Fan Token",
    "BARUSDT": "FC Barcelona Fan Token",
    "CITYUSDT": "Manchester City Fan Token",
    "PORTOUSDT": "FC Porto Fan Token",
    "SANTOSUSDT": "Santos FC Fan Token",
    "LAZIOUSDT": "Lazio Fan Token",
    "ALPINEUSDT": "Alpine F1 Team Fan Token",
    "ACMUSDT": "AC Milan Fan Token",
    "POLUSDT": "Polygon",
    "MATICUSDT": "Polygon",
    "ARBUSDT": "Arbitrum",
    "OPUSDT": "Optimism",
    "METISUSDT": "Metis",
    "ASTRUSDT": "Astar",
    "GLMRUSDT": "Moonbeam",
    "MOVRUSDT": "Moonriver",
    "CFXUSDT": "Conflux",
    "KLAYUSDT": "Klaytn",
    "CROUSDT": "Cronos",
    "OKBUSDT": "OKB",
    "HTUSDT": "Huobi Token",
    "LEOUSDT": "LEO Token",
    "GTUSDT": "GateToken",
    "BGBUSDT": "Bitget Token",
}


def stem_to_asset(sym: str) -> str:
    if sym in KNOWN:
        return KNOWN[sym]
    s = sym.replace("USDT", "")
    for pref in ("1000000", "1000", "1M"):
        if s.startswith(pref):
            s = s[len(pref) :]
            break
    return s


def fetch_meta(asset: str) -> dict:
    url = MOBULA.format(urllib.parse.quote(asset, safe=""))
    req = urllib.request.Request(url, headers={"User-Agent": "AlphaHive-s017-expand/1.0"})
    with urllib.request.urlopen(req, timeout=25) as r:
        return json.loads(r.read())


def expand_events(sym: str, asset: str, data: dict) -> list[dict]:
    rs = data.get("release_schedule") or []
    circ = data.get("circulating_supply")
    mcap = data.get("market_cap")
    out = []
    if not isinstance(rs, list):
        return out
    for x in rs:
        if not isinstance(x, dict) or x.get("unlock_date") is None:
            continue
        tokens = float(x.get("tokens_to_unlock") or 0)
        alloc = x.get("allocation_details") or x.get("allocation") or {}
        if isinstance(alloc, dict):
            alloc_keys = ",".join(sorted(str(k) for k in alloc.keys())[:12])
        else:
            alloc_keys = str(alloc)[:120]
        pct = (tokens / float(circ)) if circ and float(circ) > 0 else None
        out.append(
            {
                "symbol": sym,
                "asset": asset,
                "unlock_ms": int(x["unlock_date"]),
                "tokens_to_unlock": tokens,
                "pct_circ": pct,
                "alloc_keys": alloc_keys,
                "circulating_supply": circ,
                "market_cap": mcap,
            }
        )
    return out


def main() -> int:
    DERIVED.mkdir(parents=True, exist_ok=True)
    syms = sorted(p.stem for p in KLINES.glob("*.parquet"))
    # 跳过明显非山寨/无解锁意义
    skip = {
        "BTCUSDT", "ETHUSDT", "XAUUSDT", "XAGUSDT", "BZUSDT",
        "NVDAUSDT", "TSLAUSDT", "AAPLUSDT", "AMZNUSDT", "AMDUSDT",
        "INTCUSDT", "CRCLUSDT", "SPCXUSDT", "MUUSDT", "SNDKUSDT",
    }
    targets = [s for s in syms if s not in skip]

    old_path = DERIVED / "sample_events.parquet"
    old_ev = pd.read_parquet(old_path) if old_path.exists() else pd.DataFrame()
    if len(old_ev):
        bak = DERIVED / f"sample_events_bak_{datetime.now(timezone.utc).strftime('%Y%m%d_%H%M')}.parquet"
        old_ev.to_parquet(bak, index=False)
        print(f"backup -> {bak}")

    rows_cov = []
    all_events = []
    # 先保留旧事件（若有）
    if len(old_ev):
        keep_cols = [
            "symbol", "asset", "unlock_ms", "tokens_to_unlock", "pct_circ",
            "alloc_keys", "circulating_supply", "market_cap",
        ]
        for c in keep_cols:
            if c not in old_ev.columns:
                old_ev[c] = None
        all_events.append(old_ev[keep_cols])

    # 同 asset 名只请求一次，结果映射到所有同名 symbol
    asset_cache: dict[str, dict] = {}
    n_ok = n_sched = n_fail = 0
    for i, sym in enumerate(targets):
        asset = stem_to_asset(sym)
        cache_key = asset.lower()
        try:
            if cache_key not in asset_cache:
                time.sleep(SLEEP_S)
                raw = fetch_meta(asset)
                asset_cache[cache_key] = raw.get("data") or {}
            data = asset_cache[cache_key]
            rs = data.get("release_schedule") or []
            n = len(rs) if isinstance(rs, list) else 0
            n_ok += 1
            if n > 0:
                n_sched += 1
            evs = expand_events(sym, asset, data)
            if evs:
                all_events.append(pd.DataFrame(evs))
            rows_cov.append(
                {
                    "symbol": sym,
                    "asset": asset,
                    "n_schedule": n,
                    "n_events": len(evs),
                    "ok": True,
                    "has_circ": data.get("circulating_supply") is not None,
                }
            )
            print(f"[{i+1}/{len(targets)}] {sym} -> {asset}: schedule={n} events={len(evs)}")
        except Exception as e:
            n_fail += 1
            rows_cov.append(
                {
                    "symbol": sym,
                    "asset": asset,
                    "n_schedule": 0,
                    "n_events": 0,
                    "ok": False,
                    "error": str(e)[:160],
                    "has_circ": False,
                }
            )
            print(f"[{i+1}/{len(targets)}] {sym} FAIL {e}")

    cov = pd.DataFrame(rows_cov)
    cov.to_csv(DERIVED / "coverage_expanded.csv", index=False)

    if not all_events:
        print("no events")
        return 2
    ev = pd.concat(all_events, ignore_index=True)
    # 去重：symbol + unlock_ms + tokens
    ev = ev.drop_duplicates(subset=["symbol", "unlock_ms", "tokens_to_unlock"], keep="last")
    ev["unlock_utc"] = pd.to_datetime(ev["unlock_ms"], unit="ms", utc=True)
    ev["pass_pct_05"] = ev["pct_circ"].fillna(0) >= 0.005
    ev["pass_pct_10"] = ev["pct_circ"].fillna(0) >= 0.01
    try:
        ev.to_parquet(DERIVED / "sample_events.parquet", index=False)
    except Exception:
        ev.to_csv(DERIVED / "sample_events.csv", index=False)

    n_sym = int(ev["symbol"].nunique())
    n_ge1 = int((ev["pct_circ"].fillna(0) >= 0.01).sum())
    n_ge05 = int((ev["pct_circ"].fillna(0) >= 0.005).sum())
    now = datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M UTC")
    md = f"""# s017 扩日历报告

- date: {now}
- script: `scripts/s017_expand_calendar.py`
- klines candidates: {len(targets)}
- API ok / fail: {n_ok} / {n_fail}
- symbols with non-empty schedule this run: {n_sched}
- **merged unique events**: {len(ev)}
- **unique symbols in events**: {n_sym}
- rows pct≥0.5% / ≥1%: {n_ge05} / {n_ge1}

## 有 schedule 的币（n_events>0）

```
{cov[cov['n_events']>0][['symbol','asset','n_schedule','n_events']].sort_values('n_events',ascending=False).to_string(index=False) if (cov['n_events']>0).any() else 'none'}
```

## 产出

- `{DERIVED / 'sample_events.parquet'}`
- `{DERIVED / 'coverage_expanded.csv'}`

下一步：`python scripts/s017_expand_diagnose.py`（冻结 pct=1% 重算残差+集中度）
"""
    OUT_MD.parent.mkdir(parents=True, exist_ok=True)
    OUT_MD.write_text(md, encoding="utf-8")
    print(md)
    print(f"Wrote {OUT_MD}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
