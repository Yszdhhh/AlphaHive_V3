r"""151_taker_imbalance.py — order flow imbalance 极值事件研究（路线 #1，数据侧）。

背景：wash_cvd 用 cvd_divergence（价格 z vs CVD z 的背离）——价格-流量【状态】背离。
本脚本测流量【脉冲】：24h taker imbalance 极值（主动买/卖失衡）后的价格方向，
与 wash_cvd 正交（一阶导 vs 二阶关系）。

定义（每 symbol，无前视）：
- imb_bar = (2*taker_buy_quote_vol - quote_volume) / quote_volume ∈ [-1,+1]
- imb_24h = rolling(24).sum(2*tb - qv) / rolling(24).sum(qv)（24h 流量失衡）
- norm = 30d min-max 归一化（720h rolling）
- 事件 A：norm > 0.9（极度主动买入 = FOMO 追高）→ 做空检验
- 事件 B：norm < 0.1（极度主动卖出 = 恐慌抛售）→ 做多检验
- 72h 冷却

数据：coinglass klines（2021-12→2026-06，66 symbols，113 同源）。
基线：同期随机 symbol×时点横截面（bootstrap 95% CI，seed=2026）。
判定：A 事件 CI 上界<0 → GO_SHORT；B 事件 CI 下界>0 → GO_LONG；n<30 → 样本不足。

输出：reports/taker_imbalance.md
用法：python scripts/151_taker_imbalance.py
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

REPORT = PROJECT_ROOT / "reports" / "taker_imbalance.md"
LO_MS = int(pd.Timestamp("2022-01-01", tz="UTC").timestamp() * 1000)
HI_MS = int(pd.Timestamp("2026-06-30", tz="UTC").timestamp() * 1000)
MIN_EVENTS = 30
N_BASELINE = 3000
SEED = 2026
NORM_HI = 0.9
NORM_LO = 0.1
COOLDOWN_H = 72


def build_imbalance_ctx(sym: str) -> pd.DataFrame | None:
    """coinglass klines → ctx + imb_24h + norm（无前视）。"""
    p = m113.COINGLASS_RAW1H / "klines" / f"{sym}.parquet"
    if not p.exists():
        return None
    df = pd.read_parquet(p)
    if not {"open_time", "close", "quote_volume", "taker_buy_quote_volume"}.issubset(df.columns):
        return None
    ts = pd.to_numeric(df["open_time"], errors="coerce").to_numpy(dtype=np.int64)
    close = pd.to_numeric(df["close"], errors="coerce").to_numpy(dtype=float)
    qv = pd.to_numeric(df["quote_volume"], errors="coerce").to_numpy(dtype=float)
    tb = pd.to_numeric(df["taker_buy_quote_volume"], errors="coerce").to_numpy(dtype=float)
    # 假 bar 清洗（113 同款：30d rolling median 偏离 50x 抹除；防下架/价格错乱）
    s = pd.Series(close)
    med = s.rolling(720, min_periods=360).median()
    ratio = s / med.replace(0, np.nan)
    close = np.where((ratio >= 0.02) & (ratio <= 50.0), close, np.nan)
    flow = pd.Series(2 * tb - qv, index=pd.Index(ts)).sort_index()
    qvs = pd.Series(qv, index=pd.Index(ts)).sort_index()
    num = flow.rolling(24).sum()
    den = qvs.rolling(24).sum()
    imb = (num / den.replace(0, np.nan)).replace([np.inf, -np.inf], np.nan)
    lo = imb.rolling(720, min_periods=360).min()
    hi = imb.rolling(720, min_periods=360).max()
    norm = ((imb - lo) / (hi - lo).replace(0, np.nan)).replace([np.inf, -np.inf], np.nan)
    out = pd.DataFrame({"close": close}, index=pd.Index(ts))
    out["imb_24h"] = imb.to_numpy()
    out["imb_norm"] = norm.to_numpy()
    return out.dropna(subset=["close"])


def detect_events(ctx: pd.DataFrame, hi: float, lo: float) -> tuple[list[int], list[int]]:
    axis = ctx.index.to_numpy(dtype=np.int64)
    norm = ctx["imb_norm"].to_numpy(dtype=float)
    cd = COOLDOWN_H * 3_600_000
    ev_a: list[int] = []
    last_a = -10**18
    ev_b: list[int] = []
    last_b = -10**18
    for i in range(len(norm)):
        if not np.isfinite(norm[i]):
            continue
        t = int(axis[i])
        if norm[i] > hi and t - last_a >= cd:
            ev_a.append(t)
            last_a = t
        if norm[i] < lo and t - last_b >= cd:
            ev_b.append(t)
            last_b = t
    return ev_a, ev_b


def main() -> int:
    symbols = m113.load_universe_symbols()
    ctxs = {s: build_imbalance_ctx(s) for s in symbols}
    ctxs = {s: c for s, c in ctxs.items() if c is not None and len(c) > 800}
    print(f"imbalance ctx {len(ctxs)}")

    ev_a_all: list[dict] = []
    ev_b_all: list[dict] = []
    for sym, ctx in ctxs.items():
        a, b = detect_events(ctx, NORM_HI, NORM_LO)
        if a:
            ev_a_all.append({"symbol": sym, "ts": a})
        if b:
            ev_b_all.append({"symbol": sym, "ts": b})
    print(f"事件 A（主动买入极值）{sum(len(e['ts']) for e in ev_a_all)} | "
          f"事件 B（主动卖出极值）{sum(len(e['ts']) for e in ev_b_all)}")

    rng = np.random.default_rng(SEED)
    base = draw_random_events(ctxs, N_BASELINE, rng, max_forward_hours=168,
                              start_ms=LO_MS, end_ms=HI_MS)
    bparts = []
    for bs, bg in base.groupby("symbol", sort=False):
        if bs in ctxs:
            bparts.append(forward_stats(ctxs[bs], bg.copy(), DEFAULT_HORIZONS))
    base_df = pd.concat(bparts, ignore_index=True) if bparts else pd.DataFrame()
    br24 = pd.to_numeric(base_df["ret_24h"], errors="coerce").dropna().to_numpy()
    br168 = pd.to_numeric(base_df["ret_168h"], errors="coerce").dropna().to_numpy()

    def agg(ev_list: list[dict]) -> pd.DataFrame:
        rows = []
        for e in ev_list:
            ctx = ctxs[e["symbol"]]
            axis = ctx.index.to_numpy(dtype=np.int64)
            close = ctx["close"].to_numpy(dtype=float)
            for t in e["ts"]:
                pos = int(np.searchsorted(axis, t, side="right")) - 1
                if pos < 0 or pos + 168 >= len(close):
                    continue
                r24 = (close[pos + 24] / close[pos] - 1) * 100.0
                r168 = (close[pos + 168] / close[pos] - 1) * 100.0
                if np.isfinite(r24) and np.isfinite(r168):
                    rows.append({"t": t, "r24": r24, "r168": r168})
        return pd.DataFrame(rows)

    fa = agg(ev_a_all)
    fb = agg(ev_b_all)
    print(f"对齐后 A {len(fa)} | B {len(fb)}")

    lines = ["# order flow imbalance 极值事件研究（151，路线 #1）\n",
             f"- 生成：{datetime.now(timezone.utc):%Y-%m-%d %H:%M UTC}",
             f"- imb_24h = 24h(主动买−主动卖)/24h 总量；norm = 30d min-max",
             f"- 事件 A：norm>{NORM_HI}（FOMO 追高，做空检验）；B：norm<{NORM_LO}（恐慌抛售，做多检验）；{COOLDOWN_H}h 冷却",
             "- 数据：coinglass klines（2021-12→2026-06）；基线：随机横截面（bootstrap 95% CI，seed=2026）",
             "- 与 wash_cvd 正交性：imbalance=流量脉冲（CVD 一阶导），wash_cvd=价格-流量背离\n",
             "| 事件 | n | 24h 均值 | 24h 超额 | 24h CI | 168h 均值 | 168h 超额 | 168h CI | 168h 中位数 | 判定 |",
             "|---|---|---:|---:|---:|---:|---:|---:|---:|---|"]

    for label, f, direction in [("A 主动买入极值(>0.9)", fa, "short"),
                                ("B 主动卖出极值(<0.1)", fb, "long")]:
        n = len(f)
        if n == 0:
            lines.append(f"| {label} | 0 | - | - | - | - | - | - | - | 无事件 |")
            continue
        r24 = f["r24"].to_numpy(dtype=float)
        r168 = f["r168"].to_numpy(dtype=float)
        ci24 = bootstrap_ci(r24, br24, n_boot=1000, alpha=0.05, seed=SEED)
        ci168 = bootstrap_ci(r168, br168, n_boot=1000, alpha=0.05, seed=SEED + 1)
        if direction == "short":
            verdict = ("样本不足" if n < MIN_EVENTS else
                       "GO_SHORT" if ci168["ci_hi"] < 0 else
                       "GO_LONG" if ci168["ci_lo"] > 0 else "NO_GO")
        else:
            verdict = ("样本不足" if n < MIN_EVENTS else
                       "GO_LONG" if ci168["ci_lo"] > 0 else
                       "GO_SHORT" if ci168["ci_hi"] < 0 else "NO_GO")
        lines.append(f"| {label} | {n} | {r24.mean():+.2f}% | {ci24['mean_diff']:+.2f}% "
                     f"| [{ci24['ci_lo']:+.2f}, {ci24['ci_hi']:+.2f}] | {r168.mean():+.2f}% "
                     f"| {ci168['mean_diff']:+.2f}% | [{ci168['ci_lo']:+.2f}, {ci168['ci_hi']:+.2f}] "
                     f"| {np.median(r168):+.2f}% | **{verdict}** |")
        print(f"[151] {label}: n={n} ex168={ci168['mean_diff']:+.2f}% med={np.median(r168):+.2f}% {verdict}")

    lines.extend(["\n## 解读\n",
                   "- A 显著 GO_SHORT → FOMO 追高后回落（情绪脉冲反转）——新 edge 候选。",
                   "- B 显著 GO_LONG → 恐慌抛售后反弹（与 wash_cvd 的机制呼应但信号源独立）。",
                   "- 若与 wash_cvd 事件重叠高 → 是 wash_cvd 的影子；重叠低 → 独立维度（151 后补增量检验）。",
                   "- 无效应 → 流量脉冲已被价格吸收（imbalance 无预测力）。"])
    REPORT.parent.mkdir(parents=True, exist_ok=True)
    REPORT.write_text("\n".join(lines) + "\n", encoding="utf-8")
    print(f"wrote {REPORT}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
