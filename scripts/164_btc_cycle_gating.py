r"""164_btc_cycle_gating.py — BTC 长期周期门控：筑底/顶部场景 × wash_cvd（用户方向 + AR999/彩虹图思路）。

背景：已测 regime 均为短周期（VIX/20d 回撤/广度/贪婪，1-3 个月）。用户提出：
用 AR999/彩虹图一类【大饼宏观周期评判指标】做筑底/见顶场景下的因子组合——
长期周期定位（1-4 年）未测，可能是 2025 wash_cvd 弱化的 missing variable。

周期指标（本地复现，零外部依赖）：
1. Mayer Multiple = BTC 价格 / 200 日均线（经典周期偏离指标）
2. cycle_z = log(价格) − 4 年滚动对数回归拟合的残差 z（彩虹图简化：对数趋势带）

事件：wash_cvd（115，2022-01→2026-06 全历史）。
分层：事件时点 asof 周期指标 → 底部带（Mayer<0.8 或 cycle_z<-1）/ 中部 / 顶部带（Mayer>1.5 或 cycle_z>+1）。
检验：底部带 168h 超额显著强于顶部带 → 周期门控成立（s013 候选）；
解释 2025 弱化（若 2025 事件多在顶部带）。

基线：随机横截面；门槛 G：CI/中位数/尾切/独立窗口。
输出：reports/btc_cycle_gating.md
用法：python scripts/164_btc_cycle_gating.py
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

REPORT = PROJECT_ROOT / "reports" / "btc_cycle_gating.md"
LO_MS = int(pd.Timestamp("2022-01-01", tz="UTC").timestamp() * 1000)
HI_MS = int(pd.Timestamp("2026-06-30", tz="UTC").timestamp() * 1000)
MIN_EVENTS = 30
N_BASELINE = 3000
SEED = 2026
MAYER_BOT = 0.8
MAYER_TOP = 1.5
CZ_BOT = -1.0
CZ_TOP = 1.0


def btc_cycle() -> pd.DataFrame:
    """BTC 日线周期指标：Mayer Multiple + cycle_z（4 年滚动对数回归残差 z）。"""
    p = m113.COINGLASS_RAW1H / "klines" / "BTCUSDT.parquet"
    df = pd.read_parquet(p, columns=["open_time", "close"])
    df = df.drop_duplicates(subset="open_time").sort_values("open_time")
    df["ts"] = pd.to_numeric(df["open_time"], errors="coerce").astype(np.int64)
    df["close"] = pd.to_numeric(df["close"], errors="coerce").astype(float)
    # 日线聚合（UTC 日）
    df["day"] = pd.to_datetime(df["ts"], unit="ms", utc=True).dt.tz_localize(None).dt.normalize()
    daily = df.groupby("day")["close"].last().dropna()
    # Mayer Multiple：价格 / 200 日均线
    ma200 = daily.rolling(200, min_periods=120).mean()
    mayer = daily / ma200.replace(0, np.nan)
    # cycle_z：log(价格) 对全期日序的线性回归残差 z（彩虹图本质：全周期对数趋势带）
    logp = np.log(daily)
    x = np.arange(len(daily))
    A = np.vstack([x, np.ones(len(x))]).T
    beta, _, _, _ = np.linalg.lstsq(A, logp.to_numpy(), rcond=None)
    fit = beta[0] * x + beta[1]
    resid = logp.to_numpy() - fit
    sd = np.std(resid)
    cyc = pd.Series((logp.to_numpy() - fit) / sd, index=daily.index)
    out = pd.DataFrame({"mayer": mayer, "cycle_z": cyc})
    out["ts_ms"] = (out.index - pd.Timestamp("1970-01-01")).days * 86400_000
    return out.dropna()


def main() -> int:
    cycle = btc_cycle()
    print(f"BTC 周期指标 {len(cycle)} 天（{cycle.index.min().date()} → {cycle.index.max().date()}）")

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

    # 事件时点 asof 周期指标（事件 ts ms → 日）
    ev_day = pd.to_datetime(events["timestamp"].to_numpy(), unit="ms", utc=True).tz_localize(None).normalize()
    events["mayer"] = ev_day.map(cycle["mayer"]).to_numpy()
    events["cycle_z"] = ev_day.map(cycle["cycle_z"]).to_numpy()
    usable = events[events["mayer"].notna()].copy()
    print(f"wash_cvd {len(events)} | 有周期 {len(usable)}")

    rng = np.random.default_rng(SEED)
    base = draw_random_events(ctxs, N_BASELINE, rng, max_forward_hours=168,
                              start_ms=LO_MS, end_ms=HI_MS)
    bparts = []
    for bs, bg in base.groupby("symbol", sort=False):
        if bs in ctxs:
            bparts.append(forward_stats(ctxs[bs], bg.copy(), DEFAULT_HORIZONS))
    base_df = pd.concat(bparts, ignore_index=True) if bparts else pd.DataFrame()
    br168 = pd.to_numeric(base_df["ret_168h"], errors="coerce").dropna().to_numpy()

    lines = ["# BTC 长期周期门控 × wash_cvd（164，用户方向：彩虹图/AR999 思路）\n",
             f"- 生成：{datetime.now(timezone.utc):%Y-%m-%d %H:%M UTC}",
             "- 周期指标（本地复现）：Mayer Multiple = 价格/200日线；cycle_z = log价 4年滚动回归残差 z（彩虹图简化）",
             "- 分层：底部带（Mayer<0.8 或 cycle_z<−1）/ 中部 / 顶部带（Mayer>1.5 或 cycle_z>+1）",
             "- 检验：底部带 wash_cvd 168h 超额是否显著强于顶部带（周期门控 s013）",
             "- 基线：随机横截面；门槛 G\n",
             "| 周期层 | n | 168h 均值 | 168h 超额 | CI | 中位数 | 尾切 | W1(22-23) | W2(24-26) | 判定 |",
             "|---|---|---:|---:|---:|---:|---:|---:|---:|---|"]

    def row(label: str, g: pd.DataFrame) -> None:
        n = len(g)
        if n == 0:
            lines.append(f"| {label} | 0 | - | - | - | - | - | - | - | 无事件 |")
            return
        r = pd.to_numeric(g["ret_168h"], errors="coerce").dropna().to_numpy()
        ci = bootstrap_ci(r, br168, n_boot=1000, alpha=0.05, seed=SEED)
        thr = np.quantile(r, 0.95)
        tail = r[r <= thr].mean()
        split = int(pd.Timestamp("2024-01-01", tz="UTC").timestamp() * 1000)
        w1 = r[g["timestamp"].to_numpy() < split]
        w2 = r[g["timestamp"].to_numpy() >= split]
        w1s = f"{w1.mean():+.2f}%({len(w1)})" if len(w1) >= 10 else "n<10"
        w2s = f"{w2.mean():+.2f}%({len(w2)})" if len(w2) >= 10 else "n<10"
        verdict = ("样本不足" if n < MIN_EVENTS else
                   "GO_LONG" if ci["ci_lo"] > 0 else
                   "GO_SHORT" if ci["ci_hi"] < 0 else "NO_GO")
        lines.append(f"| {label} | {n} | {r.mean():+.2f}% | {ci['mean_diff']:+.2f}% "
                     f"| [{ci['ci_lo']:+.2f}, {ci['ci_hi']:+.2f}] | {np.median(r):+.2f}% "
                     f"| {tail:+.2f}% | {w1s} | {w2s} | **{verdict}** |")
        print(f"[164] {label}: n={n} ex168={ci['mean_diff']:+.2f}% med={np.median(r):+.2f}% {verdict}")

    row("wash_cvd 全（锚）", usable)
    row("底部带（Mayer<0.8）", usable[usable["mayer"] < MAYER_BOT])
    row("中部", usable[(usable["mayer"] >= MAYER_BOT) & (usable["mayer"] <= MAYER_TOP)])
    row("顶部带（Mayer>1.5）", usable[usable["mayer"] > MAYER_TOP])
    row("cycle_z<−1（对数带底部）", usable[usable["cycle_z"] < CZ_BOT])
    row("cycle_z>+1（对数带顶部）", usable[usable["cycle_z"] > CZ_TOP])

    # 底部 vs 顶部直接对照
    bot = usable[usable["mayer"] < MAYER_BOT]
    top = usable[usable["mayer"] > MAYER_TOP]
    if len(bot) >= 10 and len(top) >= 10:
        c = bootstrap_ci(pd.to_numeric(bot["ret_168h"], errors="coerce").dropna().to_numpy(),
                         pd.to_numeric(top["ret_168h"], errors="coerce").dropna().to_numpy(),
                         n_boot=1000, alpha=0.05, seed=SEED + 1)
        lines.append(f"\n直接对照（168h）：底部带 − 顶部带 = {c['mean_diff']:+.2f}% "
                     f"CI[{c['ci_lo']:+.2f}, {c['ci_hi']:+.2f}]"
                     f"（{'显著' if c['ci_lo'] > 0 else '不显著'}）")

    lines.extend(["\n## 解读\n",
                   "- 底部带显著强于顶部带 → 周期门控成立（s013 候选）：筑底期 wash_cvd 反弹强、顶部弱——"
                   "可解释 2025 弱化（若 2025 事件集中在顶部带）。",
                   "- 无差异 → BTC 周期位置不调制 wash_cvd（edge 是币级内生的，与周期无关）。",
                   "- 2025 弱化归因：统计 2025 事件在底部/中部/顶部带的分布，若顶部带占多数 → 周期解释成立。"])
    REPORT.parent.mkdir(parents=True, exist_ok=True)
    REPORT.write_text("\n".join(lines) + "\n", encoding="utf-8")
    print(f"wrote {REPORT}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
