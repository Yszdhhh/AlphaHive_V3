r"""186_spx_high_alt_lag.py — SPX 52 周新高 → 山寨篮子滞后抬升（跨市场传导 α）。

假设：SPX 创 52 周新高（风险偏好极强）后 24-72h，山寨（高 beta 风险资产）滞后抬升。
事件：SPX 收盘创 52 周新高（本地 macro SP500 或 Pyth SPY）。
观察：事件后 24h/72h 山寨等权篮子收益 vs 随机基线。
数据：macro/SP500.parquet（2004+）+ coinglass klines。
输出：reports/spx_high_alt_lag.md
"""
from __future__ import annotations

import importlib.util
import sys
from datetime import datetime, timezone
from pathlib import Path

import numpy as np
import pandas as pd

PROJECT_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(PROJECT_ROOT))

_spec = importlib.util.spec_from_file_location(
    "m113", str(PROJECT_ROOT / "scripts" / "113_washout_settle_study.py"))
m113 = importlib.util.module_from_spec(_spec)
sys.modules["m113"] = m113
_spec.loader.exec_module(m113)

from harness.lib.event_study import bootstrap_ci  # noqa: E402

REPORT = PROJECT_ROOT / "reports" / "spx_high_alt_lag.md"
MACRO = Path(r"C:\Users\10639\Desktop\🔒 加密资产\coinglass_db\macro")
LO_MS = int(pd.Timestamp("2022-01-01", tz="UTC").timestamp() * 1000)
HI_MS = int(pd.Timestamp("2026-06-30", tz="UTC").timestamp() * 1000)
MIN_EVENTS = 20
SEED = 2026
COOLDOWN_DAYS = 5


def main() -> int:
    p = MACRO / "SP500.parquet"
    if not p.exists():
        print("SP500 缺失")
        return 1
    d = pd.read_parquet(p)
    idx = pd.to_datetime(d.index) if not isinstance(d.index, pd.DatetimeIndex) else d.index
    spx = pd.Series(pd.to_numeric(d["close"], errors="coerce").to_numpy(), index=idx).dropna()
    hi52 = spx.rolling(252, min_periods=120).max()
    new_high = spx >= hi52 * 0.999
    # 事件：新高日（5 天冷却去重）
    events = []
    last = None
    for dt, v in new_high.items():
        if v and (last is None or (dt - last).days >= COOLDOWN_DAYS):
            events.append(dt)
            last = dt
    events = [e for e in events if e >= pd.Timestamp("2022-01-01") and e <= pd.Timestamp("2026-06-30")]
    print(f"SPX 新高事件（冷却 {COOLDOWN_DAYS}d）: {len(events)}")

    symbols = m113.load_universe_symbols()
    ctxs = m113.load_price_ctx(symbols)
    # 事件后山寨篮子收益（等权）
    rows = []
    for t in events:
        t_ms = int(t.timestamp() * 1000)
        rs24, rs72 = [], []
        for sym, ctx in ctxs.items():
            axis = ctx.index.to_numpy(dtype=np.int64)
            close = ctx["close"].to_numpy(dtype=float)
            pos = int(np.searchsorted(axis, t_ms, side="right")) - 1
            if pos < 0 or pos + 72 >= len(close):
                continue
            r24 = (close[pos + 24] / close[pos] - 1) * 100
            r72 = (close[pos + 72] / close[pos] - 1) * 100
            if np.isfinite(r24) and np.isfinite(r72):
                rs24.append(r24)
                rs72.append(r72)
        if len(rs24) >= 10:
            rows.append({"t": t_ms, "b24": np.mean(rs24), "b72": np.mean(rs72)})
    df = pd.DataFrame(rows)
    n = len(df)
    print(f"有效事件 {n}")

    # 基线：随机时间点篮子
    rng = np.random.default_rng(SEED)
    base_t = np.sort(rng.integers(LO_MS, HI_MS, size=3000, dtype=np.int64))
    brows = []
    for t in base_t:
        rs24 = []
        for sym, ctx in ctxs.items():
            axis = ctx.index.to_numpy(dtype=np.int64)
            close = ctx["close"].to_numpy(dtype=float)
            pos = int(np.searchsorted(axis, int(t), side="right")) - 1
            if pos < 0 or pos + 24 >= len(close):
                continue
            r = (close[pos + 24] / close[pos] - 1) * 100
            if np.isfinite(r):
                rs24.append(r)
        if len(rs24) >= 10:
            brows.append(np.mean(rs24))
    b24 = np.array(brows)

    lines = ["# SPX 新高 → 山寨滞后（186）\n",
             f"- 生成：{datetime.now(timezone.utc):%Y-%m-%d %H:%M UTC}",
             f"- 事件：SPX 52 周新高（{n} 次，5 天冷却）；观察：山寨等权篮子 24h/72h\n",
             "| 窗口 | n | 篮子均值 | 超额 | CI | 判定 |",
             "|---|---|---:|---:|---:|---|"]
    for col, h in [("b24", "24h"), ("b72", "72h")]:
        r = df[col].to_numpy(dtype=float)
        ci = bootstrap_ci(r, b24, n_boot=1000, alpha=0.05, seed=SEED)
        verdict = ("样本不足" if n < MIN_EVENTS else
                   "GO_LONG" if ci["ci_lo"] > 0 else
                   "GO_SHORT" if ci["ci_hi"] < 0 else "NO_GO")
        lines.append(f"| {h} | {n} | {r.mean():+.2f}% | {ci['mean_diff']:+.2f}% "
                     f"| [{ci['ci_lo']:+.2f}, {ci['ci_hi']:+.2f}] | **{verdict}** |")
        print(f"[186] {h}: n={n} 篮子 {r.mean():+.2f}% 超额 {ci['mean_diff']:+.2f}% {verdict}")
    lines.extend(["\n## 解读\n",
                  "- 超额显著正 → SPX 新高后山寨滞后抬升（跨市场传导 α，s017 候选）。",
                  "- NO_GO → 传导已被即时定价（SPX 与加密同步，无滞后窗口）。"])
    REPORT.parent.mkdir(parents=True, exist_ok=True)
    REPORT.write_text("\n".join(lines) + "\n", encoding="utf-8")
    print(f"wrote {REPORT}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
