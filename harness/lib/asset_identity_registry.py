"""Asset identity registry — 资产身份注册表（Phase 3）。

把 coinglass 合约符号解析为标准资产身份（base_asset + 倍率 + quote），
为 OI/MC 计算提供 VERIFIED 门控。处理：
- 倍率币：`1000BONKUSDT` → (base=BONK, multiplier=1000)
- 同名币 / 换合约：由 config/asset_mapping_overrides.yaml 人工覆写
- mapping_status：VERIFIED（universe 人工审过）/ UNVERIFIED（仅自动解析）

只读纯函数 + 少量缓存，无网络、无订单路径（符合宪法）。
"""
from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Optional

# (前缀, 倍率) —— 按长度降序，避免 1000 吃掉 1000000
MULTIPLIER_TABLE = [("1000000", 1_000_000.0), ("10000", 10_000.0), ("1000", 1_000.0)]
QUOTE_SUFFIXES = ("USDT", "USD_PERP", "USD", "BUSD")

OVERRIDES_PATH = Path(__file__).resolve().parents[2] / "config" / "asset_mapping_overrides.yaml"
UNIVERSE_PATH = Path(__file__).resolve().parents[2] / "config" / "universe.json"


@dataclass(frozen=True)
class AssetIdentity:
    symbol: str          # coinglass/binance 合约符号，如 1000BONKUSDT
    base_asset: str      # 标准资产名（大写），如 BONK
    multiplier: float    # 合约倍率（1 表示无倍率）
    quote: str           # 计价币，如 USDT
    mapping_status: str  # VERIFIED / UNVERIFIED / OVERRIDE
    coingecko_id: Optional[str] = None


def parse_contract_symbol(symbol: str) -> Optional[AssetIdentity]:
    """把合约符号解析为标准身份；无法解析返回 None。"""
    s = str(symbol).strip().upper()
    if not s:
        return None
    multiplier = 1.0
    for prefix, mult in MULTIPLIER_TABLE:
        if s.startswith(prefix):
            multiplier = mult
            s = s[len(prefix):]
            break
    quote = next((q for q in QUOTE_SUFFIXES if s.endswith(q)), None)
    if quote is None or len(s) <= len(quote):
        return None
    base = s[: -len(quote)]
    if not base.isalnum():
        return None
    return AssetIdentity(symbol=symbol.strip().upper(), base_asset=base, multiplier=multiplier, quote=quote, mapping_status="UNVERIFIED")


class AssetIdentityRegistry:
    """注册表：自动解析 + 人工覆写 + universe VERIFIED 标注。"""

    def __init__(self, overrides: Optional[dict] = None, universe_symbols: Optional[set[str]] = None):
        self._overrides = overrides or {}
        self._universe = {str(x).upper() for x in (universe_symbols or [])}
        self._cache: dict[str, Optional[AssetIdentity]] = {}

    @classmethod
    def from_project_config(cls) -> "AssetIdentityRegistry":
        import json

        import yaml
        overrides: dict = {}
        if OVERRIDES_PATH.exists():
            doc = yaml.safe_load(OVERRIDES_PATH.read_text(encoding="utf-8")) or {}
            overrides = doc.get("overrides", {})
        universe: set[str] = set()
        if UNIVERSE_PATH.exists():
            universe = {item["symbol"] for item in json.loads(UNIVERSE_PATH.read_text(encoding="utf-8"))["symbols"]}
        return cls(overrides=overrides, universe_symbols=universe)

    def resolve(self, symbol: str) -> Optional[AssetIdentity]:
        sym = str(symbol).strip().upper()
        if sym in self._cache:
            return self._cache[sym]
        if not sym:
            self._cache[sym] = None
            return None
        # 1) 人工覆写优先
        ov = self._overrides.get(sym)
        if ov:
            # universe 内的覆写 = 人工审核过的确认 → VERIFIED（过 OI/MC 门控）；
            # 否则标记 OVERRIDE（人工指定但未入 universe）
            status = "VERIFIED" if sym in self._universe else "OVERRIDE"
            identity = AssetIdentity(
                symbol=sym,
                base_asset=str(ov.get("base_asset", sym.removesuffix("USDT"))).upper(),
                multiplier=float(ov.get("multiplier", 1.0)),
                quote=str(ov.get("quote", "USDT")).upper(),
                mapping_status=status,
                coingecko_id=ov.get("coingecko_id"),
            )
            self._cache[sym] = identity
            return identity
        # 2) 自动解析
        parsed = parse_contract_symbol(sym)
        if parsed is None:
            self._cache[sym] = None
            return None
        status = "VERIFIED" if sym in self._universe else "UNVERIFIED"
        identity = AssetIdentity(
            symbol=parsed.symbol, base_asset=parsed.base_asset, multiplier=parsed.multiplier,
            quote=parsed.quote, mapping_status=status,
        )
        self._cache[sym] = identity
        return identity

    def verified_symbols(self) -> list[str]:
        return [s for s in self._universe]

    def mapping_ratio(self, symbols: list[str]) -> float:
        if not symbols:
            return 0.0
        resolved = sum(1 for s in symbols if self.resolve(s) is not None)
        return resolved / len(symbols)

    def to_rows(self, symbols: list[str]) -> list[dict]:
        rows = []
        for s in symbols:
            identity = self.resolve(s)
            rows.append({
                "symbol": s,
                "base_asset": identity.base_asset if identity else None,
                "multiplier": identity.multiplier if identity else None,
                "quote": identity.quote if identity else None,
                "mapping_status": identity.mapping_status if identity else "UNRESOLVED",
                "coingecko_id": identity.coingecko_id if identity else None,
            })
        return rows
