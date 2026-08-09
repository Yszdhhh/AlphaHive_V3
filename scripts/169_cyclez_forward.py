"""169_cyclez_forward.py — s013 前向积累：wash_cvd 前向流 × 周期指标分层。

165 发现 cycle_z<−1 × Mayer≥1（趋势超卖）168h +7.98%（2022-23，n=30 单窗口）。
本脚本对 108/109 前向积累流（forward_replay_returns.csv）回填周期指标并分层统计，
积累 s013 前向样本。

指标（无前视）：mayer = BTC 价格/200日线（rolling，拼接 coinglass+binance 历史）；
cycle_z = log价对截至【当前】全期回归残差 z（统计用，标注：交易用滚动拟合重算）。
分层：s013 组 = cycle_z<−1 且 Mayer≥1；对照 = 其余。

输出：reports/cyclez_forward_stats.md（追加模式）
用法：python scripts/169_cyclez_forward.py
"""
from __future__ import annotations

import sys
from datetime import datetime, timezone
from pathlib import Path

import numpy as np
import pandas as pd

PROJECT_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(PROJECT_ROOT))

REPORTS = PROJECT_ROOT / "reports"
EVENTS_CSV = REPORTS / "forward_replay_returns.csv"
REPORT_MD = REPORTS / "cyclez_forward_stats.md"
COINGLASS_ROOT = Path(r"C:\Users\10639\Desktop\🔒 加密资产\coinglass_db\raw_1h")
BINANCE_ROOT = Path(r"C:\Users\10639\Desktop\加密\binance_free_db\raw_1h")


def btc_daily_cycle() -> pd.DataFrame:
    """BTC 日线 → mayer（rolling 200d）与 cycle_z（全期对数回归残差 z）。"""
    closes: dict = {}
    for root in [COINGLASS_ROOT / "klines", BINANCE_ROOT / "klines"]:
        p = root / "BTCUSDT.parquet"
        if not p.exists():
            continue
        try:
            kl = pd.read_parquet(p, columns=["open_time", "close"])
        except Exception:
            continue
        ts = pd.to_numeric(kl["open_time"], errors="coerce").astype(np.int64)
        cl = pd.to_numeric(kl["close"], errors="coerce").astype(float)
        day = pd.to_datetime(ts, unit="ms", utc=True).dt.tz_localize(None).dt.normalize()
        for d, c in zip(day, cl):
            if np.isfinite(c):
                closes[d] = c
    daily = pd.Series(closes).sort_index()
    ma200 = daily.rolling(200, min_periods=120).mean()
    mayer = daily / ma200.replace(0, np.nan)
    logp = np.log(daily)
    x = np.arange(len(daily))
    A = np.vstack([x, np.ones(len(x))]).T
    beta, _, _, _ = np.linalg.lstsq(A, logp.to_numpy(), rcond=None)
    resid = logp.to_numpy() - (beta[0] * x + beta[1])
    cyc = (logp.to_numpy() - (beta[0] * x + beta[1])) / np.std(resid)
    return pd.DataFrame({"mayer": mayer, "cycle_z": cyc}, index=daily.index).dropna()


def main() -> int:
    if not EVENTS_CSV.exists():
        print("[169] 无前向积累")
        return 0
    ev = pd.read_csv(EVENTS_CSV)
    if ev.empty:
        print("[169] 空")
        return 0
    cycle = btc_daily_cycle()
    ev_day = pd.to_datetime(pd.to_numeric(ev["timestamp_ms"], errors="coerce"),
                            unit="ms", utc=True).dt.tz_localize(None).dt.normalize()
    ev["mayer"] = ev_day.map(cycle["mayer"]).to_numpy()
    ev["cycle_z"] = ev_day.map(cycle["cycle_z"]).to_numpy()
    usable = ev[ev["mayer"].notna()].copy()
    s013 = usable[(usable["cycle_z"] < -1.0) & (usable["mayer"] >= 1.0)]
    other = usable[~((usable["cycle_z"] < -1.0) & (usable["mayer"] >= 1.0))]

    lines = ["# s013 前向积累（169）\n",
             f"- 生成：{datetime.now(timezone.utc):%Y-%m-%d %H:%M UTC}",
             f"- 前向事件（108/109 流）：{len(usable)}；s013 组（cycle_z<−1 × Mayer≥1）：{len(s013)}",
             "- ⚠️ cycle_z 用截至当前的全期回归（统计口径）；交易口径需滚动拟合重算\n",
             "| 组 | n | ret_24h 均值 | ret_24h 中位 | ret_168h 均值 | ret_168h 中位 | 胜率(24h) |",
             "|---|---|---:|---:|---:|---:|---|"]

    def row(label: str, g: pd.DataFrame) -> None:
        n = len(g)
        if n == 0:
            lines.append(f"| {label} | 0 | - | - | - | - | - |")
            return
        r24 = pd.to_numeric(g.get("ret_24h"), errors="coerce").dropna()
        r168 = pd.to_numeric(g.get("ret_168h"), errors="coerce").dropna()
        lines.append(f"| {label} | {n} | {r24.mean():+.2f}% | {r24.median():+.2f}% "
                     f"| {r168.mean():+.2f}% | {r168.median():+.2f}% | {100 * (r24 > 0).mean():.0f}% |")
        print(f"[169] {label}: n={n} r24={r24.mean():+.2f}% r168={r168.mean():+.2f}%")

    row("全部前向", usable)
    row("s013 组（cycle_z<−1×Mayer≥1）", s013)
    row("其余", other)
    row("cycle_z<−1（单条件）", usable[usable["cycle_z"] < -1.0])

    if REPORT_MD.exists():
        old = REPORT_MD.read_text(encoding="utf-8")
        # 保留头部，替换表格段
        head = old.split("| 组 |")[0]
        lines = [head] + lines[1:]
    REPORT_MD.write_text("\n".join(lines) + "\n", encoding="utf-8")
    print(f"wrote {REPORT_MD}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
