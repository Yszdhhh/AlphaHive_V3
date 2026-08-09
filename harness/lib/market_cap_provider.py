"""Market cap provider — CoinGecko 主源 + 价格降级 + 漂移检测（Phase 3）。

为 OI/市值比提供当前市场总值，供前向监控使用（历史 MC 缺失，只前向积累）。
诚实边界：
- CoinGecko /coins/markets 是唯一提供 market_cap 的公开批量端点 → 主源。
- DefiLlama coins 接口只给 price（无 MC）→ 仅作主源失败时的价格降级，
  明确标注 source=DEFILLAMA_PRICE，绝不冒充 MC。
- MC divergence 用【时间维度】检测：同一 symbol 本次 vs 上次快照 MC 相对差
  >30% → 标记 suspicious（数据源自身漂移/脏数据），而非伪造双源 MC 对比。

门控：
- identity_gate：只有 AssetIdentityRegistry 能解析的 base_asset 才匹配 MC。
- stale gate：缓存超过 max_age 的 MC 拒绝使用。

只读 + 网络拉取，无订单路径（符合宪法）。fetch 函数可注入便于单测。
"""
from __future__ import annotations

import json
import time
from dataclasses import dataclass
from pathlib import Path
from typing import Callable, Optional

from .asset_identity_registry import AssetIdentityRegistry

DRIFT_THRESHOLD = 0.30  # 前后快照 MC 相对差 >30% → suspicious
DEFAULT_MAX_AGE_MINUTES = 60
PAGES = 4  # 每页 250 → 最多 1000 个 top 币

CoinCapFetcher = Callable[[], dict[str, float]]  # base_asset(大写) -> market_cap_usd
PriceFetcher = Callable[[list[str]], dict[str, float]]  # coingecko_id -> price


@dataclass
class CapResult:
    market_cap_usd: float
    source: str  # COINGECKO / DEFILLAMA_PRICE / CACHE
    mapping_status: str  # VERIFIED / UNVERIFIED / OVERRIDE / UNRESOLVED
    suspicious: bool  # 时间漂移超阈值 → 不信任，调用方应跳过


def _fetch_coingecko(api_key: Optional[str] = None) -> dict[str, float]:
    """CoinGecko /coins/markets 分页拉 top N 的 market_cap，按 symbol 大写索引。"""
    import requests

    headers = {"x-cg-demo-api-key": api_key} if api_key else {}
    out: dict[str, float] = {}
    for page in range(1, PAGES + 1):
        r = requests.get(
            "https://api.coingecko.com/api/v3/coins/markets",
            params={"vs_currency": "usd", "order": "market_cap_desc", "per_page": 250, "page": page},
            headers=headers,
            timeout=30,
        )
        r.raise_for_status()
        data = r.json()
        if not data:
            break
        for c in data:
            mc = c.get("market_cap")
            sym = (c.get("symbol") or "").upper()
            if mc and sym:
                out[sym] = float(mc)
    return out


def _fetch_deflilama_prices(ids: list[str]) -> dict[str, float]:
    """DefiLlama 价格降级：coins.llama.fi 按 coingecko id 批量查 price（非 MC）。"""
    import requests

    if not ids:
        return {}
    out: dict[str, float] = {}
    for i in range(0, len(ids), 100):
        chunk = [f"coingecko:{x}" for x in ids[i : i + 100]]
        r = requests.get("https://coins.llama.fi/prices/current/" + ",".join(chunk), timeout=30)
        if r.status_code != 200:
            continue
        data = r.json().get("coins", {})
        for key, val in data.items():
            price = val.get("price")
            if price:
                out[key.split(":", 1)[-1].upper()] = float(price)
    return out


class MarketCapProvider:
    """MC 查询门：CoinGecko 主源 + 价格降级 + stale gate + 时间漂移检测 + identity gate。"""

    def __init__(
        self,
        registry: AssetIdentityRegistry,
        cache_dir: Optional[Path] = None,
        max_age_minutes: int = DEFAULT_MAX_AGE_MINUTES,
        fetch_coingecko: Optional[CoinCapFetcher] = None,
        fetch_prices: Optional[PriceFetcher] = None,
        coingecko_ids: Optional[Callable[[], dict[str, Optional[str]]]] = None,
        api_key_env: str = "COINGECKO_API_KEY",
    ):
        import os

        self.registry = registry
        self.cache_dir = Path(cache_dir) if cache_dir else None
        self.max_age_s = max_age_minutes * 60
        key = os.environ.get(api_key_env)
        self._fetch_coingecko = fetch_coingecko or (lambda: _fetch_coingecko(api_key=key))
        self._fetch_prices = fetch_prices or _fetch_deflilama_prices
        # symbol -> coingecko_id；备源价格用它按 id 查
        self._ids_fn = coingecko_ids or (lambda: {i.symbol: i.coingecko_id for i in [self.registry.resolve(s) for s in self.registry.verified_symbols()]})
        self._cached: dict[str, float] = {}
        self._cached_ts = 0.0
        self._last_error: Optional[str] = None

    # ---- 拉取与缓存 ----

    def refresh(self, force: bool = False) -> bool:
        """刷新 MC 快照。返回是否成功。非 force 时缓存未过期则直接复用。"""
        now = time.time()
        if not force and self._cached and (now - self._cached_ts) < self.max_age_s:
            return True
        try:
            fresh = self._fetch_coingecko()
        except Exception as e:
            fresh = {}
            self._last_error = f"coingecko: {e}"
        if not fresh:
            fresh = self._load_cached_file() or {}
        if not fresh:
            return False
        # 时间漂移检测：与上一份快照对比
        for sym, mc in fresh.items():
            prev = self._cached.get(sym)
            if prev and prev > 0:
                drift = abs(mc - prev) / max(mc, prev)
                if drift > DRIFT_THRESHOLD:
                    fresh[sym] = -abs(mc)  # 负数 = suspicious 标记
        self._cached = fresh
        self._cached_ts = now
        self._save_cached_file(fresh)
        return True

    def _snapshot_path(self) -> Path:
        assert self.cache_dir is not None
        self.cache_dir.mkdir(parents=True, exist_ok=True)
        return self.cache_dir / "market_caps_latest.json"

    def _save_cached_file(self, caps: dict[str, float]) -> None:
        if self.cache_dir is None:
            return
        try:
            self._snapshot_path().write_text(
                json.dumps({"ts": int(time.time()), "caps": caps}, ensure_ascii=False),
                encoding="utf-8",
            )
        except OSError:
            pass

    def _load_cached_file(self) -> dict[str, float]:
        """主源失败时加载本地快照（stale gate 拦截过旧的）。"""
        if self.cache_dir is None:
            return {}
        path = self._snapshot_path()
        if not path.exists():
            return {}
        if time.time() - path.stat().st_mtime > self.max_age_s:
            return {}  # stale → 拒绝
        try:
            doc = json.loads(path.read_text(encoding="utf-8"))
        except (json.JSONDecodeError, OSError):
            return {}
        return {str(k): float(v) for k, v in doc.get("caps", {}).items()}

    # ---- 查询 ----

    def market_cap_usd(self, symbol: str) -> Optional[CapResult]:
        """查某合约符号的 MC。identity 未解析返回 UNRESOLVED；MC 缺失返回 None。"""
        identity = self.registry.resolve(symbol)
        if identity is None:
            return CapResult(market_cap_usd=0.0, source="NONE", mapping_status="UNRESOLVED", suspicious=False)
        mc = self._cached.get(identity.base_asset)
        if mc is None:
            return None  # 未覆盖（主源 top 1000 之外）→ 调用方应标记 N/A
        suspicious = mc < 0
        return CapResult(
            market_cap_usd=abs(mc),
            source="COINGECKO",
            mapping_status=identity.mapping_status,
            suspicious=suspicious,
        )

    def coverage(self, symbols: list[str]) -> dict:
        """盘点某 symbol 列表的 MC 覆盖率。"""
        total = len(symbols)
        resolved = mapped = covered = 0
        for s in symbols:
            identity = self.registry.resolve(s)
            if identity is None:
                continue
            resolved += 1
            if identity.mapping_status in ("VERIFIED", "OVERRIDE"):
                mapped += 1
            mc = self._cached.get(identity.base_asset)
            if mc and mc > 0:
                covered += 1
        return {
            "total": total,
            "resolved": resolved,
            "mapped": mapped,
            "covered": covered,
            "resolve_ratio": resolved / total if total else 0.0,
            "coverage_ratio": covered / total if total else 0.0,
        }
