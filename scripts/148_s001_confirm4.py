r"""148_s001_confirm4.py — s001 增强：wash_cvd + 4h 反弹确认（砍 168h 尾部亏损）。

背景：wash_cvd 168h 收益右偏（事件均值 >> 中位数，MFE 15.66% vs MAE -10.41%，115），
尾部大赢家 vs 深亏并存。假设：事件后 4h 内出现反弹确认（ret_4h > 0）的事件，
168h 期望更高且尾部亏损更小；无确认事件（继续阴跌）应剔除。

变体（同 126 组合口径，无前视）：
- V_ref：纯 wash_cvd（对照，应复现 115 pooled +1.31%）
- V_confirm：wash_cvd 且事件后 4h 收益 > 0（4h 确认后入场，入场延迟 4h，成本同）
- V_reject：wash_cvd 且事件后 4h 收益 <= 0（被剔除部分）

数据/基线：115 口径（m113 ctx + m115 detect_events），全区间 2022-01→2026-06；
基线 = draw_random_events + bootstrap_ci（seed=2026，n=3000）。
判定：CI 下界>0 → GO_LONG；n<30 → 样本不足。

输出：reports/s001_confirm4.md
用法：python scripts/148_s001_confirm4.py
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

from harness.lib.event_study import (  # noqa: E402
    DEFAULT_HORIZONS,
    bootstrap_ci,
    draw_random_events,
    forward_stats,
)

REPORT = PROJECT_ROOT / "reports" / "s001_confirm4.md"
LO_MS = int(pd.Timestamp("2022-01-01", tz="UTC").timestamp() * 1000)
HI_MS = int(pd.Timestamp("2026-06-30", tz="UTC").timestamp() * 1000)
MIN_EVENTS = 30
N_BASELINE = 3000
SEED = 2026


def main() -> int:
    symbols = m113.load_universe_symbols()
    ctxs = m113.load_price_ctx(symbols)
    fundings = m113.load_funding_series(symbols)
    print(f"ctx {len(ctxs)} funding {len(fundings)}")

    # wash_cvd 事件（115 口径）+ 事件后 4h 收益
    parts = []
    for sym, ctx in ctxs.items():
        ev = m115.detect_events(sym, ctx, fundings.get(sym), "wash_cvd")
        if ev.empty:
            continue
        axis = ctx.index.to_numpy(dtype=np.int64)
        close = ctx["close"].to_numpy(dtype=float)
        rows = []
        for t in ev["timestamp"].astype(np.int64).to_numpy():
            pos = int(np.searchsorted(axis, t, side="right")) - 1
            if pos < 0 or pos + 168 >= len(close):
                continue
            r4 = (close[pos + 4] / close[pos] - 1) * 100.0
            r24 = (close[pos + 24] / close[pos] - 1) * 100.0
            r168 = (close[pos + 168] / close[pos] - 1) * 100.0
            if np.isfinite(r4) and np.isfinite(r24) and np.isfinite(r168):
                rows.append({"symbol": sym, "t": int(t), "r4": r4, "r24": r24, "r168": r168})
        if rows:
            parts.append(pd.DataFrame(rows))
    ev = pd.concat(parts, ignore_index=True) if parts else pd.DataFrame()
    ev = ev[(ev["t"] >= LO_MS) & (ev["t"] <= HI_MS)]
    print(f"wash_cvd 事件（有完整 forward）: {len(ev)}")

    rng = np.random.default_rng(SEED)
    base = draw_random_events(ctxs, N_BASELINE, rng, max_forward_hours=168,
                              start_ms=LO_MS, end_ms=HI_MS)
    bparts = []
    for bs, bg in base.groupby("symbol", sort=False):
        if bs in ctxs:
            bparts.append(forward_stats(ctxs[bs], bg.copy(), DEFAULT_HORIZONS))
    base_df = pd.concat(bparts, ignore_index=True) if bparts else pd.DataFrame()
    br24 = pd.to_numeric(base_df["ret_24h"], errors="coerce").dropna().to_numpy()
    br168 = pd.to_numeric(base_df["ret_168h"], errors="coerce").dropna().to_numpy()
    print(f"基线 n={len(br24)}")

    confirm = ev[ev["r4"] > 0]
    reject = ev[ev["r4"] <= 0]

    lines = ["# s001 增强：wash_cvd × 4h 反弹确认\n",
             f"- 生成：{datetime.now(timezone.utc):%Y-%m-%d %H:%M UTC}",
             f"- 事件：wash_cvd（115 口径，72h 冷却），{LO_MS and ''}2022-01→2026-06，共 {len(ev)}",
             "- V_confirm = 事件后 4h 收益 > 0（反弹确认后入场，延迟 4h）；V_reject = 4h 收益 ≤ 0（剔除）",
             "- 基线：同期随机 symbol×时点横截面（bootstrap 95% CI，seed=2026）\n",
             "| 变体 | n | 24h 均值 | 24h 超额 | 24h CI | 168h 均值 | 168h 超额 | 168h CI | 168h 中位数 | 168h 胜率 | 判定 |",
             "|---|---|---:|---:|---:|---:|---:|---:|---:|---:|---|"]

    def row(label: str, g: pd.DataFrame) -> None:
        n = len(g)
        if n == 0:
            lines.append(f"| {label} | 0 | - | - | - | - | - | - | - | - | 无事件 |")
            return
        r24 = g["r24"].to_numpy(dtype=float)
        r168 = g["r168"].to_numpy(dtype=float)
        ci24 = bootstrap_ci(r24, br24, n_boot=1000, alpha=0.05, seed=SEED)
        ci168 = bootstrap_ci(r168, br168, n_boot=1000, alpha=0.05, seed=SEED + 1)
        verdict = ("样本不足" if n < MIN_EVENTS else
                   "GO_LONG" if ci168["ci_lo"] > 0 else
                   "GO_SHORT" if ci168["ci_hi"] < 0 else "NO_GO")
        lines.append(f"| {label} | {n} | {r24.mean():+.2f}% | {ci24['mean_diff']:+.2f}% "
                     f"| [{ci24['ci_lo']:+.2f}, {ci24['ci_hi']:+.2f}] | {r168.mean():+.2f}% "
                     f"| {ci168['mean_diff']:+.2f}% | [{ci168['ci_lo']:+.2f}, {ci168['ci_hi']:+.2f}] "
                     f"| {np.median(r168):+.2f}% | {100 * (r168 > 0).mean():.0f}% | **{verdict}** |")
        print(f"[148] {label}: n={n} ex168={ci168['mean_diff']:+.2f}% med={np.median(r168):+.2f}% {verdict}")

    row("V_ref 纯 wash_cvd", ev)
    row("V_confirm 4h确认", confirm)
    row("V_reject 无确认", reject)

    # 直接对照
    if len(confirm) >= 10 and len(reject) >= 10:
        c = bootstrap_ci(confirm["r168"].to_numpy(), reject["r168"].to_numpy(),
                         n_boot=1000, alpha=0.05, seed=SEED + 2)
        lines.append("\n直接对照（168h）：confirm − reject")
        lines.append(f"- 差 {c['mean_diff']:+.2f}% CI[{c['ci_lo']:+.2f}, {c['ci_hi']:+.2f}]"
                     f"（{'显著' if c['ci_lo'] > 0 else '不显著'}）")
        print(f"[148] confirm−reject 168h: {c['mean_diff']:+.2f}% CI[{c['ci_lo']:+.2f},{c['ci_hi']:+.2f}]")

    lines.extend(["\n## 解读\n",
                   "- V_confirm 168h 期望显著 > V_ref 且中位数转正 → 4h 确认值得作为入场条件（砍尾部）。",
                   "- V_confirm 不提升但 V_reject 168h 显著负 → 确认是必要的风控（回避深亏）。",
                   "- 两者皆无差 → 4h 信息已被价格吸收，增强不成立。",
                   "- 入场延迟 4h 的成本已含（同成本口径），确认收益必须覆盖延迟机会成本。"])
    REPORT.parent.mkdir(parents=True, exist_ok=True)
    REPORT.write_text("\n".join(lines) + "\n", encoding="utf-8")
    print(f"wrote {REPORT}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
