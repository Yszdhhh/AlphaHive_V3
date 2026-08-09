r"""142_lcs_susceptibility.py — wash_cvd × liquidation susceptibility.

LCS is deliberately defined before seeing the result as OI notional divided by
rolling 24h quote volume, with each symbol compared to its own rolling 30d
q75/q90 distribution. It is a read-only conditional event study; it does not
change scan rules or trading configuration.

The report separates an exploratory 2024 training window from the 2025+
holdout window. A non-significant contrast is reported as insufficient power,
not proof of no effect.
"""
from __future__ import annotations

import argparse
import importlib.util
import sys
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

load_universe_symbols = m113.load_universe_symbols
load_price_ctx = m113.load_price_ctx
load_funding_series = m113.load_funding_series
detect_events = m115.detect_events
episode_of = m113.episode_of
RAW_1H = m113.COINGLASS_RAW1H
REPORT = PROJECT_ROOT / "reports" / "lcs_susceptibility.md"
LO_MS = int(pd.Timestamp("2024-06-01", tz="UTC").timestamp() * 1000)
SPLIT_MS = int(pd.Timestamp("2025-01-01", tz="UTC").timestamp() * 1000)
HI_MS = int(pd.Timestamp("2026-06-23 23:00", tz="UTC").timestamp() * 1000)
ROLL_H = 720
MIN_EVENTS = 30


def _asof_lcs(ctx: pd.DataFrame, symbol: str) -> pd.DataFrame:
    """Return ctx with as-of LCS ratio and rolling q75/q90 thresholds."""
    p = RAW_1H / "klines" / f"{symbol}.parquet"
    oi_p = RAW_1H / "oi_ohlc" / f"{symbol}.parquet"
    if not p.exists() or not oi_p.exists():
        ctx["lcs_ratio"] = np.nan
        ctx["lcs_q75"] = np.nan
        ctx["lcs_q90"] = np.nan
        return ctx
    kl = pd.read_parquet(p)
    oi = pd.read_parquet(oi_p)
    kts = pd.to_numeric(kl["open_time"], errors="coerce").to_numpy(dtype=np.int64)
    qv = pd.to_numeric(kl.get("quote_volume"), errors="coerce").to_numpy(dtype=float)
    qv_s = pd.Series(qv, index=pd.Index(kts))
    qv_s = qv_s[~qv_s.index.duplicated(keep="last")].sort_index()
    oi_ts = pd.to_numeric(oi["time"], errors="coerce").to_numpy(dtype=np.int64)
    oi_close = pd.to_numeric(oi["close"], errors="coerce").to_numpy(dtype=float)
    oi_s = pd.Series(oi_close, index=pd.Index(oi_ts))
    oi_s = oi_s[~oi_s.index.duplicated(keep="last")].sort_index()
    axis = ctx.index.to_numpy(dtype=np.int64)
    qv_24 = qv_s.rolling(24, min_periods=12).sum().reindex(axis)
    oi_asof = oi_s.reindex(axis)
    ratio = oi_asof / qv_24.replace(0, np.nan)
    # Thresholds use only the symbol's preceding 30d/current as-of history.
    ctx["lcs_ratio"] = ratio.to_numpy(dtype=float)
    ctx["lcs_q75"] = ratio.rolling(ROLL_H, min_periods=360).quantile(0.75).to_numpy(dtype=float)
    ctx["lcs_q90"] = ratio.rolling(ROLL_H, min_periods=360).quantile(0.90).to_numpy(dtype=float)
    return ctx


def attach_lcs(ctxs: dict[str, pd.DataFrame], events: pd.DataFrame) -> pd.DataFrame:
    out = events.copy()
    for c in ("lcs_ratio", "lcs_q75", "lcs_q90"):
        out[f"{c}_at_event"] = np.nan
    for sym, group in out.groupby("symbol", sort=False):
        if sym not in ctxs:
            continue
        ctx = ctxs[sym]
        pos = np.searchsorted(ctx.index.to_numpy(dtype=np.int64),
                              group["timestamp"].to_numpy(dtype=np.int64), side="right") - 1
        pos = np.clip(pos, 0, len(ctx) - 1)
        for c in ("lcs_ratio", "lcs_q75", "lcs_q90"):
            vals = pd.to_numeric(ctx[c], errors="coerce").to_numpy(dtype=float)
            out.loc[group.index, f"{c}_at_event"] = vals[pos]
    out["lcs_q75_hit"] = out["lcs_ratio_at_event"] >= out["lcs_q75_at_event"]
    out["lcs_q90_hit"] = out["lcs_ratio_at_event"] >= out["lcs_q90_at_event"]
    return out


def build_baseline(ctxs: dict[str, pd.DataFrame], start_ms: int, end_ms: int,
                   n: int, seed: int) -> pd.DataFrame:
    rng = np.random.default_rng(seed)
    sampled = draw_random_events(ctxs, n, rng, max_forward_hours=168,
                                 start_ms=start_ms, end_ms=end_ms)
    if sampled.empty:
        return pd.DataFrame()
    parts = [forward_stats(ctxs[sym], g.copy(), DEFAULT_HORIZONS)
             for sym, g in sampled.groupby("symbol", sort=False) if sym in ctxs]
    return pd.concat(parts, ignore_index=True) if parts else pd.DataFrame()


def stats(ev: pd.DataFrame, base: pd.DataFrame, seed: int, label: str) -> dict:
    r = {"label": label, "n": int(len(ev)), "unique_ts": int(ev["timestamp"].nunique()) if not ev.empty else 0}
    er = pd.to_numeric(ev.get("ret_24h", pd.Series(dtype=float)), errors="coerce").dropna().to_numpy()
    br = pd.to_numeric(base.get("ret_24h", pd.Series(dtype=float)), errors="coerce").dropna().to_numpy()
    if len(er) == 0 or len(br) == 0:
        r.update(mean=np.nan, excess=np.nan, ci_lo=np.nan, ci_hi=np.nan, verdict="无基线")
        return r
    ci = bootstrap_ci(er, br, n_boot=1000, alpha=0.05, seed=seed)
    r.update(mean=float(np.mean(er)), excess=float(ci["mean_diff"]),
             ci_lo=float(ci["ci_lo"]), ci_hi=float(ci["ci_hi"]),
             ret168=float(pd.to_numeric(ev.get("ret_168h", pd.Series(dtype=float)), errors="coerce").mean()),
             verdict=("样本不足" if len(er) < MIN_EVENTS else
                      "GO_LONG" if ci["ci_lo"] > 0 else
                      "GO_SHORT" if ci["ci_hi"] < 0 else "NO_GO"))
    return r


def contrast(a: pd.DataFrame, b: pd.DataFrame, seed: int) -> dict:
    ar = pd.to_numeric(a.get("ret_24h", pd.Series(dtype=float)), errors="coerce").dropna().to_numpy()
    br = pd.to_numeric(b.get("ret_24h", pd.Series(dtype=float)), errors="coerce").dropna().to_numpy()
    if not len(ar) or not len(br):
        return {"mean_diff": np.nan, "ci_lo": np.nan, "ci_hi": np.nan}
    return bootstrap_ci(ar, br, n_boot=1000, alpha=0.05, seed=seed)


def pct(x: float, plus: bool = False) -> str:
    return "-" if not np.isfinite(x) else (f"{x:+.2f}%" if plus else f"{x:.2f}%")


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--n-baseline", type=int, default=3000)
    ap.add_argument("--seed", type=int, default=2026)
    ap.add_argument("--symbols", default=None)
    args = ap.parse_args()
    symbols = args.symbols.split(",") if args.symbols else load_universe_symbols()
    ctxs = load_price_ctx(symbols)
    fundings = load_funding_series(symbols)
    for sym, ctx in ctxs.items():
        _asof_lcs(ctx, sym)
    print(f"price_ctx={len(ctxs)} funding={len(fundings)}")

    events = []
    for sym, ctx in ctxs.items():
        ev = detect_events(sym, ctx, fundings.get(sym), "wash_cvd")
        if not ev.empty:
            events.append(ev)
    all_events = pd.concat(events, ignore_index=True) if events else pd.DataFrame(columns=["symbol", "timestamp"])
    all_events = all_events[(all_events["timestamp"] >= LO_MS) & (all_events["timestamp"] <= HI_MS)].copy()
    fwd = []
    for sym, group in all_events.groupby("symbol", sort=False):
        fwd.append(forward_stats(ctxs[sym], group.copy(), DEFAULT_HORIZONS))
    all_events = pd.concat(fwd, ignore_index=True) if fwd else all_events
    all_events = attach_lcs(ctxs, all_events)
    all_events["period"] = np.where(all_events["timestamp"] < SPLIT_MS, "train_2024", "holdout_2025+")
    all_events["episode"] = episode_of(all_events["timestamp"].to_numpy(dtype=np.int64))
    usable = all_events[all_events["lcs_ratio_at_event"].notna()].copy()
    print(f"wash_cvd={len(all_events)} LCS_usable={len(usable)} q75={int(usable['lcs_q75_hit'].sum())} q90={int(usable['lcs_q90_hit'].sum())}")

    base_all = build_baseline(ctxs, LO_MS, HI_MS, args.n_baseline, args.seed)
    bases = {
        "train_2024": build_baseline(ctxs, LO_MS, SPLIT_MS - 1, args.n_baseline, args.seed + 1),
        "holdout_2025+": build_baseline(ctxs, SPLIT_MS, HI_MS, args.n_baseline, args.seed + 2),
    }
    rows = []
    for period, group in usable.groupby("period", sort=False):
        base = bases[period]
        for label, mask in [("wash_cvd control", np.ones(len(group), dtype=bool)),
                            ("LCS q75", group["lcs_q75_hit"].to_numpy()),
                            ("LCS q90", group["lcs_q90_hit"].to_numpy())]:
            sub = group.loc[mask] if label != "wash_cvd control" else group
            rows.append((period, stats(sub, base, args.seed, label)))
    pooled_rows = []
    for label, mask in [("wash_cvd control", np.ones(len(usable), dtype=bool)),
                        ("LCS q75", usable["lcs_q75_hit"].to_numpy()),
                        ("LCS q90", usable["lcs_q90_hit"].to_numpy())]:
        pooled_rows.append(("pooled", stats(usable.loc[mask] if label != "wash_cvd control" else usable,
                                             base_all, args.seed, label)))

    lines = ["# wash_cvd × LCS 清算易感度事件研究\n",
             f"- 生成：{pd.Timestamp.now(tz='UTC'):%Y-%m-%d %H:%M UTC}",
             "- LCS 预注册定义：事件时点 as-of 的 OI close / rolling 24h quote_volume；每个 symbol 自身 rolling 30d q75/q90。",
             "- 事件：115 wash_cvd，72h 冷却；窗口 2024-06-01~2026-06-23；基线：同期随机 symbol×时点，bootstrap 95% CI。",
             "- 训练/留出：train_2024=<2025-01-01；holdout_2025+≥2025-01-01；阈值不按结果调参。",
             "> 重要：事件同一时点可能跨币种相关；bootstrap 未做时间/币种 cluster，CI 可能偏窄。非显著结果只能表示功效不足，不能证明无效。\n",
             "## 事件覆盖\n",
             f"- wash_cvd 总事件：{len(all_events)}；LCS 可用：{len(usable)}；q75 命中：{int(usable['lcs_q75_hit'].sum()) if not usable.empty else 0}；q90 命中：{int(usable['lcs_q90_hit'].sum()) if not usable.empty else 0}",
             f"- 唯一事件时点：{usable['timestamp'].nunique() if not usable.empty else 0}\n",
             "## pooled 结果\n",
             "| 组 | n | 唯一时点 | 24h 均值 | 24h 超额 | 95% CI | 168h 均值 | 判定 |",
             "|---|---:|---:|---:|---:|---|---:|---|"]
    for period, r in pooled_rows:
        lines.append(f"| {r['label']} | {r['n']} | {r['unique_ts']} | {pct(r.get('mean', np.nan))} | {pct(r.get('excess', np.nan), True)} | [{pct(r.get('ci_lo', np.nan), True)}, {pct(r.get('ci_hi', np.nan), True)}] | {pct(r.get('ret168', np.nan), True)} | {r['verdict']} |")
    lines.append("\n## train / holdout 结果\n")
    lines.extend(["| 期间 | 组 | n | 唯一时点 | 24h 均值 | 24h 超额 | 95% CI | 判定 |", "|---|---|---:|---:|---:|---:|---|---|"])
    for period, r in rows:
        lines.append(f"| {period} | {r['label']} | {r['n']} | {r['unique_ts']} | {pct(r.get('mean', np.nan))} | {pct(r.get('excess', np.nan), True)} | [{pct(r.get('ci_lo', np.nan), True)}, {pct(r.get('ci_hi', np.nan), True)}] | {r['verdict']} |")
    lines.append("\n## 增量对照（相对同一期间 wash_cvd control）\n")
    lines.append("| 期间 | LCS 组 | control n | LCS n | LCS−control 24h 差 | 95% CI |")
    lines.append("|---|---|---:|---:|---:|---|")
    for period, group in usable.groupby("period", sort=False):
        for label, mask in [("q75", group["lcs_q75_hit"]), ("q90", group["lcs_q90_hit"])]:
            c = contrast(group.loc[mask], group, args.seed + 10)
            lines.append(f"| {period} | {label} | {len(group)} | {int(mask.sum())} | {pct(c.get('mean_diff', np.nan), True)} | [{pct(c.get('ci_lo', np.nan), True)}, {pct(c.get('ci_hi', np.nan), True)}] |")
    lines.extend(["\n## 裁决规则\n",
                   "- 只有 holdout 中 n≥30、增量 CI 下界>0 且方向不被 2025+ episode 反转，才进入 shadow 候选；本脚本不会改配置。",
                   "- holdout CI 跨零：功效不足/未确认；不是 NO_GO 的科学证伪。",
                   "- 若 pooled 正而 holdout 不成立：历史探索结果，不能升级。",
                   "- 该研究不与 liq_short_z>1 合并挑优；联合筛选必须另行预注册。"])
    REPORT.parent.mkdir(parents=True, exist_ok=True)
    REPORT.write_text("\n".join(lines) + "\n", encoding="utf-8")
    print(f"wrote {REPORT}")


if __name__ == "__main__":
    main()
