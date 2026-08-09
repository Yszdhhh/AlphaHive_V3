r"""146_funding_extreme_reversal.py — funding 拥挤度极值反转（s005，机制类 E-A）。

假设：永续资金费率是杠杆拥挤度的直接定价。funding 极端正 = 多头拥挤付费（易踩踏），
极端负 = 空头拥挤付费（易轧空）。检验 funding 30d 归一化极值后 24h/72h/168h 价格方向：
- 事件 A：norm > 0.95（极度拥挤多头）→ 预期回落（GO_SHORT 检验）
- 事件 B：norm < 0.05（极度拥挤空头）→ 预期反弹（GO_LONG 检验）

数据（全本地）：funding = binance_free_db/history/funding（110 回填，2022-01→今，
69 symbols，8h 一次）；价格 = coinglass klines ctx（113 load_price_ctx）。
基线：同期随机 symbol×时点横截面（draw_random_events + bootstrap_ci，seed=2026）。
冷却 72h；事件 ts = fundingTime（ms）。
诚实边界：funding 与 wash_cvd 共享价格数据但事件源独立（funding 事件 ≠ washout 事件）；
与 s001 的增量检验在结果显著后再做。

输出：reports/funding_extreme_reversal.md
用法：python scripts/146_funding_extreme_reversal.py
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

from harness.lib.event_study import (  # noqa: E402
    DEFAULT_HORIZONS,
    bootstrap_ci,
    draw_random_events,
    forward_stats,
)

load_universe_symbols = m113.load_universe_symbols
load_price_ctx = m113.load_price_ctx
load_funding_series = m113.load_funding_series
episode_of = m113.episode_of

REPORT = PROJECT_ROOT / "reports" / "funding_extreme_reversal.md"
LO_MS = int(pd.Timestamp("2022-01-01", tz="UTC").timestamp() * 1000)
HI_MS = int(pd.Timestamp("2026-06-23", tz="UTC").timestamp() * 1000)
NORM_HI = 0.95
NORM_LO = 0.05
ROLL = 90          # 30 天（8h 间隔）
MIN_PERIODS = 45
COOLDOWN_H = 72
MIN_EVENTS = 30
N_BASELINE = 3000
SEED = 2026


def funding_norm(fund: pd.Series) -> pd.Series:
    """30d min-max 归一化（近似分位）：1=窗口最高拥挤，0=窗口最低。"""
    lo = fund.rolling(ROLL, min_periods=MIN_PERIODS).min()
    hi = fund.rolling(ROLL, min_periods=MIN_PERIODS).max()
    return (fund - lo) / (hi - lo).replace(0, np.nan)


def detect_events(fund_norm: pd.Series, hi: float, lo: float,
                  cooldown_h: int) -> tuple[list[int], list[int]]:
    """返回 (A 拥挤多头事件 ts, B 拥挤空头事件 ts)，各带 72h 冷却。"""
    vals = fund_norm.to_numpy(dtype=float)
    idx = fund_norm.index.to_numpy(dtype=np.int64)
    cd = int(cooldown_h * 3_600_000)
    ev_a: list[int] = []
    last_a = -10**18
    ev_b: list[int] = []
    last_b = -10**18
    for i in range(len(vals)):
        if not np.isfinite(vals[i]):
            continue
        t = int(idx[i])
        if vals[i] > hi and t - last_a >= cd:
            ev_a.append(t)
            last_a = t
        if vals[i] < lo and t - last_b >= cd:
            ev_b.append(t)
            last_b = t
    return ev_a, ev_b


def forward_stats_on(ctx: pd.DataFrame, ev_ts: np.ndarray) -> pd.DataFrame:
    """对给定 ts 数组计算前向收益（对齐 ctx index，事件 ts 需在 ctx 上有行）。"""
    rows = []
    axis = ctx.index.to_numpy(dtype=np.int64)
    for t in ev_ts:
        pos = int(np.searchsorted(axis, t, side="right")) - 1
        if pos < 0:
            continue
        # 只保留 ctx 上精确匹配（funding 时点本身就在 ctx 轴附近）
        if abs(axis[pos] - t) > 3_600_000:
            continue
        close = ctx["close"].to_numpy(dtype=float)
        if pos + 168 >= len(close):
            continue
        rows.append({"t": t,
                     "r24": (close[pos + 24] / close[pos] - 1) * 100.0,
                     "r72": (close[pos + 72] / close[pos] - 1) * 100.0,
                     "r168": (close[pos + 168] / close[pos] - 1) * 100.0})
    return pd.DataFrame(rows)


def main() -> int:
    symbols = load_universe_symbols()
    fundings = load_funding_series(symbols)
    ctxs = load_price_ctx(symbols)
    print(f"funding 覆盖 {len(fundings)} | 价格 ctx {len(ctxs)}")

    ev_a_all: list[dict] = []
    ev_b_all: list[dict] = []
    for sym in symbols:
        if sym not in fundings or sym not in ctxs:
            continue
        fund = fundings[sym]
        fund = fund[fund.index >= LO_MS]
        norm = funding_norm(fund)
        ev_a, ev_b = detect_events(norm, NORM_HI, NORM_LO, COOLDOWN_H)
        if ev_a:
            ev_a_all.append({"symbol": sym, "ts": ev_a})
        if ev_b:
            ev_b_all.append({"symbol": sym, "ts": ev_b})
    print(f"事件 A（拥挤多头）{sum(len(e['ts']) for e in ev_a_all)} | "
          f"事件 B（拥挤空头）{sum(len(e['ts']) for e in ev_b_all)}")

    rng = np.random.default_rng(SEED)
    base = draw_random_events(ctxs, N_BASELINE, rng, max_forward_hours=168,
                              start_ms=LO_MS, end_ms=HI_MS)
    base_parts = []
    for bs, bg in base.groupby("symbol", sort=False):
        if bs in ctxs:
            base_parts.append(forward_stats(ctxs[bs], bg.copy(), DEFAULT_HORIZONS))
    base_df = pd.concat(base_parts, ignore_index=True) if base_parts else pd.DataFrame()

    def agg(ev_list: list[dict]) -> pd.DataFrame:
        rows = []
        for e in ev_list:
            ctx = ctxs[e["symbol"]]
            f = forward_stats_on(ctx, np.array(e["ts"], dtype=np.int64))
            if not f.empty:
                f["symbol"] = e["symbol"]
                rows.append(f)
        return pd.concat(rows, ignore_index=True) if rows else pd.DataFrame()

    fa = agg(ev_a_all)
    fb = agg(ev_b_all)
    print(f"对齐后 A {len(fa)} | B {len(fb)}")

    lines = ["# funding 拥挤度极值反转（s005）\n",
             f"- 生成：{datetime.now(timezone.utc):%Y-%m-%d %H:%M UTC}",
             f"- 事件：8h funding 30d min-max 归一化 > {NORM_HI}（A 拥挤多头）/ < {NORM_LO}（B 拥挤空头），72h 冷却",
             f"- 数据：funding {len(fundings)} symbols（110 回填，2022-01→今）；价格 coinglass klines",
             "- 基线：同期随机 symbol×时点横截面（bootstrap 95% CI，seed=2026）",
             "- 判定：A 事件 CI 上界<0 → GO_SHORT（拥挤多头踩踏）；B 事件 CI 下界>0 → GO_LONG（拥挤空头轧空）\n",
             "| 事件 | n | 24h 均值 | 24h 超额 | 24h CI | 72h 超额 | 72h CI | 168h 超额 | 168h CI | 胜率 | 判定 |",
             "|---|---|---:|---:|---:|---:|---:|---:|---:|---:|---|"]

    for label, f, direction in [("A 拥挤多头(>0.95)", fa, "short"),
                                ("B 拥挤空头(<0.05)", fb, "long")]:
        n = len(f)
        if n == 0:
            lines.append(f"| {label} | 0 | - | - | - | - | - | - | - | - | 无事件 |")
            continue
        er = f["r24"].to_numpy(dtype=float)
        br24 = pd.to_numeric(base_df["ret_24h"], errors="coerce").dropna().to_numpy()
        br72 = pd.to_numeric(base_df["ret_72h"], errors="coerce").dropna().to_numpy()
        br168 = pd.to_numeric(base_df["ret_168h"], errors="coerce").dropna().to_numpy()
        ci = bootstrap_ci(er, br24, n_boot=1000, alpha=0.05, seed=SEED)
        ci72 = bootstrap_ci(f["r72"].to_numpy(dtype=float), br72, n_boot=1000, alpha=0.05, seed=SEED + 1)
        ci168 = bootstrap_ci(f["r168"].to_numpy(dtype=float), br168, n_boot=1000, alpha=0.05, seed=SEED + 2)
        win = float((er > 0).mean() * 100)
        if direction == "short":
            verdict = ("样本不足" if n < MIN_EVENTS else
                       "GO_SHORT" if ci["ci_hi"] < 0 else
                       "GO_LONG" if ci["ci_lo"] > 0 else "NO_GO")
        else:
            verdict = ("样本不足" if n < MIN_EVENTS else
                       "GO_LONG" if ci["ci_lo"] > 0 else
                       "GO_SHORT" if ci["ci_hi"] < 0 else "NO_GO")
        lines.append(f"| {label} | {n} | {er.mean():+.2f}% | {ci['mean_diff']:+.2f}% "
                     f"| [{ci['ci_lo']:+.2f}, {ci['ci_hi']:+.2f}] | {ci72['mean_diff']:+.2f}% "
                     f"| [{ci72['ci_lo']:+.2f}, {ci72['ci_hi']:+.2f}] | {ci168['mean_diff']:+.2f}% "
                     f"| [{ci168['ci_lo']:+.2f}, {ci168['ci_hi']:+.2f}] | {win:.0f}% | **{verdict}** |")
        print(f"[146] {label}: n={n} ex24={ci['mean_diff']:+.2f}% ex72={ci72['mean_diff']:+.2f}% "
              f"ex168={ci168['mean_diff']:+.2f}% {verdict}")

    lines.extend(["\n## 解读\n",
                   "- funding 极值是机制类信号（拥挤度直接定价），与 wash_cvd 事件源独立。",
                   "- 若 A 显著 GO_SHORT → 拥挤多头踩踏存在；若 B 显著 GO_LONG → 拥挤空头轧空存在。",
                   "- 负结果 = 拥挤度已被价格吸收（funding 无预测力），不宣称证伪。",
                   "- 若任一方向显著：与 s001 的增量检验（wash_cvd 事件内 funding 极值是否增强）另立预注册。"])
    REPORT.parent.mkdir(parents=True, exist_ok=True)
    REPORT.write_text("\n".join(lines) + "\n", encoding="utf-8")
    print(f"wrote {REPORT}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
