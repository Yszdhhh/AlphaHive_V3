"""data_registry.py — 统一数据路径注册表 + 新鲜度检查（2026-08-08 建立）。

背景：30+ 脚本硬编码绝对路径（emoji 漂移已踩坑 2 次）→ 本模块是唯一路径来源，
新脚本必须从这里取路径；旧脚本逐步迁移。

用法：
    from harness.lib.data_registry import paths, freshness
    kl = paths.coinglass.raw_1h / "klines" / "BTCUSDT.parquet"
    age_h, stale = freshness(kl, ts_col="time", max_age_h=48)
"""
from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path

import pandas as pd
import yaml

_PROJECT_ROOT = Path(__file__).resolve().parents[2]
_CONFIG = _PROJECT_ROOT / "config" / "data_paths.yaml"


@dataclass
class _Node:
    """递归路径节点：data.coinglass.raw_1h → Path。"""
    _path: Path | None = None
    children: dict[str, object] = field(default_factory=dict, compare=False)

    def __getattr__(self, key: str) -> "_Node | Path":
        if key in self.children:
            v = self.children[key]
            if isinstance(v, _Node):
                return v
            return _Node(Path(v) if isinstance(v, str) else v)  # type: ignore[arg-type]
        raise AttributeError(key)

    @property
    def path(self) -> Path:
        assert self._path is not None
        return self._path

    def __str__(self) -> str:
        return str(self._path)

    def __truediv__(self, other: str) -> Path:
        assert self._path is not None
        return self._path / other


def _build() -> "_Node":
    with _CONFIG.open("r", encoding="utf-8") as f:
        raw = yaml.safe_load(f)

    def walk(d: dict) -> "_Node":
        children: dict[str, object] = {}
        root_p: Path | None = None
        for k, v in d.items():
            if k == "root":
                root_p = Path(v)
            else:
                children[k] = v
        node = _Node(None, children)
        if root_p is not None:
            for k, v in list(children.items()):
                p = Path(v)
                node.children[k] = root_p / p if not p.is_absolute() else p  # type: ignore[operator]
        return node

    top = _Node(None, {})
    for group, cfg in raw.items():
        top.children[group] = walk(cfg)  # type: ignore[assignment]
    return top


# 模块级单例：coinglass.raw_1h / binance_free.raw_1h / project.data / ...
paths: _Node = _build()


def freshness(path: Path, ts_col: str | None = "t", max_age_h: float = 48.0) -> tuple[float, bool]:
    """文件新鲜度：返回 (最近 bar 距今小时数, 是否过期)。

    支持：数值 ms/s 时间戳列、datetime64 列、DatetimeIndex（ts_col=None）。
    无法读取 → (nan, True)。
    """
    try:
        df = pd.read_parquet(path) if ts_col is None else pd.read_parquet(path, columns=[ts_col])
        if ts_col is None:
            idx = df.index
            if isinstance(idx, pd.DatetimeIndex):
                last = idx.max()
                age_h = (pd.Timestamp.now(tz=last.tz) - last).total_seconds() / 3600.0
                return age_h, age_h > max_age_h
            return float("nan"), True
        col = df[ts_col]
        if pd.api.types.is_datetime64_any_dtype(col):
            last = col.max()
            age_h = (pd.Timestamp.now(tz=last.tz) - last).total_seconds() / 3600.0
            return age_h, age_h > max_age_h
        last = pd.to_numeric(col, errors="coerce").dropna().max()
        if pd.isna(last):
            return float("nan"), True
        last_s = last / 1000.0 if last > 1e12 else last
        import time
        age_h = (time.time() - last_s) / 3600.0
        return age_h, age_h > max_age_h
    except Exception:  # noqa: BLE001
        return float("nan"), True


def health_report() -> dict[str, dict]:
    """注册源健康快照：路径、最后 bar 时间、距今小时、是否过期。"""
    import time
    from datetime import datetime, timezone

    # history klines：相对 binance_free root（raw_1h 的 parent）
    _bn_root = Path(str(paths.binance_free.raw_1h)).parent
    checks = {
        "coinglass_klines": (paths.coinglass.raw_1h / "klines" / "BTCUSDT.parquet", "open_time", 48),
        "coinglass_liquidation": (paths.coinglass.raw_1h / "liquidation" / "BTCUSDT.parquet", "time", 72),
        "binance_klines": (paths.binance_free.raw_1h / "klines" / "BTCUSDT.parquet", "open_time", 3),
        "binance_klines_history": (_bn_root / "history" / "klines" / "BTCUSDT.parquet", "open_time", 48),
        "binance_funding_history": (_bn_root / "history" / "funding" / "BTCUSDT.parquet", "fundingTime", 24),
        "coinalyze_liquidation": (paths.project.data / "coinalyze_liquidation" / "DOGEUSDT.parquet", "t", 96),
        "otc_premium": (paths.project.data / "otc_premium.csv", "date", 30),
        "macro_sp500": (paths.coinglass.macro / "SP500.parquet", None, 120),
        "macro_vix": (paths.coinglass.macro / "VIX.parquet", None, 120),
        "cme_bitcoin": (paths.coinglass.macro / "cme_bitcoin.parquet", "date", 96),
    }
    out: dict[str, dict] = {}
    for name, (p, ts_col, max_h) in checks.items():
        if not p.exists():
            out[name] = {"exists": False, "age_h": None, "stale": True}
            continue
        if p.suffix == ".csv":
            try:
                df = pd.read_csv(p)
                last = pd.to_datetime(df[ts_col], errors="coerce").max()
                age_h = (pd.Timestamp.now(tz=last.tz) - last).total_seconds() / 3600
                out[name] = {"exists": True, "last": str(last.date()), "age_h": round(age_h, 1),
                             "stale": age_h > max_h}
            except Exception:  # noqa: BLE001
                out[name] = {"exists": True, "age_h": None, "stale": True}
            continue
        age_h, stale = freshness(p, ts_col=ts_col, max_age_h=float(max_h))
        last_s = None
        if p.exists():
            try:
                if ts_col is None:
                    df = pd.read_parquet(p)
                    last_v = df.index.max()
                    last_s = last_v.strftime("%Y-%m-%d %H:%M")
                else:
                    df = pd.read_parquet(p, columns=[ts_col])
                    col = df[ts_col]
                    if pd.api.types.is_datetime64_any_dtype(col):
                        last_s = col.max().strftime("%Y-%m-%d %H:%M")
                    else:
                        last_v = pd.to_numeric(col, errors="coerce").dropna().max()
                        last_s = datetime.fromtimestamp(
                            (last_v / 1000 if last_v > 1e12 else last_v), tz=timezone.utc
                        ).strftime("%Y-%m-%d %H:%M")
            except Exception:  # noqa: BLE001
                pass
        out[name] = {"exists": True, "last": last_s, "age_h": round(age_h, 1) if not pd.isna(age_h) else None,
                     "stale": stale}
    return out


if __name__ == "__main__":
    import json
    print(json.dumps(health_report(), ensure_ascii=False, indent=2))
