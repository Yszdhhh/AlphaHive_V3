r"""180_stop_loss_validation.py — B2：账户 B 风控参数的历史路径验证。

账户 B 的 -10% 止损/trailing 50% 来自老项目（chassis_engine/cluster1_live_sim），
从未在 wash_cvd 事件上验证过。本脚本路径模拟对比：
- 无止损（对照，当前统计口径）：持有 168h
- 止损 -10%：事件后逐 bar 检查 close ≤ entry×0.90 → 触发即退出（记 -10%）
- trailing 50%：峰值回落 50% 退出
- 止损+trailing 组合

判定：止损是否改善 168h 期望/中位数/胜率/最大单笔亏损（期望提升 or 尾部减少）。

输出：reports/stop_loss_validation.md
用法：python scripts/180_stop_loss_validation.py
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
_spec2 = importlib.util.spec_from_file_location(
    "m115", str(PROJECT_ROOT / "scripts" / "115_short_squeeze_combo_study.py"))
m115 = importlib.util.module_from_spec(_spec2)
sys.modules["m115"] = m115
_spec2.loader.exec_module(m115)

from harness.lib.event_study import DEFAULT_HORIZONS, forward_stats  # noqa: E402

REPORT = PROJECT_ROOT / "reports" / "stop_loss_validation.md"
LO_MS = int(pd.Timestamp("2022-01-01", tz="UTC").timestamp() * 1000)
HI_MS = int(pd.Timestamp("2026-06-30", tz="UTC").timestamp() * 1000)
COST = 0.0027
HOLD = 168
STOP = -0.10
TRAIL = -0.50


def simulate(close: np.ndarray, pos: int, mode: str) -> float:
    """事件后路径模拟，返回收益（含入场成本）。"""
    if pos + HOLD >= len(close):
        return np.nan
    entry = close[pos]
    net_entry = entry * (1 + COST)
    if mode == "hold":
        exit_px = close[pos + HOLD]
        return exit_px / net_entry - 1
    peak = entry
    for i in range(pos + 1, pos + HOLD + 1):
        c = close[i]
        peak = max(peak, c)
        if mode in ("stop", "both") and c <= entry * (1 + STOP):
            return close[i] / net_entry - 1
        if mode in ("trail", "both") and c <= peak * (1 + TRAIL):
            return close[i] / net_entry - 1
    return close[pos + HOLD] / net_entry - 1


def main() -> int:
    symbols = m113.load_universe_symbols()
    ctxs = m113.load_price_ctx(symbols)
    fundings = m113.load_funding_series(symbols)
    ev_parts = []
    for sym, ctx in ctxs.items():
        ev = m115.detect_events(sym, ctx, fundings.get(sym), "wash_cvd")
        if not ev.empty:
            ev_parts.append(ev)
    events = pd.concat(ev_parts, ignore_index=True) if ev_parts else pd.DataFrame(
        columns=["symbol", "timestamp"])
    events = events[(events["timestamp"] >= LO_MS) & (events["timestamp"] <= HI_MS)].copy()

    rows = []
    for sym, g in events.groupby("symbol", sort=False):
        ctx = ctxs[sym]
        axis = ctx.index.to_numpy(dtype=np.int64)
        close = ctx["close"].to_numpy(dtype=float)
        for t in g["timestamp"].astype(np.int64).to_numpy():
            pos = int(np.searchsorted(axis, t, side="right")) - 1
            if pos < 0:
                continue
            r = {"symbol": sym, "t": int(t)}
            for mode in ["hold", "stop", "trail", "both"]:
                r[mode] = simulate(close, pos, mode)
            if np.isfinite(r["hold"]):
                rows.append(r)
    df = pd.DataFrame(rows)
    print(f"事件路径 {len(df)}")

    lines = ["# 账户 B 风控参数路径验证（180，B2）\n",
             f"- 生成：{datetime.now(timezone.utc):%Y-%m-%d %H:%M UTC}",
             f"- 事件：wash_cvd（115），{len(df)} 个路径；成本 {COST * 1e4:.0f}bps 单边",
             f"- 止损 -10% / trailing 峰值回落 50% / 持有 168h\n",
             "| 模式 | 均值 | 中位数 | 胜率 | p5 | p95 | 最大亏损 | 触发率 |",
             "|---|---:|---:|---:|---:|---:|---:|---|"]

    for mode, desc in [("hold", "无止损（对照）"), ("stop", "止损 -10%"),
                       ("trail", "trailing 50%"), ("both", "止损+trailing")]:
        r = df[mode].to_numpy(dtype=float)
        r = r[np.isfinite(r)]
        if mode == "hold":
            trig = 0.0
        elif mode == "stop":
            trig = float((df[mode] <= STOP).mean())
        elif mode == "trail":
            trig = float((df[mode] < df["hold"] - 0.001).mean())  # 近似：提前退出
        else:
            trig = float((df[mode] <= STOP).mean())
        lines.append(f"| {desc} | {r.mean() * 100:+.2f}% | {np.median(r) * 100:+.2f}% "
                     f"| {100 * (r > 0).mean():.0f}% | {np.percentile(r, 5) * 100:+.1f}% "
                     f"| {np.percentile(r, 95) * 100:+.1f}% | {r.min() * 100:+.1f}% | {trig:.0%} |")
        print(f"[180] {desc}: 均值 {r.mean() * 100:+.2f}% 中位 {np.median(r) * 100:+.2f}% "
              f"胜率 {100 * (r > 0).mean():.0f}% p5 {np.percentile(r, 5) * 100:+.1f}%")

    lines.extend(["\n## 解读\n",
                  "- 止损模式期望 ≥ 对照 → 风控参数有效（减少尾部或提升期望）。",
                  "- 止损期望 < 对照但最大亏损显著收窄 → 尾部保护价值（可作组合级配置）。",
                  "- 两者皆无改善 → -10% 止损在 wash_cvd 事件上是负优化（V 型反弹被砍），需调参或弃用。"])
    REPORT.parent.mkdir(parents=True, exist_ok=True)
    REPORT.write_text("\n".join(lines) + "\n", encoding="utf-8")
    print(f"wrote {REPORT}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
