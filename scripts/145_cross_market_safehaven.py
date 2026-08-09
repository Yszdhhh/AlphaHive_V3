r"""145_cross_market_safehaven.py — 跨市场避险联动：加密崩盘日贵金属/避险资产是否脉冲。

假设（s006，E-C 信息/资金流延迟）：加密市场崩盘（BTC 急跌）→ 避险资金脉冲流入
贵金属（XAU/XAG）→ 事件后 24h/72h 黄金白银超额为正。

数据（全部本地缓存，无需新拉取）：
- BTC：binance_free_db raw_1h klines（与 108 同源）
- XAU/XAG/GBP：data/pyth_raw/（144 已缓存）

事件：BTC ret_24h < -5%（急跌日；72h 冷却）——不依赖山寨，纯大盘事件。
基线：避险资产同区间随机时间点（bootstrap 95% CI）。
对照：BTC 大跌日 vs 全样本，黄金白银英镑的 24h/72h/168h 均值差。

诚实边界：避险联动若是"新闻同日"驱动（如 CPI 当天股债同跌），事件窗口可能
混入共同宏观驱动而非资金脉冲——报告里标注，不宣称因果。

输出：reports/cross_market_safehaven.md
用法：python scripts/145_cross_market_safehaven.py
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

REPORT = PROJECT_ROOT / "reports" / "cross_market_safehaven.md"
BTC_KLINES = Path(r"C:\Users\10639\Desktop\加密\binance_free_db\raw_1h\klines\BTCUSDT.parquet")
PYTH_DIR = PROJECT_ROOT / "data" / "pyth_raw"
SAFEHAVENS = {
    "METAL.XAU_USD.parquet": ("黄金 XAU", "24/7"),
    "METAL.XAG_USD.parquet": ("白银 XAG", "24/7"),
    "FX.GBP_USD.parquet": ("英镑 GBP", "24/7"),
}
BTC_CRASH = -5.0   # BTC 24h 跌幅阈值
COOLDOWN_H = 72


def load_btc() -> pd.DataFrame:
    kl = pd.read_parquet(BTC_KLINES)
    kl = kl[["open_time", "close"]].dropna().drop_duplicates(subset="open_time").sort_values("open_time")
    kl["open_time"] = pd.to_numeric(kl["open_time"], errors="coerce").astype(np.int64)
    return kl


def main() -> int:
    btc = load_btc()
    ts = btc["open_time"].to_numpy(dtype=np.int64)
    close = btc["close"].to_numpy(dtype=float)
    ret24 = pd.Series(close).pct_change(24) * 100.0
    fired = np.isfinite(ret24.to_numpy()) & (ret24.to_numpy() < BTC_CRASH)
    events: list[int] = []
    last = -10**18
    for i in np.flatnonzero(fired):
        t = int(ts[i])
        if t - last >= COOLDOWN_H * 3600:
            events.append(t)
            last = t
    ev = np.array(events, dtype=np.int64)
    print(f"BTC 崩盘事件（24h < -5%，72h 冷却）: {len(ev)}")

    lines = ["# 跨市场避险联动：加密崩盘 → 贵金属脉冲？\n",
             f"- 生成：{datetime.now(timezone.utc):%Y-%m-%d %H:%M UTC}",
             f"- 事件：BTC ret_24h < -{abs(BTC_CRASH):.0f}%（binance_free_db 1h），{COOLDOWN_H}h 冷却，共 {len(ev)} 次",
             "- 观察：事件后 24h/72h/168h 避险资产收益（vs 同资产随机时间基线，bootstrap 95% CI）",
             "- ⚠️ 共同宏观驱动混淆：若崩盘与 CPI/FOMC 同日，事件窗口含宏观而非纯资金脉冲，报告不做因果宣称\n",
             "| 避险资产 | 事件 n | 24h 均值 | 24h 超额 | 95% CI | 72h 超额 | 168h 超额 | 判定 |",
             "|---|---|---:|---:|---:|---:|---:|---|"]

    rng = np.random.default_rng(2026)
    lo, hi = int(ts.min()), int(ts.max())
    for fname, (name, mode) in SAFEHAVENS.items():
        p = PYTH_DIR / fname
        if not p.exists():
            lines.append(f"| {name} | 数据缺失 | - | - | - | - | - | - |")
            continue
        d = pd.read_parquet(p)
        sts = d["t"].to_numpy(dtype=np.int64)
        sclose = d["c"].to_numpy(dtype=float)
        # 事件时点 = BTC 崩盘 bar（ms）→ 秒对齐 Pyth（t 为秒单位）
        fwd = []
        for t in ev:
            t_s = int(t) // 1000
            pos = int(np.searchsorted(sts, t_s, side="right")) - 1
            if pos < 0 or pos + 168 >= len(sclose):
                continue
            fwd.append({"t": t_s,
                        "r24": (sclose[pos + 24] / sclose[pos] - 1) * 100.0,
                        "r72": (sclose[pos + 72] / sclose[pos] - 1) * 100.0,
                        "r168": (sclose[pos + 168] / sclose[pos] - 1) * 100.0})
        f = pd.DataFrame(fwd)
        n = len(f)
        if n == 0:
            lines.append(f"| {name} | 0 | - | - | - | - | - | - | 无重叠 |")
            continue
        # 基线：同资产随机时间点（事件跨度内 ×50）
        ev_lo, ev_hi = int(f["t"].min()), int(f["t"].max())
        base_t = np.sort(rng.integers(ev_lo, ev_hi + 1, size=max(3000, n * 50), dtype=np.int64))
        bf = []
        for t in base_t:
            pos = int(np.searchsorted(sts, t, side="right")) - 1
            if pos < 0 or pos + 168 >= len(sclose):
                continue
            bf.append((sclose[pos + 24] / sclose[pos] - 1) * 100.0)
        base24 = np.array(bf)
        ci = bootstrap_ci(f["r24"].to_numpy(), base24, n_boot=1000, alpha=0.05, seed=2026)
        verdict = ("样本不足" if n < 30 else
                   "GO_LONG" if ci["ci_lo"] > 0 else
                   "GO_SHORT" if ci["ci_hi"] < 0 else "NO_GO")
        lines.append(f"| {name} | {n} | {f['r24'].mean():+.2f}% | {ci['mean_diff']:+.2f}% "
                     f"| [{ci['ci_lo']:+.2f}, {ci['ci_hi']:+.2f}] | {f['r72'].mean():+.2f}% "
                     f"| {f['r168'].mean():+.2f}% | **{verdict}** |")
        print(f"[145] {name}: n={n} ex24={ci['mean_diff']:+.2f}% {verdict}")

    lines.extend(["\n## 解读\n",
                   "- 若避险资产在 BTC 崩盘后显著正超额 → 跨市场资金脉冲存在，可做对冲/联动策略（s006）。",
                   "- 若 NO_GO → 加密与贵金属各自独立定价（或联动为同日宏观驱动、无滞后脉冲），s006 关闭。",
                   "- 判定语义：超额 vs 同资产随机基线；CI 跨零 = 无统计证据。"])
    REPORT.parent.mkdir(parents=True, exist_ok=True)
    REPORT.write_text("\n".join(lines) + "\n", encoding="utf-8")
    print(f"wrote {REPORT}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
