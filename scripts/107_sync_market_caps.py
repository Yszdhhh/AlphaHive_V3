"""107_sync_market_caps.py — 每小时拉取 MC 快照并积累（Phase 3）。

历史 MC 缺失，OI/市值比只能从今天起【前向积累】。本脚本：
1. CoinGecko 主源拉 top 1000 的 market_cap（按 symbol 索引）
2. 经 AssetIdentityRegistry 匹配到合约符号（identity_gate：VERIFIED 才进计算）
3. 时间漂移检测 + stale gate
4. 写入 data/raw/market_caps/：
   - mc_YYYYMMDD_HHMM.parquet：时间戳快照（积累用，前向可对齐历史）
   - market_caps_latest.json：最新状态（跨进程复用，provider 自己维护）

只读 + 网络拉取，无订单路径（符合宪法）。建议 Windows 计划任务每小时跑一次。
用法：
  python scripts/107_sync_market_caps.py [--symbols BTCUSDT,1000BONKUSDT] [--force]
"""
from __future__ import annotations

import argparse
import sys
from datetime import datetime, timezone
from pathlib import Path

import pandas as pd

PROJECT_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(PROJECT_ROOT))

from harness.lib.asset_identity_registry import AssetIdentityRegistry
from harness.lib.market_cap_provider import MarketCapProvider

SNAPSHOT_DIR = PROJECT_ROOT / "data" / "raw" / "market_caps"
BASE_SYMBOLS = ["BTCUSDT", "ETHUSDT", "SOLUSDT"]  # 大盘基准，不参与山寨 OI/MC 事件池


def load_universe_symbols() -> list[str]:
    import json

    with (PROJECT_ROOT / "config" / "universe.json").open("r", encoding="utf-8") as f:
        universe = json.load(f)["symbols"]
    return [item["symbol"] for item in universe if item["symbol"] not in BASE_SYMBOLS]


def coingecko_ids_from(registry: AssetIdentityRegistry, symbols: list[str]) -> dict[str, str | None]:
    """symbol -> coingecko_id（registry 里 override/解析出的 id）。"""
    out: dict[str, str | None] = {}
    for s in symbols:
        identity = registry.resolve(s)
        out[s] = identity.coingecko_id if identity else None
    return out


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--symbols", default=None, help="逗号分隔的 symbol 子集（默认 universe 山寨池）")
    parser.add_argument("--force", action="store_true", help="强制刷新（忽略缓存）")
    args = parser.parse_args()

    symbols = [s.strip() for s in args.symbols.split(",")] if args.symbols else load_universe_symbols()

    registry = AssetIdentityRegistry.from_project_config()
    provider = MarketCapProvider(
        registry,
        cache_dir=SNAPSHOT_DIR,
        coingecko_ids=lambda: coingecko_ids_from(registry, symbols),
    )
    ok = provider.refresh(force=args.force)
    if not ok:
        print(f"[107] 刷新失败: {provider._last_error}")
        raise SystemExit(1)

    rows = []
    for s in symbols:
        identity = registry.resolve(s)
        r = provider.market_cap_usd(s)
        rows.append({
            "symbol": s,
            "base_asset": identity.base_asset if identity else None,
            "market_cap_usd": r.market_cap_usd if r else None,
            "source": r.source if r else None,
            "mapping_status": r.mapping_status if r else "UNRESOLVED",
            "suspicious": r.suspicious if r else False,
        })
    df = pd.DataFrame(rows)

    SNAPSHOT_DIR.mkdir(parents=True, exist_ok=True)
    stamp = datetime.now(timezone.utc).strftime("%Y%m%d_%H%M")
    path = SNAPSHOT_DIR / f"mc_{stamp}.parquet"
    df.to_parquet(path, index=False)

    cov = provider.coverage(symbols)
    print(f"[107] MC 快照写入 {path}")
    print(f"  symbols={cov['total']} resolved={cov['resolved']} mapped={cov['mapped']} "
          f"covered={cov['covered']} resolve_ratio={cov['resolve_ratio']:.0%} coverage_ratio={cov['coverage_ratio']:.0%}")
    bad = df[df["suspicious"]]
    if not bad.empty:
        print(f"  suspicious(时间漂移): {', '.join(bad['symbol'])}")
    n_na = df["market_cap_usd"].isna().sum()
    if n_na:
        print(f"  N/A(主源 top1000 未覆盖): {n_na} → {', '.join(df[df['market_cap_usd'].isna()]['symbol'])}")
    print(f"  universe 山寨池 MC 中位数: ${df['market_cap_usd'].median():,.0f}")


if __name__ == "__main__":
    main()
