r"""188_vol_calm_breakout.py — 波动率平静长度 → 爆发（波动率聚集结构 α）。

假设：BTC 低波动（平静）持续越久，随后的波动爆发越剧烈（波动率聚集），
且爆发方向可测（平静期资金累积 → 方向？）。
事件：BTC 20d 波动率 < 历史 25 分位（平静）的第 N 天（平静长度 3/7/14 天）。
观察：平静结束后 24h/72h BTC 收益（方向）+ 波动率变化（幅度）。
输出：reports/vol_calm_breakout.md
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

REPORT = PROJECT_ROOT / "reports" / "vol_calm_breakout.md"
MIN_EVENTS = 20
SEED = 2026


def main() -> int:
    p = m113.COINGLASS_RAW1H / "klines" / "BTCUSDT.parquet"
    df = pd.read_parquet(p, columns=["open_time", "close"])
    ts = pd.to_numeric(df["open_time"], errors="coerce").to_numpy(dtype=np.int64)
    cl = pd.to_numeric(df["close"], errors="coerce").to_numpy(dtype=float)
    s = pd.Series(cl, index=pd.Index(ts))
    s = s[~s.index.duplicated(keep="last")].sort_index()
    s.index = pd.to_datetime(s.index, unit="ms", utc=True).tz_localize(None)
    daily = s.resample("D").last().dropna()
    ret = daily.pct_change()
    vol20 = ret.rolling(20).std()
    q25 = vol20.rolling(1095, min_periods=300).quantile(0.25)
    calm = vol20 < q25
    print(f"BTC 日线 {len(daily)} | 平静日占比 {calm.mean():.1%}")

    # 平静连续长度事件（平静结束日 = 从平静转非平静）
    calm_arr = calm.fillna(False).to_numpy()
    idx = daily.index.to_numpy()
    events = []
    run = 0
    for i, c in enumerate(calm_arr):
        if c:
            run += 1
        else:
            if run >= 3:
                events.append((idx[i], run))  # 平静结束日 + 长度
            run = 0
    print(f"平静段（≥3 天）结束事件: {len(events)}")

    rows = []
    for t_end, run_len in events:
        pos = daily.index.searchsorted(t_end)
        if pos + 72 >= len(daily) or pos < 10:
            continue
        r24 = (daily.iloc[pos + 1] / daily.iloc[pos] - 1) * 100
        r72 = (daily.iloc[pos + 3] / daily.iloc[pos] - 1) * 100
        # 爆发幅度：结束后 5 天波动率 vs 平静期波动率
        vol_after = ret.iloc[pos + 1:pos + 6].std() * 100
        vol_before = ret.iloc[pos - 20:pos].std() * 100
        if np.isfinite(r24) and np.isfinite(r72):
            rows.append({"t": int(pd.Timestamp(t_end).timestamp() * 1000), "len": run_len,
                         "r24": r24, "r72": r72,
                         "vol_ratio": vol_after / vol_before if vol_before > 0 else np.nan})
    ev = pd.DataFrame(rows)
    print(f"有效事件 {len(ev)}")

    # 基线：随机日
    rng = np.random.default_rng(SEED)
    base_idx = rng.integers(10, len(daily) - 10, size=3000)
    b24 = (daily.iloc[base_idx + 1].to_numpy() / daily.iloc[base_idx].to_numpy() - 1) * 100

    lines = ["# 波动率平静长度 → 爆发（188）\n",
             f"- 生成：{datetime.now(timezone.utc):%Y-%m-%d %H:%M UTC}",
             f"- 平静段（≥3 天）结束事件 {len(ev)}；基线随机日\n",
             "| 组 | n | 24h 均值 | 超额 | CI | 72h 均值 | 爆发幅度比 | 判定 |",
             "|---|---|---:|---:|---:|---:|---:|---|"]

    def row(label: str, g: pd.DataFrame) -> None:
        n = len(g)
        if n < MIN_EVENTS:
            lines.append(f"| {label} | {n} | - | - | - | - | - | 样本不足 |")
            print(f"[188] {label}: n={n} 样本不足")
            return
        r = g["r24"].to_numpy(dtype=float)
        ci = bootstrap_ci(r, b24, n_boot=1000, alpha=0.05, seed=SEED)
        vr = g["vol_ratio"].median()
        verdict = ("样本不足" if n < MIN_EVENTS else
                   "GO_LONG" if ci["ci_lo"] > 0 else
                   "GO_SHORT" if ci["ci_hi"] < 0 else "NO_GO")
        lines.append(f"| {label} | {n} | {r.mean():+.2f}% | {ci['mean_diff']:+.2f}% "
                     f"| [{ci['ci_lo']:+.2f}, {ci['ci_hi']:+.2f}] | {g['r72'].mean():+.2f}% "
                     f"| {vr:.1f}x | **{verdict}** |")
        print(f"[188] {label}: n={n} ex24={ci['mean_diff']:+.2f}% vol_ratio={vr:.1f}x {verdict}")

    row("平静≥3 天结束", ev)
    row("  平静≥7 天", ev[ev["len"] >= 7])
    row("  平静≥14 天", ev[ev["len"] >= 14])

    lines.extend(["\n## 解读\n",
                  "- 爆发幅度比 > 2 → 波动率聚集确认（平静越长爆发越猛）——结构性事实。",
                  "- 24h 超额显著正/负 → 平静结束有方向预测力（s018 候选）；NO_GO → 方向不可测但幅度可测（波动率产品/仓位工具）。"])
    REPORT.parent.mkdir(parents=True, exist_ok=True)
    REPORT.write_text("\n".join(lines) + "\n", encoding="utf-8")
    print(f"wrote {REPORT}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
