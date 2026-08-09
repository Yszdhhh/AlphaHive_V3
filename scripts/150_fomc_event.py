r"""150_fomc_event.py — s007：指数事件驱动 — FOMC 决议日后的 SPY/QQQ 反应。

假设（E-C 信息/事件驱动）：FOMC 利率决议（美东 14:00）是月级最重要宏观事件，
决议后 24h（跨决议瞬间 + 次日交易日）存在系统性反应偏差（post-FOMC drift）。

数据：Pyth SPY/QQQ 小时级（美盘时段，已缓存 data/pyth_raw/）。
事件：FOMC 决议日（官方预定日程，提前一年公布；UTC 18:00 ≈ 美东 14:00 夏令时）。
窗口：2022-01 → 2026-07（决议日 UTC 18:00 起算 24/72/168 根美盘 bar）。
基线：同资产随机时间点（bootstrap 95% CI，seed=2026）。
诚实边界：事件 n≈36（8 次/年 × 4.5 年）→ 大概率样本不足，方向性观察为主；
2022-24（加息周期）vs 2025-26（宽松/暂停）分开看 regime 差异。

输出：reports/fomc_event.md
用法：python scripts/150_fomc_event.py
"""
from __future__ import annotations

import sys
from datetime import datetime, timezone
from pathlib import Path

import numpy as np
import pandas as pd

PROJECT_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(PROJECT_ROOT))

from harness.lib.event_study import bootstrap_ci  # noqa: E402

REPORT = PROJECT_ROOT / "reports" / "fomc_event.md"
PYTH_DIR = PROJECT_ROOT / "data" / "pyth_raw"

# FOMC 决议日（官方日程，提前一年公布；美东 14:00 = UTC 18:00 夏令时）
FOMC_DATES = [
    "2022-01-26", "2022-03-16", "2022-05-04", "2022-06-15", "2022-07-27",
    "2022-09-21", "2022-11-02", "2022-12-14",
    "2023-02-01", "2023-03-22", "2023-05-03", "2023-06-14", "2023-07-26",
    "2023-09-20", "2023-11-01", "2023-12-13",
    "2024-01-31", "2024-03-20", "2024-05-01", "2024-06-12", "2024-07-31",
    "2024-09-18", "2024-11-07", "2024-12-18",
    "2025-01-29", "2025-03-19", "2025-05-07", "2025-06-18", "2025-07-30",
    "2025-09-17", "2025-10-29", "2025-12-10",
    "2026-01-28", "2026-03-18", "2026-04-29", "2026-06-17", "2026-07-29",
]
ASSETS = {
    "EQUITY.US.SPY_USD.parquet": "标普 SPY",
    "EQUITY.US.QQQ_USD.parquet": "纳指 QQQ",
    "EQUITY.US.NVDA_USD.parquet": "英伟达 NVDA",
}
EVENT_UTC_H = 18  # 决议 UTC 18:00（夏令时；冬令时 19:00，误差 1h 标注）


def main() -> int:
    ev_ts = [int(pd.Timestamp(d, tz="UTC").timestamp()) + EVENT_UTC_H * 3600
             for d in FOMC_DATES]
    print(f"FOMC 事件 {len(ev_ts)}（{FOMC_DATES[0]} → {FOMC_DATES[-1]}）")

    lines = ["# s007：FOMC 决议后 SPY/QQQ/NVDA 反应\n",
             f"- 生成：{datetime.now(timezone.utc):%Y-%m-%d %H:%M UTC}",
             f"- 事件：FOMC 决议日 UTC 18:00（美东 14:00），{len(ev_ts)} 次（官方预定日程，2022-01→2026-07）",
             "- ⚠️ 冬令时实际为 19:00 UTC，统一 18:00 起算（误差 1h，标注）",
             "- 收益：决议后 24/72/168 根美盘 bar（24 ≈ 跨 3 交易日，含决议瞬间跳变 + 次日）",
             "- 基线：同资产随机时间点（bootstrap 95% CI，seed=2026）\n",
             "| 资产 | n | 24h 均值 | 24h 超额 | 24h CI | 72h 超额 | 168h 超额 | 判定 |",
             "|---|---|---:|---:|---:|---:|---:|---|"]

    rng = np.random.default_rng(2026)
    for fname, name in ASSETS.items():
        p = PYTH_DIR / fname
        if not p.exists():
            lines.append(f"| {name} | 数据缺失 | - | - | - | - | - | - |")
            continue
        d = pd.read_parquet(p)
        sts = d["t"].to_numpy(dtype=np.int64)
        close = d["c"].to_numpy(dtype=float)
        fwd = []
        for t in ev_ts:
            pos = int(np.searchsorted(sts, t, side="right")) - 1
            if pos < 0 or pos + 168 >= len(close):
                continue
            fwd.append({"t": t,
                        "r24": (close[pos + 24] / close[pos] - 1) * 100.0,
                        "r72": (close[pos + 72] / close[pos] - 1) * 100.0,
                        "r168": (close[pos + 168] / close[pos] - 1) * 100.0})
        f = pd.DataFrame(fwd)
        n = len(f)
        if n == 0:
            lines.append(f"| {name} | 0 | - | - | - | - | - | - | 无重叠 |")
            continue
        lo, hi = int(f["t"].min()), int(f["t"].max())
        base_t = np.sort(rng.integers(lo, hi + 1, size=3000, dtype=np.int64))
        bf = []
        for t in base_t:
            pos = int(np.searchsorted(sts, t, side="right")) - 1
            if pos < 0 or pos + 24 >= len(close):
                continue
            bf.append((close[pos + 24] / close[pos] - 1) * 100.0)
        base24 = np.array([x for x in bf if np.isfinite(x)])
        ci = bootstrap_ci(f["r24"].to_numpy(), base24, n_boot=1000, alpha=0.05, seed=2026)
        verdict = ("样本不足" if n < 20 else
                   "GO_LONG" if ci["ci_lo"] > 0 else
                   "GO_SHORT" if ci["ci_hi"] < 0 else "NO_GO")
        lines.append(f"| {name} | {n} | {f['r24'].mean():+.2f}% | {ci['mean_diff']:+.2f}% "
                     f"| [{ci['ci_lo']:+.2f}, {ci['ci_hi']:+.2f}] | {f['r72'].mean():+.2f}% "
                     f"| {f['r168'].mean():+.2f}% | **{verdict}** |")
        print(f"[150] {name}: n={n} ex24={ci['mean_diff']:+.2f}% {verdict}")
        # regime 分解
        for label, lo_d, hi_d in [("加息期 2022-24", "2022-01-01", "2024-12-31"),
                                  ("宽松期 2025-26", "2025-01-01", "2026-12-31")]:
            sub = f[(f["t"] >= int(pd.Timestamp(lo_d, tz="UTC").timestamp()))
                    & (f["t"] <= int(pd.Timestamp(hi_d, tz="UTC").timestamp()))]
            if len(sub):
                print(f"    {label}: n={len(sub)} 24h 均值 {sub['r24'].mean():+.2f}%")

    lines.extend(["\n## 解读\n",
                   "- n≈30 左右 → 大概率样本不足，方向性观察；显著结果也需事件数 ≥20 且方向跨 regime 一致。",
                   "- 加息期 vs 宽松期方向相反 → regime 依赖的事件驱动；一致 → 结构性的 post-FOMC drift。",
                   "- 若 SPY 无效应但 NVDA 有 → 事件驱动聚焦高 beta（s007 可转向个股事件）。",
                   "- FOMC 日期为官方预定日程，脚本内硬编码需人工核对。"])
    REPORT.parent.mkdir(parents=True, exist_ok=True)
    REPORT.write_text("\n".join(lines) + "\n", encoding="utf-8")
    print(f"wrote {REPORT}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
