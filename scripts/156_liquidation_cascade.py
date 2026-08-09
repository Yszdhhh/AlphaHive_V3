r"""156_liquidation_cascade.py — 市场级清算风暴事件（机制锚场景 #2）。

背景：131 只测单币 liq_short_z。本脚本测【市场级】清算风暴（全池 24h 总清算激增）
后的山寨篮子方向——清算级联是否可预测（传染后超卖 vs 流动性螺旋继续跌）。

数据：coinglass liquidation（2024-06-06→2026-06-23，66 symbols，131 同源）。
事件：全池 24h 总清算（long+short 求和）的 30d z-score > 2（72h 冷却）。
观察：事件后 24h/72h/168h 山寨等权篮子收益（无前视：篮子 = 事件时点后 forward 等权）。
基线：随机时间点篮子收益（bootstrap 95% CI）。
双向检验：GO_LONG（超卖反弹）/ GO_SHORT（流动性螺旋）。

输出：reports/liquidation_cascade.md
用法：python scripts/156_liquidation_cascade.py
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

REPORT = PROJECT_ROOT / "reports" / "liquidation_cascade.md"
LO_MS = int(pd.Timestamp("2024-06-06", tz="UTC").timestamp() * 1000)
HI_MS = int(pd.Timestamp("2026-06-23", tz="UTC").timestamp() * 1000)
Z_THR = 2.0
COOLDOWN_H = 72
MIN_EVENTS = 20
SEED = 2026


def main() -> int:
    symbols = m113.load_universe_symbols()
    ctxs = m113.load_price_ctx(symbols)
    # 市场总清算序列（24h 累计，跨币求和）
    liq_series: pd.Series | None = None
    for sym in symbols:
        p = m113.COINGLASS_RAW1H / "liquidation" / f"{sym}.parquet"
        if not p.exists():
            continue
        df = pd.read_parquet(p)
        if not {"time", "long_liquidation_usd", "short_liquidation_usd"}.issubset(df.columns):
            continue
        ts = pd.to_numeric(df["time"], errors="coerce").to_numpy(dtype=np.int64)
        tot = (pd.to_numeric(df["long_liquidation_usd"], errors="coerce").fillna(0)
               + pd.to_numeric(df["short_liquidation_usd"], errors="coerce").fillna(0)).to_numpy(dtype=float)
        s = pd.Series(tot, index=pd.Index(ts))
        s = s[~s.index.duplicated(keep="last")].sort_index()
        liq_series = s if liq_series is None else liq_series.add(s, fill_value=0)
    liq24 = liq_series.rolling(24).sum()
    z = m113.rolling_z(liq24, 720)
    print(f"清算覆盖 {len(symbols)} symbols | 序列 {len(liq24)} bars")

    axis = liq24.index.to_numpy(dtype=np.int64)
    zvals = z.to_numpy(dtype=float)
    fired = np.isfinite(zvals) & (zvals > Z_THR)
    events: list[int] = []
    last = -10**18
    for i in np.flatnonzero(fired):
        t = int(axis[i])
        if t - last >= COOLDOWN_H * 3_600_000:
            events.append(t)
            last = t
    events = [t for t in events if LO_MS <= t <= HI_MS]
    print(f"清算风暴事件（z>{Z_THR}，72h 冷却）: {len(events)}")

    # 篮子收益：事件后各 symbol forward 收益等权
    def basket_ret(ev_ts: list[int], ctxs: dict) -> pd.DataFrame:
        rows = []
        for sym, ctx in ctxs.items():
            caxis = ctx.index.to_numpy(dtype=np.int64)
            close = ctx["close"].to_numpy(dtype=float)
            for t in ev_ts:
                pos = int(np.searchsorted(caxis, t, side="right")) - 1
                if pos < 0 or pos + 168 >= len(close):
                    continue
                r24 = (close[pos + 24] / close[pos] - 1) * 100.0
                r72 = (close[pos + 72] / close[pos] - 1) * 100.0
                r168 = (close[pos + 168] / close[pos] - 1) * 100.0
                if np.isfinite(r24) and np.isfinite(r168):
                    rows.append({"t": t, "sym": sym, "r24": r24, "r72": r72, "r168": r168})
        return pd.DataFrame(rows)

    ev = pd.DataFrame(basket_ret(events, ctxs))
    n_ev = ev["t"].nunique() if not ev.empty else 0
    print(f"事件篮子行 {len(ev)}，唯一事件 {n_ev}")

    # 基线：随机时间点篮子（等权）
    rng = np.random.default_rng(SEED)
    base_t = np.sort(rng.integers(LO_MS, HI_MS, size=2000, dtype=np.int64))
    bdf = pd.DataFrame(basket_ret(base_t.tolist(), ctxs))
    b_basket = bdf.groupby("t")[["r24", "r168"]].mean()
    b24 = b_basket["r24"].dropna().to_numpy()
    b168 = b_basket["r168"].dropna().to_numpy()

    lines = ["# 市场级清算风暴事件（156，机制锚 #2）\n",
             f"- 生成：{datetime.now(timezone.utc):%Y-%m-%d %H:%M UTC}",
             f"- 事件：全池 24h 总清算（long+short）30d z-score > {Z_THR}，72h 冷却，共 {n_ev} 次",
             f"- 观察：事件后 24h/72h/168h 山寨等权篮子（跨 symbol 等权均值）",
             "- 基线：随机时间点篮子（bootstrap 95% CI，seed=2026）\n",
             "| 时点 | n 事件 | 篮子 24h 均值 | 24h 超额 | CI | 篮子 168h 均值 | 168h 超额 | 168h CI | 判定 |",
             "|---|---|---:|---:|---:|---:|---:|---:|---|"]

    for label, col, br, hor in [("24h", "r24", b24, "24h"), ("168h", "r168", b168, "168h")]:
        vals = ev.groupby("t")[col].mean().dropna()
        n = len(vals)
        if n == 0:
            continue
        ci = bootstrap_ci(vals.to_numpy(), br, n_boot=1000, alpha=0.05, seed=SEED)
        verdict = ("样本不足" if n < MIN_EVENTS else
                   "GO_LONG" if ci["ci_lo"] > 0 else
                   "GO_SHORT" if ci["ci_hi"] < 0 else "NO_GO")
        if hor == "24h":
            lines.append(f"| {hor} | {n} | {vals.mean():+.2f}% | {ci['mean_diff']:+.2f}% "
                         f"| [{ci['ci_lo']:+.2f}, {ci['ci_hi']:+.2f}] | - | - | - | **{verdict}** |")
        else:
            # 找到 24h 行补 168h 列
            lines[-1] = lines[-1].replace("| - | - | - |", f"| {vals.mean():+.2f}% | {ci['mean_diff']:+.2f}% | [{ci['ci_lo']:+.2f}, {ci['ci_hi']:+.2f}] |")
            lines[-1] = lines[-1].replace(f"**{verdict}**", f"**{verdict}**")
        print(f"[156] {hor}: n={n} 超额 {ci['mean_diff']:+.2f}% {verdict}")

    lines.extend(["\n## 解读\n",
                   "- GO_LONG → 清算风暴后市场级超卖反弹（级联末端 = 底部信号）。",
                   "- GO_SHORT → 流动性螺旋继续（级联传染有惯性，与 151 单币惯性一致）。",
                   "- NO_GO/样本不足 → 市场级清算无方向预测力（级联已一步到位）。",
                   "- 事件数：2024-06→2026-06 约 24 个月，z>2 风暴约每 1-3 个月一次 → n 预计 10-25。"])
    REPORT.parent.mkdir(parents=True, exist_ok=True)
    REPORT.write_text("\n".join(lines) + "\n", encoding="utf-8")
    print(f"wrote {REPORT}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
