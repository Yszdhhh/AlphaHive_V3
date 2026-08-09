r"""165_cyclez_review.py — s013 复核：cycle_z<−1（对数趋势带超卖）× wash_cvd。

164 发现 cycle_z<−1 中位数 +2.09% 转正（唯一与超卖直觉同向），n=145 CI 跨零。
本脚本完整复核（门槛 G）：
1. 独立窗口（2022-23 vs 2024-26）
2. 尾部切除（去 top5%）
3. 阈值敏感性（z<−0.75 / <−1 / <−1.25）
4. 与 Mayer 交叉（cycle_z<−1 × Mayer 高低——两个超卖指标的一致性）

输出：reports/cyclez_review.md
用法：python scripts/165_cyclez_review.py
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

REPORT = PROJECT_ROOT / "reports" / "cyclez_review.md"
LO_MS = int(pd.Timestamp("2022-01-01", tz="UTC").timestamp() * 1000)
HI_MS = int(pd.Timestamp("2026-06-30", tz="UTC").timestamp() * 1000)
MIN_EVENTS = 30
N_BASELINE = 3000
SEED = 2026


def btc_cycle() -> pd.DataFrame:
    p = m113.COINGLASS_RAW1H / "klines" / "BTCUSDT.parquet"
    df = pd.read_parquet(p, columns=["open_time", "close"])
    df = df.drop_duplicates(subset="open_time").sort_values("open_time")
    df["ts"] = pd.to_numeric(df["open_time"], errors="coerce").astype(np.int64)
    df["close"] = pd.to_numeric(df["close"], errors="coerce").astype(float)
    df["day"] = pd.to_datetime(df["ts"], unit="ms", utc=True).dt.tz_localize(None).dt.normalize()
    daily = df.groupby("day")["close"].last().dropna()
    ma200 = daily.rolling(200, min_periods=120).mean()
    mayer = daily / ma200.replace(0, np.nan)
    logp = np.log(daily)
    x = np.arange(len(daily))
    A = np.vstack([x, np.ones(len(x))]).T
    beta, _, _, _ = np.linalg.lstsq(A, logp.to_numpy(), rcond=None)
    fit = beta[0] * x + beta[1]
    resid = logp.to_numpy() - fit
    sd = np.std(resid)
    cyc = pd.Series((logp.to_numpy() - fit) / sd, index=daily.index)
    return pd.DataFrame({"mayer": mayer, "cycle_z": cyc}).dropna()


def main() -> int:
    cycle = btc_cycle()
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
    events["mayer"] = ev_day.map(cycle["mayer"]).to_numpy()
    events["cycle_z"] = ev_day.map(cycle["cycle_z"]).to_numpy()
    usable = events[events["cycle_z"].notna()].copy()
    print(f"事件 {len(events)} | 有 cycle_z {len(usable)}")

    rng = np.random.default_rng(SEED)
    base = draw_random_events(ctxs, N_BASELINE, rng, max_forward_hours=168,
                              start_ms=LO_MS, end_ms=HI_MS)
    bparts = []
    for bs, bg in base.groupby("symbol", sort=False):
        if bs in ctxs:
            bparts.append(forward_stats(ctxs[bs], bg.copy(), DEFAULT_HORIZONS))
    base_df = pd.concat(bparts, ignore_index=True) if bparts else pd.DataFrame()
    br168 = pd.to_numeric(base_df["ret_168h"], errors="coerce").dropna().to_numpy()

    lines = ["# s013 复核：cycle_z<−1 × wash_cvd（165）\n",
             f"- 生成：{datetime.now(timezone.utc):%Y-%m-%d %H:%M UTC}",
             "- cycle_z = log 价全期回归残差 z（彩虹图式趋势偏离）",
             "- 门槛 G：CI / 独立窗口 / 尾切 / 阈值敏感性\n",
             "| 组 | n | 168h 超额 | CI | 中位数 | 尾切 | W1(22-23) | W2(24-26) | 判定 |",
             "|---|---|---:|---:|---:|---:|---:|---:|---|"]

    def row(label: str, g: pd.DataFrame) -> None:
        n = len(g)
        if n == 0:
            lines.append(f"| {label} | 0 | - | - | - | - | - | - | 无事件 |")
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
        lines.append(f"| {label} | {n} | {ci['mean_diff']:+.2f}% "
                     f"| [{ci['ci_lo']:+.2f}, {ci['ci_hi']:+.2f}] | {np.median(r):+.2f}% "
                     f"| {tail:+.2f}% | {w1s} | {w2s} | **{verdict}** |")
        print(f"[165] {label}: n={n} ex168={ci['mean_diff']:+.2f}% med={np.median(r):+.2f}% {verdict}")

    row("cycle_z<−0.75", usable[usable["cycle_z"] < -0.75])
    row("cycle_z<−1.0（164 原口径）", usable[usable["cycle_z"] < -1.0])
    row("cycle_z<−1.25", usable[usable["cycle_z"] < -1.25])
    cz = usable[usable["cycle_z"] < -1.0]
    row("  × Mayer<1.0（双超卖一致）", cz[cz["mayer"] < 1.0])
    row("  × Mayer≥1.0（趋势超卖）", cz[cz["mayer"] >= 1.0])

    lines.extend(["\n## 裁决\n",
                   "- 三阈值单调 + 独立窗口同号 + 尾切仍正 → s013 升级候选（s001 的周期条件层）。",
                   "- 与 Mayer 交叉：双超卖一致组更强 → 周期门控组合有效；趋势超卖组更强 → cycle_z 独立于 Mayer。",
                   "- 任一环节失败 → s013 关闭（认知保留）。"])
    REPORT.parent.mkdir(parents=True, exist_ok=True)
    REPORT.write_text("\n".join(lines) + "\n", encoding="utf-8")
    print(f"wrote {REPORT}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
