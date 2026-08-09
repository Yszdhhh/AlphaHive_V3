r"""202_dune_panic_backtest.py — P7 恐慌日回测：3pool USDT 溢价 × BTC 抄底（历史版）。

用 Dune 回填的 Curve 3pool USDT 历史价（2020-09 → 今，data/dune/usdt_3pool_daily.csv）
把 P7 的"稳定币溢价 × BTC 抄底"命题在**历史恐慌事件**上检验（P2P 场外溢价无历史，
3pool 链上价是唯一可回测的恐慌 gauge）：
- A1 恐慌日分层：BTC 日跌 ≤-5%（抄底语境）按当日 USDT 溢价分层（深度脱锚 ≤-30bps vs 持平/转正）
  → BTC 前向 24/72/168h——脱锚加深是"恐慌高潮（超卖反弹）"还是"系统性恶化（继续跌）"？
- A2 溢价尖峰择时：USDT 溢价 ≥ +50bps（场外 fomo/入场）日 → BTC 前向（等积累，历史检验）
基线：随机日 BTC 前向（bootstrap CI）。

数据：BTCUSDT 日线 = fapi klines 全史（2020-09 → 今，公开接口当日拉取，无 credits）。
输出：reports/dune_panic_backtest.md
用法：python scripts/202_dune_panic_backtest.py
"""
from __future__ import annotations

import json
import sys
import time
import urllib.request
from datetime import datetime, timezone
from pathlib import Path

import numpy as np
import pandas as pd

PROJECT_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(PROJECT_ROOT))

from harness.lib.event_study import bootstrap_ci  # noqa: E402

PREMIUM_CSV = PROJECT_ROOT / "data" / "dune" / "usdt_3pool_daily.csv"
REPORT = PROJECT_ROOT / "reports" / "dune_panic_backtest.md"

DIP_RET = -5.0        # BTC 大跌定义（%）
DEEP_DEPEG_BPS = -30.0  # 深度脱锚分层阈值
FOMO_PREMIUM_BPS = 50.0  # 溢价尖峰阈值
COOLDOWN_DAYS = 7
MIN_EVENTS = 10
SEED = 2026
UA = {"User-Agent": "Mozilla/5.0"}


def btc_daily() -> pd.Series:
    """fapi BTCUSDT 日线 close（2020-09+），本地无此期历史。"""
    rows: list[list] = []
    start = 1_600_300_800_000  # 2020-09-16
    for _ in range(8):
        url = (f"https://fapi.binance.com/fapi/v1/klines?symbol=BTCUSDT"
               f"&interval=1d&startTime={start}&limit=1500")
        req = urllib.request.Request(url, headers=UA)
        with urllib.request.urlopen(req, timeout=30) as r:
            data = json.loads(r.read())
        if not data:
            break
        rows.extend(data)
        start = int(data[-1][0]) + 86_400_000
        if len(data) < 1500:
            break
        time.sleep(0.2)
    s = pd.Series({int(k[0]): float(k[4]) for k in rows})
    return s.sort_index()


def main() -> int:
    prem = pd.read_csv(PREMIUM_CSV)
    prem["date"] = pd.to_datetime(prem["date"], utc=True)
    prem["premium_bps"] = pd.to_numeric(prem["premium_bps"], errors="coerce")
    prem = prem.dropna(subset=["premium_bps"]).set_index("date")["premium_bps"].sort_index()

    btc = btc_daily()
    print(f"3pool 溢价 {len(prem)} 天 | BTC 日线 {len(btc)} 天")
    # BTC ms 索引 → UTC 日期；与溢价对齐（共同日期）
    btc_dt = pd.Series(btc.to_numpy(), index=pd.to_datetime(btc.index, unit="ms", utc=True))
    idx = prem.index.intersection(btc_dt.index)
    p = prem.loc[idx]
    c = btc_dt.loc[idx]
    ret = c.pct_change() * 100.0
    print(f"对齐 {len(idx)} 天 | 溢价范围 {p.min():.1f}~{p.max():.1f} bps")

    # 前向收益（日线 → 1/3/7 天；注意：非小时）
    fwd = {}
    for h in (1, 3, 7):
        fwd[h] = (c.shift(-h) / c - 1.0) * 100.0

    # 事件检测（cooldown）→ 日期列表
    def events(mask: pd.Series) -> list:
        out: list = []
        last = None
        for d, m in mask.items():
            if m and (last is None or (d - last).days >= COOLDOWN_DAYS):
                out.append(d)
                last = d
        return out

    dips = events(ret <= DIP_RET)
    print(f"BTC 大跌日（≤{DIP_RET}%）: {len(dips)} 次")

    def stats(ev_days: list, label: str, lines: list[str]) -> None:
        vals = {h: fwd[h].loc[ev_days].dropna() for h in (1, 3, 7)}
        lines.append(f"| {label} | {len(ev_days)} | "
                     + " | ".join(f"{v.mean():+.2f}%（n={len(v)}）" for h, v in vals.items()) + " | - |")

    lines = ["# 3pool USDT 溢价 × BTC 抄底恐慌日回测（202，P7 历史版）\n",
             f"- 生成：{datetime.now(timezone.utc):%Y-%m-%d %H:%M UTC}",
             f"- 数据：Curve 3pool USDT/DAI 日频中位价（Dune，{idx.min():%Y-%m-%d}→{idx.max():%Y-%m-%d}，{len(idx)} 天）",
             f"- 大跌日定义：BTC 日跌 ≤{DIP_RET}%（{COOLDOWN_DAYS} 天冷却）；前向 = 事件日收盘后 1/3/7 天（日线）",
             f"- 基线：随机日 BTC 前向（bootstrap 95% CI，seed={SEED}）\n",
             "| 组 | n | 1d | 3d | 7d | 判定 |",
             "|---|---|---:|---:|---:|---|"]

    # A1：大跌日 × 溢价分层
    deep = [d for d in dips if p.loc[d] <= DEEP_DEPEG_BPS]
    hold = [d for d in dips if p.loc[d] > DEEP_DEPEG_BPS]
    stats(deep, f"大跌日+深度脱锚（溢价≤{DEEP_DEPEG_BPS:.0f}bps）", lines)
    stats(hold, f"大跌日+溢价未深脱锚（>{DEEP_DEPEG_BPS:.0f}bps）", lines)

    # A2：溢价尖峰日
    spikes = events(p >= FOMO_PREMIUM_BPS)
    stats(spikes, f"溢价尖峰日（≥+{FOMO_PREMIUM_BPS:.0f}bps）", lines)

    # bootstrap 对比（24h/168h 超额 vs 随机日基线）
    rng = np.random.default_rng(SEED)
    base_t = pd.Series(np.random.choice(idx, size=2000, replace=True))
    lines.append("\n## 超额 vs 随机日基线\n")
    lines.append("| 组 | 1d 超额 CI | 7d 超额 CI |")
    lines.append("|---|---:|---:|")
    for label, g in [("大跌+深脱锚", deep), ("大跌+未深脱锚", hold), ("溢价尖峰", spikes)]:
        cells = []
        for h in (1, 7):
            ev_v = fwd[h].loc[g].dropna().to_numpy(dtype=float)
            bs_v = fwd[h].loc[base_t].dropna().to_numpy(dtype=float)
            if len(ev_v) >= MIN_EVENTS and len(bs_v):
                ci = bootstrap_ci(ev_v, bs_v, seed=SEED)
                cells.append(f"{ci['mean_diff']:+.2f}% [{ci['ci_lo']:+.2f}, {ci['ci_hi']:+.2f}]")
            else:
                cells.append(f"样本不足(n={len(ev_v)})")
        lines.append(f"| {label} | {cells[0]} | {cells[1]} |")

    lines += ["\n## 解读\n",
              "- 深度脱锚（≤-30bps）发生在恐慌高潮（2020-09 Tether 恐慌 / 2022-05 LUNA）。",
              "- 大跌日脱锚更深 → 若 1/3/7d 显著为正 = 恐慌高潮超卖反弹（溢价加深是抄底确认）；",
              "- 显著为负 = 脱锚是系统性恶化信号（回避）；不显著 = 溢价与 BTC 抄底无关联。",
              "- ⚠️ 3pool 溢价是**链上信用风险 gauge**（恐慌时 USDT 折价），与 P2P 场外溢价",
              "（资金流 gauge，恐慌时反而转正）方向可能相反——两者互补，P7 前向序列继续积累。"]
    REPORT.parent.mkdir(parents=True, exist_ok=True)
    REPORT.write_text("\n".join(lines) + "\n", encoding="utf-8")
    print(f"wrote {REPORT}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
