r"""184_macro_state_joint.py — 市场阶段 × 宏观状态联合剖析（用户方向：固定 A 调整 B/C）。

当前市场叙事：宏观降息 + BTC 低波动筑底 + 标普新高 + 中期大选临近。
本脚本把可测状态合成，wash_cvd 事件按状态组合分层：
- EASING：FEDFUNDS 90 天下降 ≥25bp（降息周期，asof 无前视）
- BTC_LOWVOL：BTC 20d 波动率 < 近 3 年中位（低波动筑底）
- SPX_HIGH：SP500 距 52 周高点 < 2%（标普新高）
- ELECTION：距中期/总统选举日 <6 个月（大选窗口）

方法：单状态分层 + 双状态组合（固定 A 调 B/C 的 2×2），不展开全 3 维笛卡尔积（样本稀释）。
基线：随机横截面；168h 超额 + 中位数；门槛 G。

输出：reports/macro_state_joint.md
用法：python scripts/184_macro_state_joint.py
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

REPORT = PROJECT_ROOT / "reports" / "macro_state_joint.md"
MACRO = Path(r"C:\Users\10639\Desktop\🔒 加密资产\coinglass_db\macro")
LO_MS = int(pd.Timestamp("2022-01-01", tz="UTC").timestamp() * 1000)
HI_MS = int(pd.Timestamp("2026-06-30", tz="UTC").timestamp() * 1000)
MIN_EVENTS = 30
N_BASELINE = 3000
SEED = 2026

# 美国大选日（总统年 11 月第一个周一后的周二；中期=非总统年）
ELECTION_DAYS = [
    "2004-11-02", "2006-11-07", "2008-11-04", "2010-11-02", "2012-11-06",
    "2014-11-04", "2016-11-08", "2018-11-06", "2020-11-03", "2022-11-08",
    "2024-11-05", "2026-11-03",
]


def load_macro_series() -> dict[str, pd.Series]:
    out = {}
    for fname, col in [("FEDFUNDS.parquet", "fed"), ("SP500.parquet", "spx")]:
        p = MACRO / fname
        if not p.exists():
            continue
        d = pd.read_parquet(p)
        idx = pd.to_datetime(d.index) if not isinstance(d.index, pd.DatetimeIndex) else d.index
        out[col] = pd.Series(pd.to_numeric(d["close"], errors="coerce").to_numpy(), index=idx).dropna()
    return out


def main() -> int:
    ms = load_macro_series()
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
    fwd_parts = []
    for sym, g in events.groupby("symbol", sort=False):
        if sym in ctxs:
            fwd_parts.append(forward_stats(ctxs[sym], g.copy(), DEFAULT_HORIZONS))
    events = pd.concat(fwd_parts, ignore_index=True) if fwd_parts else events

    ev_day = pd.to_datetime(events["timestamp"].to_numpy(), unit="ms", utc=True).tz_localize(None).normalize()
    # 状态构造（asof 无前视）
    if "fed" in ms:
        fed = ms["fed"].resample("D").last().ffill()
        fed_chg90 = fed.diff(90)
        events["EASING"] = (fed_chg90.reindex(ev_day) <= -0.25).to_numpy(dtype=float)
    if "spx" in ms:
        spx = ms["spx"]
        hi52 = spx.rolling(252, min_periods=120).max()
        near_hi = (spx / hi52 - 1) >= -0.02
        events["SPX_HIGH"] = near_hi.reindex(ev_day, method="ffill").to_numpy(dtype=float)
    # BTC 低波动
    p = m113.COINGLASS_RAW1H / "klines" / "BTCUSDT.parquet"
    df = pd.read_parquet(p, columns=["open_time", "close"])
    ts = pd.to_numeric(df["open_time"], errors="coerce").to_numpy(dtype=np.int64)
    cl = pd.to_numeric(df["close"], errors="coerce").to_numpy(dtype=float)
    s = pd.Series(cl, index=pd.Index(ts))
    s = s[~s.index.duplicated(keep="last")].sort_index()
    s.index = pd.to_datetime(s.index, unit="ms", utc=True).tz_localize(None)
    vol20 = s.resample("D").last().dropna().pct_change().rolling(20).std()
    med3y = vol20.rolling(1095, min_periods=300).median()
    events["BTC_LOWVOL"] = (vol20.reindex(ev_day) <= med3y.reindex(ev_day)).to_numpy(dtype=float)
    # 选举窗口（前 6 个月）
    elec = pd.to_datetime(ELECTION_DAYS)
    in_window = np.zeros(len(events), dtype=bool)
    for ed in elec:
        in_window |= (ev_day >= ed - pd.Timedelta(days=182)) & (ev_day <= ed)
    events["ELECTION"] = in_window.astype(float)
    print(f"事件 {len(events)} | 状态覆盖 EASING {events['EASING'].notna().sum() if 'EASING' in events else 0}")

    rng = np.random.default_rng(SEED)
    base = draw_random_events(ctxs, N_BASELINE, rng, max_forward_hours=168,
                              start_ms=LO_MS, end_ms=HI_MS)
    bparts = []
    for bs, bg in base.groupby("symbol", sort=False):
        if bs in ctxs:
            bparts.append(forward_stats(ctxs[bs], bg.copy(), DEFAULT_HORIZONS))
    base_df = pd.concat(bparts, ignore_index=True) if bparts else pd.DataFrame()
    br168 = pd.to_numeric(base_df["ret_168h"], errors="coerce").dropna().to_numpy()

    lines = ["# 市场阶段 × 宏观状态联合剖析（184）\n",
             f"- 生成：{datetime.now(timezone.utc):%Y-%m-%d %H:%M UTC}",
             "- 状态（asof 无前视）：EASING=FEDFUNDS 90d 降 ≥25bp / BTC_LOWVOL=BTC 20d 波动率<3y 中位",
             "- SPX_HIGH=SP500 距 52 周高 <2% / ELECTION=距大选日 <6 个月",
             "- 方法：单状态 + 双状态 2×2（固定 A 调 B/C），不全笛卡尔积\n",
             "| 组 | n | 168h 超额 | CI | 中位数 | 尾切 | 判定 |",
             "|---|---|---:|---:|---:|---:|---|"]

    def row(label: str, g: pd.DataFrame) -> None:
        n = len(g)
        if n < MIN_EVENTS:
            lines.append(f"| {label} | {n} | - | - | - | - | 样本不足 |")
            print(f"[184] {label}: n={n} 样本不足")
            return
        r = pd.to_numeric(g["ret_168h"], errors="coerce").dropna().to_numpy()
        ci = bootstrap_ci(r, br168, n_boot=1000, alpha=0.05, seed=SEED)
        thr = np.quantile(r, 0.95)
        tail = r[r <= thr].mean()
        verdict = ("样本不足" if n < MIN_EVENTS else
                   "GO_LONG" if ci["ci_lo"] > 0 else
                   "GO_SHORT" if ci["ci_hi"] < 0 else "NO_GO")
        lines.append(f"| {label} | {n} | {ci['mean_diff']:+.2f}% "
                     f"| [{ci['ci_lo']:+.2f}, {ci['ci_hi']:+.2f}] | {np.median(r):+.2f}% "
                     f"| {tail:+.2f}% | **{verdict}** |")
        print(f"[184] {label}: n={n} ex168={ci['mean_diff']:+.2f}% med={np.median(r):+.2f}% {verdict}")

    for st in ["EASING", "BTC_LOWVOL", "SPX_HIGH", "ELECTION"]:
        if st not in events.columns:
            continue
        row(f"{st}=1", events[events[st] == 1])
        row(f"{st}=0", events[events[st] == 0])
    # 双状态组合（固定 EASING 调 BTC_LOWVOL × SPX_HIGH）
    if all(c in events.columns for c in ["EASING", "BTC_LOWVOL", "SPX_HIGH"]):
        e = events[events["EASING"] == 1]
        row("EASING × BTC_LOWVOL", e[e["BTC_LOWVOL"] == 1])
        row("EASING × SPX_HIGH", e[e["SPX_HIGH"] == 1])
        row("EASING × 双低波×新高", e[(e["BTC_LOWVOL"] == 1) & (e["SPX_HIGH"] == 1)])

    lines.extend(["\n## 解读\n",
                  "- 某状态组合显著强于其余 → 市场阶段门控成立（s016 候选：当前降息+低波动+新高窗口）。",
                  "- 全部无差 → 宏观状态不调制 wash_cvd（与 120/175 一致：币级内生）。",
                  "- 样本稀释警告：双状态组合 n 减半，三状态组合不展开。"])
    REPORT.parent.mkdir(parents=True, exist_ok=True)
    REPORT.write_text("\n".join(lines) + "\n", encoding="utf-8")
    print(f"wrote {REPORT}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
